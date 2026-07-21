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
from . import pricing
from .pricing import eta_seconds
from .repo import get_repo
from .storage import get_storage

log = logging.getLogger("originshot.worker")


class _JobStepReporter(StepReporter):
    """Persists step transitions — and each step's assets — as the run advances.

    Holds the step list in memory and rewrites the whole array on each event. The array is
    small (≤5 entries) and this avoids a read-modify-write race against the worker's own
    status updates — this object is the sole writer of `steps` for its job.

    Progress reporting is cosmetic and every reporting path swallows its own exceptions:
    losing a UI update must never fail a run the provider has already been paid for.
    **Asset persistence is not cosmetic**, so it is handled separately — per-asset failures
    are collected in `persist_errors` and surfaced on the job rather than silently dropped.

    Assets are written when their style finishes rather than when the whole job does. A pack
    with a video step takes minutes; waiting for the last one to land before showing the
    first is the difference between watching a product work and watching a spinner. The
    client already reloads its grid whenever the completed-step count moves, so the write
    has to happen *before* the step flips to `done` — see `finish`.
    """

    def __init__(self, uid: str, job_id: str, styles: list[str]) -> None:
        self._uid = uid
        self._job_id = job_id
        self.asset_ids: list[str] = []
        self.persist_errors: list[str] = []
        # Provider spend accumulated per completed step. Tracked here because assets are now
        # durable before the job ends: if the run dies afterwards, the work was still billed,
        # and settling as if nothing happened would hand out those assets for free.
        self.cost_total: float = 0.0
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
        job = None
        try:
            # update_job returns the full, updated job document — reused below as the stream
            # event so every push is a complete snapshot (no partial-shape special case).
            job = get_repo().update_job(self._uid, self._job_id, {
                "steps": [self._steps[k] for k in self._order],
            })
        except Exception as exc:  # noqa: BLE001
            log.warning("step flush failed for job %s: %s", self._job_id, exc)
        # Push the same progress to any live /stream subscriber the instant it changes, so the
        # studio updates without polling. Best-effort: a lost push must never fail a run, and
        # each event is a full snapshot so a dropped one self-heals from the next.
        if job is not None:
            try:
                from . import events

                events.publish(self._job_id, job)
            except Exception:  # noqa: BLE001
                pass

    def _patch(self, style: Style, **fields) -> None:
        step = self._steps.get(style.value)
        if step is None:
            return
        step.update(fields)
        self._flush()

    def start(self, style: Style) -> None:
        self._patch(style, status=StepStatus.running.value, started_at=utcnow())

    def _persist(self, assets: list[dict]) -> None:
        """Write this step's assets, so they are readable the moment the step reads `done`.

        Ordering matters: the client reloads its grid on seeing a step complete, so a write
        that happened after the status flip would be raced and the grid would come back
        empty. One failure does not abort the rest — the pack's per-style isolation applies
        to storage too — but it is recorded so the job reports `partial` instead of `done`.
        """
        from . import transparency

        repo = get_repo()
        for asset in assets:
            try:
                stored = repo.add_asset(self._uid, asset)
                self.asset_ids.append(stored["id"])
                transparency.record_asset(stored)
            except Exception as exc:  # noqa: BLE001
                log.exception("asset persist failed for job %s", self._job_id)
                self.persist_errors.append(f"{asset.get('style', 'asset')}: not saved ({exc})")

    def finish(self, style: Style, assets: list[dict]) -> None:
        self._persist(assets)
        step = self._steps.get(style.value) or {}
        started = step.get("started_at")
        # Provider/model/cost come from the assets the step produced — they're only known
        # after the call returns, which is the whole reason these are reported per step.
        first = assets[0] if assets else {}
        # Falls back to list price for providers whose SDK reports no cost (OpenAI) — an
        # unpriced step is unpriced, not free. See pricing.billable_cost.
        cost, cost_source = pricing.billable_cost(assets)
        self.cost_total += cost
        # QA rollup: only over assets that actually carry a report — no report, no claim.
        reports = [a["qa"] for a in assets if a.get("qa")]
        self._patch(
            style,
            status=StepStatus.done.value,
            finished_at=utcnow(),
            duration_ms=_elapsed_ms(started),
            provider=first.get("provider"),
            model=first.get("model"),
            cost_usd=round(cost, 4) if cost else None,
            cost_source=cost_source,
            asset_count=len(assets),
            qa_passed=all(r.get("passed") for r in reports) if reports else None,
            qa_attempts=max(
                (r.get("attempts") or r.get("attempt") or 1) for r in reports
            ) if reports else None,
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


async def _run_job(uid: str, job_id: str, sku_id: str, styles: list[str], runner) -> None:
    """The job lifecycle shared by generation and replay.

    `runner(reporter, job) -> (assets, errors)` does the actual work; everything around it
    — status transitions, per-step asset bookkeeping, crash salvage, and exactly-once
    credit settlement — is identical for both, and keeping one copy is what keeps the
    settlement invariant single-sourced (the same argument batches.py makes for reusing
    submit_generation).
    """
    from . import credits

    repo = get_repo()
    reporter = _JobStepReporter(uid, job_id, styles)
    repo.update_job(uid, job_id, {
        "status": JobStatus.running.value,
        "started_at": utcnow(),
    })

    job = repo.get_job(uid, job_id) or {}
    held = float(job.get("credits_held") or 0.0)
    actual: float | None = None

    try:
        assets, errors = await runner(reporter, job)
        # Already written per step by the reporter, so the client could show them as they
        # landed. Reading the ids back from it keeps a single writer for assets.
        asset_ids = list(reporter.asset_ids)
        errors = errors + reporter.persist_errors

        if not asset_ids:
            status = JobStatus.failed
        elif errors:
            status = JobStatus.partial
        else:
            status = JobStatus.done

        # Per-step provider cost (Step.cost_usd, surfaced by generation._map), with list
        # price substituted for providers that report none — see pricing.billable_cost.
        # `cost_source` travels with the number so the UI and analytics can say whether the
        # figure is a provider's bill or our estimate, instead of implying the former.
        actual, cost_source = pricing.billable_cost(assets)
        patch = {
            "status": status.value,
            "asset_ids": asset_ids,
            "cost_estimate": actual or None,
            "cost_actual": actual,
            "cost_source": cost_source,
            "finished_at": utcnow(),
        }
        if errors:
            patch["error"] = "; ".join(errors)[:500]
        repo.update_job(uid, job_id, patch)
        log.info("job %s %s: %d assets, %d errors", job_id, status.value, len(asset_ids), len(errors))
    except Exception as exc:  # noqa: BLE001
        log.exception("job %s failed", job_id)
        # Steps that completed before the crash already wrote their assets, and the provider
        # already billed for them. Settle against what was actually produced rather than
        # refunding the whole hold — and keep those assets attached to the job, because they
        # are real and the user can use them.
        salvaged = list(reporter.asset_ids)
        actual = round(reporter.cost_total, 4)
        repo.update_job(uid, job_id, {
            "status": (JobStatus.partial if salvaged else JobStatus.failed).value,
            "asset_ids": salvaged,
            "cost_actual": actual,
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
        # Push the final, settled job to any live subscriber — the event that tells the stream
        # to stop. Sent last so `cost_actual` and `credits_held` are already reconciled.
        try:
            from . import events

            final = repo.get_job(uid, job_id)
            if final:
                events.publish(job_id, final)
        except Exception:  # noqa: BLE001
            pass


def _require_sku_and_original(repo, uid: str, sku_id: str) -> tuple[dict, dict]:
    sku = repo.get_sku(uid, sku_id)
    if not sku:
        raise RuntimeError("SKU not found")
    original = next((a for a in repo.list_assets(uid, sku_id) if a.get("is_authentic")), None)
    if not original:
        raise RuntimeError("No authentic original uploaded for this SKU")
    return sku, original


async def process_generation(uid: str, job_id: str, sku_id: str, styles: list[str]) -> None:
    async def runner(reporter: _JobStepReporter, job: dict):
        repo = get_repo()
        sku, original = _require_sku_and_original(repo, uid, sku_id)
        return await generate_assets(
            uid, sku, original, styles, storage=get_storage(),
            brand=repo.get_brand_kit(uid), marketplaces=job.get("marketplaces") or [],
            reporter=reporter,
        )

    await _run_job(uid, job_id, sku_id, styles, runner)


async def process_replay(uid: str, job_id: str, sku_id: str, asset_id: str) -> None:
    """Replay one asset from its manifest as an ordinary job (see generation.replay_asset).

    The style list for the reporter comes from the job document — the submit path recorded
    the source asset's style there, and reading it back keeps this function free of a
    second lookup that could disagree with what was quoted and held.
    """
    from .generation import replay_asset

    repo = get_repo()
    job = repo.get_job(uid, job_id) or {}
    styles = [str(s) for s in job.get("requested_styles") or []]

    async def runner(reporter: _JobStepReporter, job: dict):
        sku, original = _require_sku_and_original(repo, uid, sku_id)
        source = next((a for a in repo.list_assets(uid, sku_id) if a.get("id") == asset_id), None)
        if not source:
            raise RuntimeError("Source asset not found")
        return await replay_asset(
            uid, sku, source, original, storage=get_storage(), reporter=reporter
        )

    await _run_job(uid, job_id, sku_id, styles, runner)


# ── Production Arq worker ──────────────────────────────────────────────
async def generate_task(ctx, uid: str, job_id: str, sku_id: str, styles: list[str]) -> None:
    await process_generation(uid, job_id, sku_id, styles)


async def replay_task(ctx, uid: str, job_id: str, sku_id: str, asset_id: str) -> None:
    await process_replay(uid, job_id, sku_id, asset_id)


class WorkerSettings:
    """Run with: `arq app.worker.WorkerSettings` (needs Redis + the [worker] extra)."""

    functions = [generate_task, replay_task]

    @staticmethod
    def redis_settings():
        from arq.connections import RedisSettings

        return RedisSettings.from_dsn(get_settings().redis_url)
