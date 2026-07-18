"""Marketplace readiness — the pre-export answer to "will my main image be accepted?".

Runs the SKU's main image (latest studio asset, else the authentic original) through the
same rendition code the export uses and measures the result against each channel's rules.
Same renderer, same checks as the shipped ZIP — a green check here is a statement about
the file the seller will actually upload.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from originshot_pipelines.compliance import studio_scorecard

from ..auth import CurrentUser, get_current_user
from ..models import ComplianceOut, Modality, Style
from ..repo import get_repo
from ..storage import get_storage

router = APIRouter(tags=["compliance"])


def _main_image(assets: list[dict]) -> dict | None:
    """Latest studio asset if one exists — that's the marketplace main image — else the
    authentic original, else any image."""
    images = [a for a in assets if a.get("modality") == Modality.image.value]
    studios = [a for a in images if a.get("style") == Style.studio.value]
    if studios:
        return max(studios, key=lambda a: str(a.get("created_at")))
    originals = [a for a in images if a.get("is_authentic")]
    return (originals or images or [None])[0]


@router.get("/skus/{sku_id}/compliance", response_model=ComplianceOut)
def compliance(sku_id: str, user: CurrentUser = Depends(get_current_user)):
    repo = get_repo()
    if not repo.get_sku(user.uid, sku_id):
        raise HTTPException(404, "Not found")

    asset = _main_image(repo.list_assets(user.uid, sku_id))
    if not asset or not asset.get("b2_key"):
        raise HTTPException(400, "Nothing to check — upload or generate an image first")

    try:
        master = get_storage().get_bytes(asset["b2_key"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, "Could not read the master image from storage") from exc

    return ComplianceOut(
        source_style=asset.get("style"),
        source_sha256=asset.get("sha256"),
        items=studio_scorecard(master),
    )
