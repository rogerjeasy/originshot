"""Genblaze storage sink → Backblaze B2 (content-addressable + Parquet analytics).

✅ WEEK-1 VERIFIED (genblaze-core 0.3.2, genblaze-s3 0.3.2):
  * `ObjectStorageSink(backend, *, prefix, key_strategy, parquet_sink, ...)` — there is
    **no** `embed_policy` kwarg (embedding is done explicitly post-run; see provenance.py).
  * `S3StorageBackend.for_backblaze(bucket, *, region, key_id, app_key, ...)` — pass B2
    credentials explicitly rather than relying on ambient AWS env vars.
  * `ParquetSink(base_dir, *, policy=None)` requires the optional `pyarrow` dependency
    (`pip install 'genblaze[parquet]'` or our `analytics` extra). It is wired in only when
    pyarrow is importable so the sink still works without the analytics stack.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("listsnap.pipelines.storage")


def _parquet_sink():
    """Return a ParquetSink if pyarrow is available and the dir is writable, else None.

    The directory comes from PARQUET_DIR (default ``data/``, relative to the working dir).
    Analytics are a nice-to-have, so an unwritable path degrades to None rather than
    failing the whole generation run — in the container /app is root-owned and we run as
    appuser, so this would otherwise raise PermissionError.
    """
    try:
        import pyarrow  # noqa: F401
    except Exception:  # noqa: BLE001
        return None
    from genblaze_core import ParquetSink

    base_dir = os.environ.get("PARQUET_DIR", "data/")
    try:
        return ParquetSink(base_dir)
    except OSError as exc:
        log.warning("Parquet analytics disabled — %s is not writable (%s).", base_dir, exc)
        return None


def make_sink():
    """Build an ObjectStorageSink backed by Backblaze B2.

    CONTENT_ADDRESSABLE → dedup (the cost story). ParquetSink → analytics export (optional).
    """
    from genblaze_core import KeyStrategy, ObjectStorageSink
    from genblaze_s3 import S3StorageBackend

    backend = S3StorageBackend.for_backblaze(
        os.environ["B2_BUCKET"],
        region=os.environ.get("B2_REGION"),
        key_id=os.environ.get("B2_KEY_ID"),
        app_key=os.environ.get("B2_APP_KEY"),
    )
    return ObjectStorageSink(
        backend,
        prefix="assets",
        key_strategy=KeyStrategy.CONTENT_ADDRESSABLE,
        parquet_sink=_parquet_sink(),
    )
