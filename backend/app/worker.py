"""Job execution.

`process_generation` is the single code path used by BOTH:
  * dev/inline execution via FastAPI BackgroundTasks (no Redis required), and
  * the production Arq worker (`arq app.worker.WorkerSettings`).

The actual generation (real Genblaze pipelines or the dev mock) lives in generation.py.

Two things happen here beyond running the pipeline:

  * **step persistence** — `_JobStepReporter` writes each style's start/finish onto the job
    document as it happens, so a polling client sees real progress instead of a spinner.
  * **credit settlement** — the estimated cost was held when the job was submitted
    (api/generate.py). Whatever happens below, that hold must be reconciled exactly once,
    which is why settlement lives in a `finally` and is itself exception-guarded: a job that
    crashes mid-run must not strand the user's credit.
"""
from __future__ import annotations

import logging

from .config import get_settings
from .generation import StepReporter, generate_assets
from .models import JobStatus, StepStatus, Style, utcnow
from .pricing import eta_seconds
from .repo import get_repo
from .storage import get_storage

log = logging.getLogger("originshot.worker")


class _JobStepReporter(StepReporter):
    """Persists step transitions onto the job document.

    Holds the step list in memory and rewrites the whole array on each event. The array is
    small (≤5 entries) and this avoids a read-modify-write race against the worker's own
    status updates — this object is the sole writer of `steps` for its job.

    Every method swallows its own exceptions: progress reporting is cosmetic, and losing a
    UI update must never fail a run the provider has already been paid for.
    """

    def __init__(self, uid: str, job_id: str, styles: list[str]) -> None:
        self._uid = uid
        self._job_id = job_id
        self._steps: dict[str, dict] = {}
        self._order: list[str] = []
        for s in styles:
            try:
                style = Style(s)
            except ValueError:
                continue
            self._order.append(style.value)
            self._steps[style.value] = {
                "style": style.value,
                "status": StepStatus.pending.value,
                "eta_seconds": eta_seconds([style]),
                "asset_count": 0,
            }
        self._flush()

    def _flush(self) -> None:
        try:
            get_repo().update_job(self._uid, self._job_id, {
                "steps": [self._steps[k] for k in self._order],
            })
        except Exception as exc:  # noqa: BLE001
            log.warning("step flush failed for job %s: %s", self._job_id, exc)

    def _patch(self, style: Style, **fields) -> None:
        step = self._steps.get(style.value)
        if step is None:
            return
        step.update(fields)
        self._flush()

    def start(self, style: Style) -> None:
        self._patch(style, status=StepStatus.running.value, started_at=utcnow())

    def finish(self, style: Style, assets: list[dict]) -> None:
        step = self._steps.get(style.value) or {}
        started = step.get("started_at")
        # Provider/model/cost come from the assets the step produced — they're only known
        # after the call returns, which is the whole reason these are reported per step.
        first = assets[0] if assets else {}
        cost = sum(c for a in assets if (c := a.get("cost_usd")) is not None)
        self._patch(
            style,
            status=StepStatus.done.value,
            finished_at=utcnow(),
            duration_ms=_elapsed_ms(started),
            provider=first.get("provider"),
            model=first.get("model"),
            cost_usd=round(cost, 4) if cost else None,
            asset_count=len(assets),
        )

    def fail(self, style: Style, error: str) -> None:
        step = self._steps.get(style.value) or {}
        self._patch(
            style,
            status=StepStatus.failed.value,
            finished_at=utcnow(),
            duration_ms=_elapsed_ms(step.get("started_at")),
            error=error[:300],
        )

    def skip(self, style: Style, reason: str) -> None:
        self._patch(style, status=StepStatus.skipped.value, error=reason[:300])


def _elapsed_ms(started) -> int | None:
    if not started:
        return None
    try:
        return max(0, int((utcnow() - started).total_seconds() * 1000))
    except TypeError:
        return None


async def process_generation(uid: str, job_id: str, sku_id: str, styles: list[str]) -> None:
    from . import credits

    repo = get_repo()
    storage = get_storage()
    reporter = _JobStepReporter(uid, job_id, styles)
    repo.update_job(uid, job_id, {
        "status": JobStatus.running.value,
        "started_at": utcnow(),
    })

    job = repo.get_job(uid, job_id) or {}
    held = float(job.get("credits_held") or 0.0)
    actual: float | None = None

    try:
        sku = repo.get_sku(uid, sku_id)
        if not sku:
            raise RuntimeError("SKU not found")
        original = next((a for a in repo.list_assets(uid, sku_id) if a.get("is_authentic")), None)
        if not original:
            raise RuntimeError("No authentic original uploaded for this SKU")

        marketplaces = job.get("marketplaces") or []
        brand = repo.get_brand_kit(uid)
        assets, errors = await generate_assets(
            uid, sku, original, styles, storage=storage, brand=brand,
            marketplaces=marketplaces, reporter=reporter,
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
        actual = round(cost, 4) if cost else 0.0
        patch = {
            "status": status.value,
            "asset_ids": asset_ids,
            "cost_estimate": actual or None,
            "cost_actual": actual,
            "finished_at": utcnow(),
        }
        if errors:
            patch["error"] = "; ".join(errors)[:500]
        repo.update_job(uid, job_id, patch)
        log.info("job %s %s: %d assets, %d errors", job_id, status.value, len(asset_ids), len(errors))
    except Exception as exc:  # noqa: BLE001
        log.exception("job %s failed", job_id)
        actual = 0.0  # nothing was produced ⇒ the whole hold is refunded below
        repo.update_job(uid, job_id, {
            "status": JobStatus.failed.value,
            "error": str(exc),
            "finished_at": utcnow(),
        })
    finally:
        # Reconcile exactly once, whatever happened above. Guarded so a settlement failure
        # is logged rather than replacing the job's real outcome with a ledger traceback.
        if held:
            try:
                credits.settle(uid, job_id=job_id, sku_id=sku_id, held=held, actual=actual)
                repo.update_job(uid, job_id, {"credits_held": 0.0})
            except Exception:  # noqa: BLE001
                log.exception("credit settlement failed for job %s (held $%.4f)", job_id, held)


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
