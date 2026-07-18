"""Export — assemble a per-SKU pack with per-marketplace format targets.

MVP returns JSON; a stretch goal renders a marketplace-formatted ZIP (BUILD_PLAN §5/§18).
"""
from fastapi import APIRouter, Depends, HTTPException

from originshot_pipelines.presets import preset_targets

from ..auth import CurrentUser, get_current_user
from ..models import ExportRequest
from ..repo import get_repo
from ..util import disclosure, presigned_url_for

router = APIRouter(tags=["export"])


@router.post("/skus/{sku_id}/export")
def export_pack(
    sku_id: str,
    body: ExportRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    repo = get_repo()
    sku = repo.get_sku(user.uid, sku_id)
    if not sku:
        raise HTTPException(404, "Not found")

    assets = repo.list_assets(user.uid, sku_id)
    marketplaces = [m.value for m in body.marketplaces] if body else []

    return {
        "sku_id": sku_id,
        "title": sku.get("title"),
        "count": len(assets),
        "presets": preset_targets(marketplaces),  # per-marketplace format targets
        "assets": [
            {
                "style": a.get("style"),
                "sha256": a.get("sha256"),
                "url": presigned_url_for(a),
                "disclosure": disclosure(a),
            }
            for a in assets
        ],
    }
