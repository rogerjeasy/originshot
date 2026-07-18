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

    # Fail before creating a job or holding credit: if generation can't run, there is
    # nothing to queue and nothing to charge for.
    missing = missing_generation_requirements()
    if missing and generation_mode() == "unconfigured":
        raise HTTPException(
            503,
            "Image generation is currently unavailable — the service is missing: "
            + ", ".join(missing),
        )

    enforce_generation_quota(user.uid)  # denial-of-wallet protection: caps request volume

    # A user's first authenticated call isn't necessarily /me — generating straight after
    # sign-up must not 402 on a welcome credit that was never issued. Idempotent.
    credits.ensure_signup_grant(user.uid)

    styles = [s.value for s in body.styles]
    marketplaces = [m.value for m in body.marketplaces]
    estimate = pricing.estimate_styles(body.styles)

    # Create the job first so the hold's ledger row can reference it — an orphaned hold with
    # no job_id is exactly the kind of entry that makes a ledger unauditable.
    job = repo.create_job(user.uid, {
        "sku_id": sku_id,
        "requested_styles": styles,
        "marketplaces": marketplaces,
        "eta_seconds": pricing.eta_seconds(body.styles),
        "steps": [
            {"style": s, "status": StepStatus.pending.value,
             "eta_seconds": pricing.eta_seconds([s]), "asset_count": 0}
            for s in styles
        ],
    })

    # Caps *spend*, which the request-count quota above cannot: one video pack costs ~10x an
    # image pack. Raises 402 with the numbers when the balance won't cover the quote.
    try:
        credits.hold(user.uid, job_id=job["id"], sku_id=sku_id, amount=estimate)
    except Exception:
        # Don't leave a queued job behind for a run that will never start.
        repo.update_job(user.uid, job["id"], {
            "status": "failed", "error": "Insufficient credit", "finished_at": None,
        })
        raise
    repo.update_job(user.uid, job["id"], {"credits_held": estimate})

    await enqueue_generation(background, user.uid, job["id"], sku_id, styles)
    return repo.get_job(user.uid, job["id"]) or job


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: CurrentUser = Depends(get_current_user)):
    job = get_repo().get_job(user.uid, job_id)
    if not job:
        raise HTTPException(404, "Not found")
    return job
