"""Small shared helpers for assembling API responses."""
from __future__ import annotations

from .storage import get_storage


def with_presigned_url(asset: dict) -> dict:
    """Attach a short-lived presigned URL.

    Prefers a real object key (presigned against our bucket); falls back to a durable URL
    stored by the Genblaze sink when no key is available.
    """
    a = dict(asset)
    key = a.get("b2_key")
    if key and not str(key).startswith("http"):
        a["url"] = get_storage().presigned_get(key)
    else:
        a["url"] = a.get("b2_url") or key
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
