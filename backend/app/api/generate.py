"""Generation endpoints — kick off a job and poll its status.

Dev runs the job inline via BackgroundTasks (no Redis needed). For production, switch the
`background.add_task(...)` line to an Arq enqueue (see app/worker.py WorkerSettings).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from .. import credits, pricing
from ..auth import CurrentUser, get_current_user
from ..generation import generation_mode, missing_generation_requirements
from ..models import GenerateRequest, JobOut, StepStatus
from ..repo import get_repo
from ..queue import enqueue_generation
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


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: CurrentUser = Depends(get_current_user)):
    job = get_repo().get_job(user.uid, job_id)
    if not job:
        raise HTTPException(404, "Not found")
    return job
