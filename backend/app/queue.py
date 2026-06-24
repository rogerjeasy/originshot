"""Job dispatch — Arq (Redis) in production, inline BackgroundTasks otherwise."""
from __future__ import annotations

import logging

from fastapi import BackgroundTasks

from .config import get_settings
from .worker import process_generation

log = logging.getLogger("listsnap.queue")


async def enqueue_generation(
    background: BackgroundTasks, uid: str, job_id: str, sku_id: str, styles: list[str]
) -> str:
    """Dispatch a generation job. Returns the mode used ("arq" or "inline")."""
    settings = get_settings()
    if settings.job_queue.lower() == "arq":
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await pool.enqueue_job("generate_task", uid, job_id, sku_id, styles)
            return "arq"
        except Exception as e:  # noqa: BLE001
            log.warning("arq enqueue failed (%s); falling back to inline", e)

    background.add_task(process_generation, uid, job_id, sku_id, styles)
    return "inline"
