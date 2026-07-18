"""SKU (product) endpoints — all scoped to the authenticated user."""
from fastapi import APIRouter, Depends, HTTPException

from ..auth import CurrentUser, get_current_user
from ..models import AssetOut, SkuCreate, SkuOut
from ..repo import get_repo
from ..util import with_presigned_url

router = APIRouter(prefix="/skus", tags=["skus"])


@router.post("", response_model=SkuOut, status_code=201)
def create_sku(body: SkuCreate, user: CurrentUser = Depends(get_current_user)):
    return get_repo().create_sku(user.uid, body.model_dump())


@router.get("", response_model=list[SkuOut])
def list_skus(user: CurrentUser = Depends(get_current_user)):
    return get_repo().list_skus(user.uid)


@router.get("/{sku_id}", response_model=SkuOut)
def get_sku(sku_id: str, user: CurrentUser = Depends(get_current_user)):
    sku = get_repo().get_sku(user.uid, sku_id)
    if not sku:
        raise HTTPException(404, "Not found")
    return sku


@router.get("/{sku_id}/assets", response_model=list[AssetOut])
def list_assets(sku_id: str, user: CurrentUser = Depends(get_current_user)):
    repo = get_repo()
    if not repo.get_sku(user.uid, sku_id):
        raise HTTPException(404, "Not found")
    return [with_presigned_url(a) for a in repo.list_assets(user.uid, sku_id)]
