"""In-process pub/sub for live job progress — the push side of SSE streaming.

The studio used to learn about a running generation by polling `GET /api/jobs/{id}` on a
1.2-second timer: a request every 1.2s whether or not anything changed, and up to 1.2s of lag
on every update. This bus replaces the timer with a push. A generation job runs as a FastAPI
background task in the same event loop as the request that streams it, so a plain
``asyncio.Queue`` per subscriber is all it takes to hand progress from the worker to the
`/stream` endpoint the moment it happens — no Redis, no polling, no lag.

Design notes that keep it honest about its limits:

  * **Same-process only.** This works because generation runs inline (``JOB_QUEUE=inline``),
    which is the deployed configuration. The Arq/Redis worker path would run the job in a
    different process, where an in-memory queue can't reach it; streaming there would need a
    Redis pub/sub channel. That is stated rather than pretended around — the endpoint falls
    back to a final snapshot, and the client falls back to polling, if no events arrive.
  * **Best-effort, exactly like the reporter it carries.** Publishing can never fail a run: a
    full or absent queue drops the event. Correctness does not depend on any single event
    arriving, because every event is a *complete* snapshot of the job's progress, not a delta
    — a client that missed one recovers fully from the next, and from the snapshot the
    endpoint sends on connect.
  * **Bounded.** Each subscriber queue is capped; a slow reader drops old events rather than
    growing memory without limit. The terminal event and the on-connect snapshot mean a
    dropped intermediate event is never load-bearing.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

log = logging.getLogger("originshot.events")

# job_id -> set of subscriber queues. Module-level so the worker (publisher) and the SSE
# endpoint (subscriber) share it within the one process/event loop.
_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

# Per-subscriber backlog cap. Small on purpose: progress events are full snapshots, so a
# subscriber only ever needs the latest — old ones are safe to drop under backpressure.
_MAX_BACKLOG = 32


def subscribe(job_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_BACKLOG)
    _subscribers[job_id].add(q)
    return q


def unsubscribe(job_id: str, q: asyncio.Queue) -> None:
    subs = _subscribers.get(job_id)
    if not subs:
        return
    subs.discard(q)
    if not subs:
        _subscribers.pop(job_id, None)


def publish(job_id: str, event: dict) -> None:
    """Fan a progress snapshot out to every subscriber of `job_id`. Never raises.

    A queue that is full (a client too slow to keep up) has its oldest event dropped to make
    room — the newest snapshot is always the most useful one, and no client relies on seeing
    every intermediate event.
    """
    for q in list(_subscribers.get(job_id, ())):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            try:
                q.get_nowait()      # drop the oldest, keep the newest
                q.put_nowait(event)
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001 — progress must never break a run
            log.debug("event publish dropped for job %s: %s", job_id, exc)


def has_subscribers(job_id: str) -> bool:
    return bool(_subscribers.get(job_id))
