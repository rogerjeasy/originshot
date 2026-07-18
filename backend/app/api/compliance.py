"""Marketplace readiness — the pre-export answer to "will my main image be accepted?".

Runs the SKU's main image (latest studio asset, else the authentic original) through the
same rendition code the export uses and measures the result against each channel's rules.
Same renderer, same checks as the shipped ZIP — a green check here is a statement about
the file the seller will actually upload.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from originshot_pipelines.compliance import studio_scorecard

from ..auth import CurrentUser, get_current_user
from ..models import ComplianceOut, Modality, Style
from ..repo import get_repo
from ..storage import get_storage, key_from_url

router = APIRouter(tags=["compliance"])
log = logging.getLogger("originshot.compliance")


def _asset_key(asset: dict) -> str | None:
    """Storage key for an asset, or None when only an off-bucket URL is known.

    Mirrors app/api/export.py deliberately. Assets generated before manifest embedding was
    wired carry ONLY a sink `b2_url` and no `b2_key`, so reading `b2_key` alone refuses
    perfectly readable images — which is exactly how this endpoint used to 400 on SKUs
    whose studio page rendered fine.
    """
    key = asset.get("b2_key") or key_from_url(asset.get("b2_url"))
    return key if key and not str(key).startswith("http") else None


def _candidates(assets: list[dict]) -> list[dict]:
    """Main-image candidates, best first.

    The newest studio shot is the marketplace main image, so it leads; the authentic
    original is the honest fallback (the response reports which one was measured). Ordered
    rather than chosen outright so an unreadable best candidate falls through to the next
    instead of failing the whole check.
    """
    images = [a for a in assets if a.get("modality") == Modality.image.value]
    studios = sorted(
        (a for a in images if a.get("style") == Style.studio.value),
        key=lambda a: str(a.get("created_at")), reverse=True,
    )
    originals = [a for a in images if a.get("is_authentic")]

    ordered: list[dict] = []
    seen: set[str] = set()
    for asset in [*studios, *originals, *images]:
        key = str(asset.get("id") or id(asset))
        if key not in seen:
            seen.add(key)
            ordered.append(asset)
    return ordered


@router.get("/skus/{sku_id}/compliance", response_model=ComplianceOut)
def compliance(sku_id: str, user: CurrentUser = Depends(get_current_user)):
    repo = get_repo()
    if not repo.get_sku(user.uid, sku_id):
        raise HTTPException(404, "Not found")

    storage = get_storage()
    for asset in _candidates(repo.list_assets(user.uid, sku_id)):
        key = _asset_key(asset)
        if not key:
            continue
        try:
            master = storage.get_bytes(key)
        except Exception as exc:  # noqa: BLE001 — try the next candidate, don't fail the check
            log.warning("compliance: could not read %s (%s)", key, exc)
            continue
        return ComplianceOut(
            source_style=asset.get("style"),
            source_sha256=asset.get("sha256"),
            items=studio_scorecard(master),
        )

    raise HTTPException(400, "Nothing to check — upload or generate an image first")
