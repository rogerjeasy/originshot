"""Job execution.

`process_generation` is the single code path used by BOTH:
  * dev/inline execution via FastAPI BackgroundTasks (no Redis required), and
  * the production Arq worker (`arq app.worker.WorkerSettings`).

The actual generation (real Genblaze pipelines or the dev mock) lives in generation.py.
"""
from __future__ import annotations

import logging

from .config import get_settings
from .generation import generate_assets
from .models import JobStatus, utcnow
from .repo import get_repo
from .storage import get_storage

log = logging.getLogger("originshot.worker")


async def process_generation(uid: str, job_id: str, sku_id: str, styles: list[str]) -> None:
    repo = get_repo()
    storage = get_storage()
    repo.update_job(uid, job_id, {"status": JobStatus.running.value})
    try:
        sku = repo.get_sku(uid, sku_id)
        if not sku:
            raise RuntimeError("SKU not found")
        original = next((a for a in repo.list_assets(uid, sku_id) if a.get("is_authentic")), None)
        if not original:
            raise RuntimeError("No authentic original uploaded for this SKU")

        job = repo.get_job(uid, job_id) or {}
        marketplaces = job.get("marketplaces") or []
        brand = repo.get_brand_kit(uid)
        assets, errors = await generate_assets(
            uid, sku, original, styles, storage=storage, brand=brand, marketplaces=marketplaces
        )
        asset_ids = [repo.add_asset(uid, a)["id"] for a in assets]

        if not assets:
            status = JobStatus.failed
        elif errors:
            status = JobStatus.partial
        else:
            status = JobStatus.done

        # Sum the per-step provider cost (Step.cost_usd, surfaced by generation._map).
        cost = sum(c for a in assets if (c := a.get("cost_usd")) is not None)
        patch = {
            "status": status.value,
            "asset_ids": asset_ids,
            "cost_estimate": round(cost, 4) if cost else None,
            "finished_at": utcnow(),
        }
        if errors:
            patch["error"] = "; ".join(errors)[:500]
        repo.update_job(uid, job_id, patch)
        log.info("job %s %s: %d assets, %d errors", job_id, status.value, len(asset_ids), len(errors))
    except Exception as exc:  # noqa: BLE001
        log.exception("job %s failed", job_id)
        repo.update_job(uid, job_id, {
            "status": JobStatus.failed.value,
            "error": str(exc),
            "finished_at": utcnow(),
        })


# ── Production Arq worker ──────────────────────────────────────────────
async def generate_task(ctx, uid: str, job_id: str, sku_id: str, styles: list[str]) -> None:
    await process_generation(uid, job_id, sku_id, styles)


class WorkerSettings:
    """Run with: `arq app.worker.WorkerSettings` (needs Redis + the [worker] extra)."""

    functions = [generate_task]

    @staticmethod
    def redis_settings():
        from arq.connections import RedisSettings

        return RedisSettings.from_dsn(get_settings().redis_url)
