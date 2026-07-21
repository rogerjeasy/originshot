"""SSE progress streaming and the in-process event bus.

The stream's contract is what the client relies on: a snapshot on connect (so a late or
post-completion subscriber still gets current state and can stop), one full-job event per
progress change, and a terminal event that ends the stream. The streaming generator is
exercised directly and in-loop — an asyncio.Queue is bound to one event loop, so this is the
only way to test it that mirrors production (where the worker and the endpoint share the loop)
without the flakiness of driving a live stream across threads.
"""
from __future__ import annotations

import json

import pytest

from app import events


# ── The event bus ──────────────────────────────────────────────────────
def test_publish_reaches_every_subscriber():
    q1 = events.subscribe("job-1")
    q2 = events.subscribe("job-1")
    events.publish("job-1", {"id": "job-1", "status": "running"})
    assert q1.get_nowait()["status"] == "running"
    assert q2.get_nowait()["status"] == "running"
    events.unsubscribe("job-1", q1)
    events.unsubscribe("job-1", q2)


def test_unsubscribe_cleans_up():
    q = events.subscribe("job-2")
    assert events.has_subscribers("job-2")
    events.unsubscribe("job-2", q)
    assert not events.has_subscribers("job-2")


def test_publish_to_nobody_is_a_noop():
    events.publish("nobody-listening", {"id": "x"})  # must not raise


def test_a_full_queue_drops_the_oldest_not_the_newest():
    q = events.subscribe("job-3")
    for i in range(events._MAX_BACKLOG + 5):
        events.publish("job-3", {"id": "job-3", "n": i})
    seen = []
    while not q.empty():
        seen.append(q.get_nowait()["n"])
    assert seen[-1] == events._MAX_BACKLOG + 4      # newest kept under backpressure
    assert len(seen) <= events._MAX_BACKLOG
    events.unsubscribe("job-3", q)


# ── The streaming generator ────────────────────────────────────────────
def _payloads(frames: list[str]) -> list[dict]:
    out = []
    for f in frames:
        for line in f.splitlines():
            if line.startswith("data: "):
                out.append(json.loads(line[len("data: "):]))
    return out


def _seed_job(repo, uid="dev-user", status="running"):
    return repo.create_job(uid, {
        "sku_id": "sku-1", "requested_styles": ["studio"], "status": status,
        "steps": [{"style": "studio", "status": "running", "asset_count": 0}],
    })


@pytest.mark.anyio
async def test_finished_job_streams_a_snapshot_then_closes(client):
    """A subscriber that attaches after completion still gets the final state, then the stream ends."""
    from app.api.generate import job_event_stream
    from app.repo import get_repo

    job = _seed_job(get_repo(), status="done")
    frames = [frame async for frame in job_event_stream("dev-user", job["id"])]
    payloads = _payloads(frames)
    assert len(payloads) == 1               # snapshot only; terminal status ends it immediately
    assert payloads[0]["status"] == "done"
    assert payloads[0]["id"] == job["id"]
    assert not events.has_subscribers(job["id"])   # generator cleaned up its subscription


@pytest.mark.anyio
async def test_running_job_streams_pushed_progress_then_terminal(client):
    """Snapshot, then a pushed progress event, then a terminal event that ends the stream."""
    from app.api.generate import job_event_stream
    from app.repo import get_repo

    repo = get_repo()
    job = _seed_job(repo, status="running")
    jid = job["id"]

    gen = job_event_stream("dev-user", jid)
    frames: list[str] = []

    # 1. Snapshot on connect (subscribes internally).
    frames.append(await gen.__anext__())
    # 2. Push a progress event, then a terminal one — distinct snapshots (copied so a later
    #    repo write can't mutate an already-queued event). Mirrors the worker publishing
    #    in-process on the same loop.
    repo.update_job("dev-user", jid, {
        "steps": [{"style": "studio", "status": "done", "asset_count": 1}]})
    events.publish(jid, dict(repo.get_job("dev-user", jid)))
    events.publish(jid, dict(repo.update_job("dev-user", jid, {"status": "done"})))
    # 3. Drain the rest; the terminal event ends the stream.
    async for frame in gen:
        frames.append(frame)

    statuses = [p["status"] for p in _payloads(frames)]
    assert statuses[0] == "running"        # snapshot
    assert statuses[-1] == "done"          # terminal ends it
    assert not events.has_subscribers(jid)  # generator cleaned up its subscription


@pytest.mark.anyio
async def test_idle_stream_emits_a_keepalive(client, monkeypatch):
    """With no events, the generator emits an SSE keepalive comment rather than blocking."""
    from app.api import generate as gen_mod
    from app.repo import get_repo

    monkeypatch.setattr(gen_mod, "_STREAM_HEARTBEAT_SECONDS", 0.05)
    job = _seed_job(get_repo(), status="running")
    gen = gen_mod.job_event_stream("dev-user", job["id"])
    await gen.__anext__()                    # snapshot
    keepalive = await gen.__anext__()        # no event within the heartbeat -> comment
    assert keepalive.startswith(":")
    await gen.aclose()


def test_stream_endpoint_404s_for_a_job_you_do_not_own(client):
    from app.repo import get_repo

    other = get_repo().create_job("someone-else", {"sku_id": "s", "requested_styles": ["studio"]})
    assert client.get(f"/api/jobs/{other['id']}/stream").status_code == 404
