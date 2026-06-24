"""Export — assemble a per-SKU pack with per-marketplace format targets.

MVP returns JSON; a stretch goal renders a marketplace-formatted ZIP (BUILD_PLAN §5/§18).
"""
from fastapi import APIRouter, Depends, HTTPException

from listsnap_pipelines.presets import preset_targets

from ..auth import CurrentUser, require_verified_email
from ..models import ExportRequest
from ..repo import get_repo
from ..storage import get_storage
from ..util import disclosure

router = APIRouter(tags=["export"])


@router.post("/skus/{sku_id}/export")
def export_pack(
    sku_id: str,
    body: ExportRequest | None = None,
    user: CurrentUser = Depends(require_verified_email),
):
    repo = get_repo()
    sku = repo.get_sku(user.uid, sku_id)
    if not sku:
        raise HTTPException(404, "Not found")

    storage = get_storage()
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
                "url": storage.presigned_get(a["b2_key"]) if a.get("b2_key") else a.get("b2_url"),
                "disclosure": disclosure(a),
            }
            for a in assets
        ],
    }
