"""Catalog Mode — one run across many SKUs.

The product this app describes is "a 150-SKU shop that can't afford $25–150 per product",
but until now it generated one product at a time. This module is the fan-out: N SKUs, a
bounded number in flight at once, one live board, one bulk download.

**Each SKU is still an ordinary job.** A batch does not invent a second generation path — it
submits the same job the single-SKU button submits (`api/generate.submit_generation`), so
credit holds, settlement, per-style isolation, QA retries and provenance all behave
identically whether a photo was run alone or as item 47 of a catalog. The batch adds exactly
three things on top: concurrency control, per-item bookkeeping, and honest partial results.

**Why a per-item hold rather than one big batch hold.** A single hold for the whole catalog
would have to be reconciled against N settlements, and any crash between them would strand
credit no operator could reason about. Holding per job keeps the ledger's existing
hold/settle invariant exactly as it is: one hold, one settlement, one job.

**Why `blocked` is not `failed`.** A catalog can run out of balance or daily quota halfway
through. Those items never started and cost nothing, so they are reported as blocked and are
trivially re-runnable — telling a seller their photos *failed* when they simply ran out of
credit is a lie that generates a support ticket.
"""
from __future__ import annotations

import asyncio
import logging

from .config import get_settings
from .models import BatchItemStatus, BatchStatus, JobStatus, utcnow
from .repo import get_repo

log = logging.getLogger("originshot.batches")

# Terminal job states, mapped onto the item states the board renders.
_JOB_TO_ITEM = {
    JobStatus.done.value: BatchItemStatus.done,
    JobStatus.partial.value: BatchItemStatus.partial,
    JobStatus.failed.value: BatchItemStatus.failed,
}


class _BatchBoard:
    """Owns the batch document's `items` array and is its sole writer.

    Items complete concurrently, so every mutation goes through one lock and rewrites the
    whole (small) array — the same read-modify-write avoidance the per-job step reporter
    uses, for the same reason. Flush failures are logged, never raised: losing a progress
    update must not fail a run the provider has already been paid for.
    """

    def __init__(self, uid: str, batch_id: str, items: list[dict]) -> None:
        self._uid = uid
        self._batch_id = batch_id
        self._items = items
        self._lock = asyncio.Lock()

    @property
    def items(self) -> list[dict]:
        return self._items

    async def set(self, index: int, **fields) -> None:
        async with self._lock:
            self._items[index].update(fields)
            try:
                get_repo().update_batch(self._uid, self._batch_id, {"items": self._items})
            except Exception as exc:  # noqa: BLE001
                log.warning("batch %s flush failed: %s", self._batch_id, exc)


def concurrency_for(count: int) -> int:
    """How many SKUs to run at once.

    Bounded deliberately low. Generation is I/O-bound on the provider, so more parallelism
    buys wall-clock time cheaply — but each in-flight job also holds decoded image bytes for
    QA scoring in the same web process, and the deployment target is a 512 MB free-tier
    instance. Two is a throughput win that stays inside that envelope; the ceiling exists so
    a 100-SKU catalog can't turn into 100 simultaneous provider calls and a rate-limit ban.
    """
    return max(1, min(get_settings().catalog_concurrency, count))


async def process_batch(uid: str, batch_id: str) -> None:
    """Run every SKU in the batch, at most `concurrency` at a time."""
    from .api.generate import submit_generation
    from .credits import InsufficientCredit
    from .worker import process_generation

    repo = get_repo()
    batch = repo.get_batch(uid, batch_id)
    if not batch:
        log.warning("batch %s vanished before it started", batch_id)
        return

    styles = list(batch.get("styles") or [])
    marketplaces = list(batch.get("marketplaces") or [])
    board = _BatchBoard(uid, batch_id, list(batch.get("items") or []))
    limit = int(batch.get("concurrency") or 1)
    sem = asyncio.Semaphore(limit)

    repo.update_batch(uid, batch_id, {
        "status": BatchStatus.running.value,
        "started_at": utcnow(),
    })

    async def run_item(index: int, item: dict) -> None:
        sku_id = item["sku_id"]
        async with sem:
            sku = repo.get_sku(uid, sku_id)
            if not sku or not sku.get("original_sha256"):
                await board.set(index, status=BatchItemStatus.failed.value,
                                error="no product photo on this SKU")
                return

            # Quota is re-checked per item, not once up front: a long catalog can cross the
            # daily line partway through, and the honest response is to stop starting new
            # work rather than to have waved the whole run through at submit time.
            settings = get_settings()
            if repo.count_generations_today(uid) >= settings.daily_generation_quota:
                await board.set(index, status=BatchItemStatus.blocked.value,
                                error="daily generation quota reached")
                return

            try:
                job = submit_generation(uid, sku, sku_id, styles, marketplaces)
            except InsufficientCredit as exc:
                await board.set(index, status=BatchItemStatus.blocked.value,
                                error=f"insufficient credit (needs ${exc.required:.2f})")
                return
            except Exception as exc:  # noqa: BLE001
                log.exception("batch %s: submit failed for %s", batch_id, sku_id)
                await board.set(index, status=BatchItemStatus.failed.value,
                                error=str(exc)[:200])
                return

            await board.set(index, status=BatchItemStatus.running.value,
                            job_id=job["id"])
            started = utcnow()
            try:
                await process_generation(uid, job["id"], sku_id, styles)
            except Exception as exc:  # noqa: BLE001 — one SKU must not end the catalog
                log.exception("batch %s: generation crashed for %s", batch_id, sku_id)
                await board.set(index, status=BatchItemStatus.failed.value,
                                error=str(exc)[:200])
                return

            # process_generation owns the job document (including settlement) — read the
            # outcome back rather than inferring it, so the board can never disagree with
            # the job a user opens from it.
            done = repo.get_job(uid, job["id"]) or {}
            await board.set(
                index,
                status=_JOB_TO_ITEM.get(done.get("status"), BatchItemStatus.failed).value,
                asset_count=len(done.get("asset_ids") or []),
                cost_actual=done.get("cost_actual"),
                duration_ms=max(0, int((utcnow() - started).total_seconds() * 1000)),
                error=(done.get("error") or None),
            )

    await asyncio.gather(*(run_item(i, item) for i, item in enumerate(board.items)))

    items = board.items
    produced = [i for i in items if i.get("status") in
                (BatchItemStatus.done.value, BatchItemStatus.partial.value)]
    clean = all(i.get("status") == BatchItemStatus.done.value for i in items)
    if not produced:
        status = BatchStatus.failed
    elif clean:
        status = BatchStatus.done
    else:
        status = BatchStatus.partial

    repo.update_batch(uid, batch_id, {
        "status": status.value,
        "finished_at": utcnow(),
        "cost_actual": round(sum(float(i.get("cost_actual") or 0.0) for i in items), 4),
    })
    log.info("batch %s %s: %d/%d SKUs produced assets",
             batch_id, status.value, len(produced), len(items))
