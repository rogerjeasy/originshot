"""Small shared helpers for assembling API responses."""
from __future__ import annotations

from .storage import get_storage, key_from_url


def presigned_url_for(asset: dict) -> str | None:
    """Short-lived presigned URL for an asset's media.

    Prefers a real object key (presigned against our bucket). Assets written before the
    sink key was recorded only have the sink's unsigned URL, so recover the key from it —
    the bucket is private and the raw URL 403s. Falls back to the stored URL for objects
    that genuinely live elsewhere.
    """
    key = asset.get("b2_key") or key_from_url(asset.get("b2_url"))
    if key and not str(key).startswith("http"):
        return get_storage().presigned_get(key)
    return asset.get("b2_url") or key


def with_presigned_url(asset: dict) -> dict:
    """Copy of `asset` with a short-lived presigned `url` attached."""
    a = dict(asset)
    a["url"] = presigned_url_for(a)
    return a


def disclosure(asset: dict) -> str:
    """Human-readable AI-disclosure / authenticity statement for an asset."""
    if asset.get("is_authentic"):
        return "Authentic original — unedited upload. Provenance verifiable via ListSnap."
    model = asset.get("model") or "an AI model"
    provider = asset.get("provider") or "provider"
    parent = (asset.get("parent_sha256") or "")[:12]
    return (
        f"AI-generated image. Model: {model} ({provider}). "
        f"Derived from authentic source {parent}. Provenance verifiable via ListSnap."
    )
