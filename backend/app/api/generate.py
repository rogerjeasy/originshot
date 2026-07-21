"""Generation endpoints — kick off a job and poll its status.

Dev runs the job inline via BackgroundTasks (no Redis needed). For production, switch the
`background.add_task(...)` line to an Arq enqueue (see app/worker.py WorkerSettings).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from .. import credits, pricing
from ..auth import CurrentUser, get_current_user
from ..generation import generation_mode, missing_generation_requirements
from ..models import GenerateRequest, JobOut, StepStatus, Style
from ..repo import get_repo
from ..queue import enqueue_generation, enqueue_replay
from ..security import enforce_generation_quota

router = APIRouter(tags=["generate"])


def assert_generation_available() -> None:
    """503 when the service can't generate at all.

    Checked before a job exists or credit moves: if generation can't run, there is nothing
    to queue and nothing to charge for.
    """
    missing = missing_generation_requirements()
    if missing and generation_mode() == "unconfigured":
        raise HTTPException(
            503,
            "Image generation is currently unavailable — the service is missing: "
            + ", ".join(missing),
        )


def submit_generation(uid: str, sku: dict, sku_id: str, styles: list[str],
                      marketplaces: list[str]) -> dict:
    """Create a job and hold its estimated cost. Returns the job document.

    Shared by the single-SKU endpoint and the catalog runner so the two can't drift on the
    accounting — a batch path that created jobs without holding credit would be a hole
    straight through the denial-of-wallet controls.

    Raises `InsufficientCredit` (402) when the balance won't cover the quote; the caller
    decides whether that fails a request or just blocks one item of a batch.
    """
    repo = get_repo()
    estimate = pricing.estimate_styles(styles)

    # Create the job first so the hold's ledger row can reference it — an orphaned hold with
    # no job_id is exactly the kind of entry that makes a ledger unauditable.
    job = repo.create_job(uid, {
        "sku_id": sku_id,
        "requested_styles": styles,
        "marketplaces": marketplaces,
        "eta_seconds": pricing.eta_seconds(styles),
        "steps": [
            {"style": s, "status": StepStatus.pending.value,
             "eta_seconds": pricing.eta_seconds([s]), "asset_count": 0}
            for s in styles
        ],
    })

    # Caps *spend*, which the request-count quota cannot: one video pack costs ~10x an
    # image pack. Raises 402 with the numbers when the balance won't cover the quote.
    try:
        credits.hold(uid, job_id=job["id"], sku_id=sku_id, amount=estimate)
    except Exception:
        # Don't leave a queued job behind for a run that will never start.
        repo.update_job(uid, job["id"], {
            "status": "failed", "error": "Insufficient credit", "finished_at": None,
        })
        raise
    repo.update_job(uid, job["id"], {"credits_held": estimate})
    return repo.get_job(uid, job["id"]) or job


@router.post("/skus/{sku_id}/generate", response_model=JobOut, status_code=202)
async def generate(
    sku_id: str,
    body: GenerateRequest,
    background: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    repo = get_repo()
    sku = repo.get_sku(user.uid, sku_id)
    if not sku:
        raise HTTPException(404, "Not found")
    if not sku.get("original_sha256"):
        raise HTTPException(400, "Upload a product photo before generating")

    assert_generation_available()
    enforce_generation_quota(user.uid)  # denial-of-wallet protection: caps request volume

    # A user's first authenticated call isn't necessarily /me — generating straight after
    # sign-up must not 402 on a welcome credit that was never issued. Idempotent.
    credits.ensure_signup_grant(user.uid)

    styles = [s.value for s in body.styles]
    marketplaces = [m.value for m in body.marketplaces]
    job = submit_generation(user.uid, sku, sku_id, styles, marketplaces)

    await enqueue_generation(background, user.uid, job["id"], sku_id, styles)
    return job


@router.post("/skus/{sku_id}/assets/{asset_id}/replay", response_model=JobOut, status_code=202)
async def replay(
    sku_id: str,
    asset_id: str,
    background: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    """Re-run a generated asset from its stored manifest — provenance as the spec.

    Same job machinery as /generate (hold → run → settle, quota, per-step progress), but
    the pipeline step is rebuilt from the manifest rather than from the current prompt
    templates. See originshot_pipelines/replay.py for what is and isn't carried over.

    The refusals are specific on purpose: each names the reason the manifest can't drive
    a run, because "409" alone teaches the caller nothing.
    """
    repo = get_repo()
    sku = repo.get_sku(user.uid, sku_id)
    if not sku:
        raise HTTPException(404, "Not found")
    asset = next((a for a in repo.list_assets(user.uid, sku_id) if a.get("id") == asset_id), None)
    if not asset:
        raise HTTPException(404, "Not found")
    if asset.get("is_authentic"):
        raise HTTPException(
            409, "The authentic original is a photograph, not a generation — "
            "there is no manifest to replay."
        )
    if asset.get("style") == Style.video.value:
        raise HTTPException(
            400, "Video assets can't be replayed: their input was a generated intermediate "
            "(the hero frame), not the anchored original."
        )
    if not asset.get("manifest_key"):
        raise HTTPException(
            409, "No stored manifest for this asset — it predates provenance sidecars "
            "or was produced by the dev mock."
        )

    assert_generation_available()
    enforce_generation_quota(user.uid)
    credits.ensure_signup_grant(user.uid)

    job = submit_generation(user.uid, sku, sku_id, [asset["style"]], [])
    # Recorded on the job so the UI can label the run, and so the replayed asset's
    # `replay_of` lineage has a job-side counterpart an operator can query.
    repo.update_job(user.uid, job["id"], {
        "replay_of_sha256": asset["sha256"], "replay_of_asset_id": asset_id,
    })
    await enqueue_replay(background, user.uid, job["id"], sku_id, asset_id)
    return repo.get_job(user.uid, job["id"]) or job


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: CurrentUser = Depends(get_current_user)):
    job = get_repo().get_job(user.uid, job_id)
    if not job:
        raise HTTPException(404, "Not found")
    return job


# How long a single stream connection is allowed to stay open. Comfortably past the longest
# job (the 600s video step) plus overhead; a job that hasn't finished by then is stuck, and
# the client falls back to a poll rather than holding a socket forever.
_STREAM_MAX_SECONDS = 780
# Heartbeat cadence. SSE comment lines keep intermediaries from closing an idle connection and
# let the server notice a vanished client between progress events.
_STREAM_HEARTBEAT_SECONDS = 15
_TERMINAL = {"done", "partial", "failed"}


def _sse(job: dict) -> str:
    """One SSE ``data:`` frame carrying a job snapshot in the GET /jobs/{id} shape."""
    import json

    return f"data: {json.dumps(JobOut(**job).model_dump(mode='json'))}\n\n"


async def job_event_stream(uid: str, job_id: str):
    """Async generator of SSE frames for one job's progress. Extracted so it is directly
    testable in-loop (publishing to the same event loop's queue), without fighting the test
    client's streaming or crossing event loops.

    Emits a snapshot on connect, then one frame per pushed progress event, a keepalive comment
    on idle, and ends on a terminal status or the safety deadline.
    """
    import asyncio

    from .. import events

    repo = get_repo()
    queue = events.subscribe(job_id)
    loop = asyncio.get_event_loop()
    deadline = loop.time() + _STREAM_MAX_SECONDS
    try:
        # Snapshot on connect — subscribed first (above) so an event fired in the gap is
        # queued, not missed; each frame is a full snapshot, so state still converges.
        snapshot = repo.get_job(uid, job_id)
        if snapshot:
            snap_terminal = str(snapshot.get("status")) in _TERMINAL   # capture before yield
            yield _sse(snapshot)
            if snap_terminal:
                return
        while loop.time() < deadline:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=_STREAM_HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"      # SSE comment; ignored by clients
                continue
            # Defence in depth: only ever stream the caller's own job. Job ids are unguessable
            # and the endpoint already checked ownership, but the stream is long-lived so the
            # cheap re-check stays.
            if event.get("owner_uid") not in (None, uid):
                continue
            # Decide terminality from the value we are about to serialise, BEFORE yielding —
            # the event dict may be a live reference (the in-memory repo hands back references)
            # that a later write mutates, and the stream must end on the state it actually sent.
            is_terminal = str(event.get("status")) in _TERMINAL
            yield _sse(event)
            if is_terminal:
                return
    finally:
        events.unsubscribe(job_id, queue)


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str, user: CurrentUser = Depends(get_current_user)):
    """Server-Sent Events stream of a job's progress — the push replacement for polling.

    Each event's ``data`` is a job snapshot in the same shape as ``GET /jobs/{job_id}``, so
    the client just replaces its job state on each one; the stream ends on a terminal status.
    Auth is the ordinary Bearer dependency (the client consumes this with ``fetch``, which —
    unlike ``EventSource`` — can send the Authorization header), so the same per-user scoping
    applies: a stream is only ever opened for the caller's own job.

    Because the worker only pushes when generation runs **inline** (the deployed mode), a job
    with no live task simply streams its snapshot and closes, leaving the client to fall back
    to polling. No update is lost silently — the snapshot plus the terminal event bracket it.
    """
    from fastapi.responses import StreamingResponse

    if not get_repo().get_job(user.uid, job_id):
        raise HTTPException(404, "Not found")

    return StreamingResponse(
        job_event_stream(user.uid, job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # tell any nginx-style proxy not to buffer the stream
        },
    )
