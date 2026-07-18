"""Generation endpoints — kick off a job and poll its status.

Dev runs the job inline via BackgroundTasks (no Redis needed). For production, switch the
`background.add_task(...)` line to an Arq enqueue (see app/worker.py WorkerSettings).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from ..auth import CurrentUser, get_current_user
from ..models import GenerateRequest, JobOut
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

    enforce_generation_quota(user.uid)  # denial-of-wallet protection

    styles = [s.value for s in body.styles]
    marketplaces = [m.value for m in body.marketplaces]
    job = repo.create_job(
        user.uid,
        {"sku_id": sku_id, "requested_styles": styles, "marketplaces": marketplaces},
    )
    await enqueue_generation(background, user.uid, job["id"], sku_id, styles)
    return job


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: CurrentUser = Depends(get_current_user)):
    job = get_repo().get_job(user.uid, job_id)
    if not job:
        raise HTTPException(404, "Not found")
    return job
