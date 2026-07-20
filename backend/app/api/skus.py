"""SKU (product) endpoints — all scoped to the authenticated user.

Read/create are strictly per-user (the repo is uid-scoped, so a caller only ever sees their
own SKUs). Update and delete additionally allow an **admin** to act on anyone's SKU, for
moderation and cleanup — and a non-owner who isn't an admin gets a 404, not a 403, so the
endpoint never even confirms that someone else's SKU exists.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from ..admin import is_admin
from ..auth import CurrentUser, get_current_user
from ..models import AssetOut, SkuCreate, SkuOut, SkuUpdate
from ..repo import get_repo
from ..storage import get_storage
from ..util import with_presigned_url

log = logging.getLogger("originshot.skus")

router = APIRouter(prefix="/skus", tags=["skus"])


def _resolve_for_write(sku_id: str, user: CurrentUser) -> tuple[str, dict]:
    """Resolve a SKU the caller is allowed to modify, or raise 404.

    Returns ``(owner_uid, sku)``. The owner reaches their own SKU through the uid-scoped repo;
    an admin resolves any SKU globally. Anyone else — including an authenticated user pointing
    at a stranger's SKU — gets a 404 rather than a 403, so existence is never leaked to a
    non-owner. The returned `owner_uid` is what the mutation is scoped to, so an admin edit
    lands on the real owner's record, not the admin's namespace.
    """
    repo = get_repo()
    sku = repo.get_sku(user.uid, sku_id)
    if sku:
        return user.uid, sku
    if is_admin(user):
        found = repo.find_sku_by_id(sku_id)
        if found:
            return found
    raise HTTPException(404, "Not found")


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


@router.patch("/{sku_id}", response_model=SkuOut)
def update_sku(sku_id: str, body: SkuUpdate, user: CurrentUser = Depends(get_current_user)):
    """Edit a SKU's title/category/description. Owner or admin only.

    Partial: only supplied fields change. `None`/omitted fields are left untouched (so an
    edit can't null out `title`, which `SkuOut` requires — clear a field by sending "").
    """
    owner_uid, _ = _resolve_for_write(sku_id, user)
    patch = body.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(400, "No fields to update")
    updated = get_repo().update_sku(owner_uid, sku_id, patch)
    if not updated:  # lost a race with a concurrent delete
        raise HTTPException(404, "Not found")
    return updated


@router.delete("/{sku_id}")
def delete_sku(sku_id: str, user: CurrentUser = Depends(get_current_user)):
    """Delete a SKU, its assets, and their global index entries. Owner or admin only.

    The Firestore removal is the authoritative delete. Transparency-log entries are NOT
    touched — the ledger is append-only, and a deleted asset's provenance record staying in
    it is correct (it records that the file *was* made; deleting the file doesn't unmake that
    history). B2 media cleanup is best-effort and guarded against the content-addressable
    dedup case, so shared bytes another SKU still points at are never pulled out from under it.
    """
    owner_uid, _ = _resolve_for_write(sku_id, user)
    repo = get_repo()
    removed = repo.delete_sku(owner_uid, sku_id)

    storage = get_storage()
    media_deleted = 0
    for asset in removed:
        # Per-asset manifest sidecar: not content-addressed, so nothing else references it.
        _safe_delete(storage, asset.get("manifest_key"))
        # Embedded media lives under a content-addressed key; only delete the object once no
        # remaining asset resolves to that hash (the index entry was already dropped above).
        sha, key = asset.get("sha256"), asset.get("b2_key")
        if key and (sha is None or repo.find_asset_by_sha(sha) is None):
            if _safe_delete(storage, key):
                media_deleted += 1

    log.info("deleted sku %s (owner %s): %d assets, %d media objects",
             sku_id, owner_uid, len(removed), media_deleted)
    return {"id": sku_id, "assets_removed": len(removed), "media_objects_deleted": media_deleted}


def _safe_delete(storage, key: str | None) -> bool:
    """Best-effort object delete. A storage failure must not fail an already-committed delete."""
    if not key:
        return False
    try:
        storage.delete(key)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("media cleanup failed for %s: %s", key, exc)
        return False


@router.get("/{sku_id}/assets", response_model=list[AssetOut])
def list_assets(sku_id: str, user: CurrentUser = Depends(get_current_user)):
    repo = get_repo()
    if not repo.get_sku(user.uid, sku_id):
        raise HTTPException(404, "Not found")
    return [with_presigned_url(a) for a in repo.list_assets(user.uid, sku_id)]
