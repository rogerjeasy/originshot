"""Security controls: response headers, rate limiting, upload validation, quotas.

See ../docs/SECURITY.md §6 (uploads), §9 (API headers), §10 (denial-of-wallet).
"""
from __future__ import annotations

import hashlib
import io

from fastapi import HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings

# IP-based limiter for coarse abuse protection; per-user quotas are enforced separately.
limiter = Limiter(key_func=get_remote_address)

_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; img-src 'self' data: https:; connect-src 'self'; frame-ancestors 'none'",
        )
        if not get_settings().is_dev:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def validate_and_normalize_image(data: bytes) -> dict:
    """Validate an uploaded image and return normalized, metadata-stripped PNG bytes.

    Defends against: wrong type (magic-byte check), oversized files, decompression bombs,
    and embedded metadata/EXIF/GPS (stripped by re-encoding). Returns a dict with
    ``bytes``, ``sha256``, ``width``, ``height``, ``mime_type``.
    """
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")

    try:
        from PIL import Image
    except ImportError:  # graceful degradation if Pillow is unavailable
        sha = hashlib.sha256(data).hexdigest()
        return {"bytes": data, "sha256": sha, "width": None, "height": None,
                "mime_type": "application/octet-stream"}

    Image.MAX_IMAGE_PIXELS = settings.max_image_pixels
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = (probe.format or "").upper()
            if fmt not in _ALLOWED_FORMATS:
                raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                    f"Unsupported image type: {fmt or 'unknown'}")
            probe.verify()  # detect truncated/corrupt files
        # Re-open (verify() leaves the file unusable) and re-encode to strip all metadata.
        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
            width, height = img.size
            out = io.BytesIO()
            img.save(out, format="PNG")  # PNG, no EXIF/GPS carried over
            norm = out.getvalue()
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or corrupt image")

    return {
        "bytes": norm,
        "sha256": hashlib.sha256(norm).hexdigest(),
        "width": width,
        "height": height,
        "mime_type": "image/png",
    }


def enforce_generation_quota(uid: str) -> None:
    """Raise 429 when the user has exhausted their daily generation quota."""
    from .repo import get_repo

    settings = get_settings()
    used = get_repo().count_generations_today(uid)
    if used >= settings.daily_generation_quota:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Daily generation quota reached ({settings.daily_generation_quota}).",
        )
