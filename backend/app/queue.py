"""Job dispatch — Arq (Redis) in production, inline BackgroundTasks otherwise."""
from __future__ import annotations

import logging

from fastapi import BackgroundTasks

from .config import get_settings
from .worker import process_generation, process_replay

log = logging.getLogger("originshot.queue")


async def _dispatch(background: BackgroundTasks, task_name: str, inline_fn, *args) -> str:
    """Enqueue on Arq when configured, else run inline. Returns the mode used."""
    settings = get_settings()
    if settings.job_queue.lower() == "arq":
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await pool.enqueue_job(task_name, *args)
            return "arq"
        except Exception as e:  # noqa: BLE001
            log.warning("arq enqueue failed (%s); falling back to inline", e)

    background.add_task(inline_fn, *args)
    return "inline"


async def enqueue_generation(
    background: BackgroundTasks, uid: str, job_id: str, sku_id: str, styles: list[str]
) -> str:
    """Dispatch a generation job."""
    return await _dispatch(
        background, "generate_task", process_generation, uid, job_id, sku_id, styles
    )


async def enqueue_replay(
    background: BackgroundTasks, uid: str, job_id: str, sku_id: str, asset_id: str
) -> str:
    """Dispatch a replay job (worker.process_replay)."""
    return await _dispatch(
        background, "replay_task", process_replay, uid, job_id, sku_id, asset_id
    )
