"""Object storage abstraction.

  * B2Storage    — Backblaze B2 (S3-compatible) via boto3; private bucket, short-lived
                   presigned GET URLs only (never public). See ../docs/SECURITY.md §8.
  * LocalStorage — dev fallback; writes under .devdata/media and serves via /media.

Keys are content-addressable: assets/<sha[:2]>/<sha[2:4]>/<sha><ext>  → dedup for free.
"""
from __future__ import annotations

from pathlib import Path

from .config import get_settings


def storage_key(sha256: str, ext: str) -> str:
    ext = ext if ext.startswith(".") else f".{ext}"
    return f"assets/{sha256[:2]}/{sha256[2:4]}/{sha256}{ext}"


def key_from_url(url: str | None) -> str | None:
    """Recover an object key from a URL that points at our own B2 bucket.

    The Genblaze sink writes into the bucket we own but hands back a plain, unsigned URL.
    The bucket is private (SECURITY.md §8), so that URL 403s — recover the key so callers
    can presign it instead. Returns None for anything outside our bucket (or when B2 isn't
    configured), leaving the caller's existing fallback in charge.
    """
    from urllib.parse import unquote, urlparse

    settings = get_settings()
    bucket = settings.b2_bucket
    # Gate on full B2 config: without credentials get_storage() serves LocalStorage, which
    # would presign a B2 key into a bogus /media/ URL.
    if not url or not bucket or not settings.b2_configured:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None

    host = parsed.netloc.rsplit("@", 1)[-1].split(":")[0]
    path = unquote(parsed.path).lstrip("/")
    if host.startswith(f"{bucket}."):  # virtual-hosted style: <bucket>.s3.<region>...
        return path or None
    head, _, rest = path.partition("/")  # path style: s3.<region>.../<bucket>/<key>
    if head == bucket:
        return rest or None
    return None


class LocalStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.root = Path(__file__).resolve().parent.parent / ".devdata" / "media"
        self.root.mkdir(parents=True, exist_ok=True)
        self.base_url = settings.public_base_url.rstrip("/")

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def presigned_get(self, key: str) -> str:
        return f"{self.base_url}/media/{key}"

    def delete(self, key: str) -> None:
        path = self.root / key
        if path.exists():
            path.unlink()


class B2Storage:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            s = self._settings
            self._client = boto3.client(
                "s3",
                endpoint_url=s.b2_endpoint,
                aws_access_key_id=s.b2_key_id,
                aws_secret_access_key=s.b2_app_key,
                region_name=s.b2_region,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}
        self.client.put_object(Bucket=self._settings.b2_bucket, Key=key, Body=data, **extra)
        return key

    def presigned_get(self, key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._settings.b2_bucket, "Key": key},
            ExpiresIn=self._settings.presigned_url_ttl_seconds,
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self._settings.b2_bucket, Key=key)


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        _storage = B2Storage() if get_settings().b2_configured else LocalStorage()
    return _storage
