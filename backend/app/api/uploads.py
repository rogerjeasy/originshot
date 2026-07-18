"""Upload endpoint — validates the image, anchors it as the authentic original."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..auth import CurrentUser, get_current_user
from ..models import AssetOut, Modality, Style
from ..repo import get_repo
from ..security import validate_and_normalize_image
from ..storage import get_storage, storage_key
from ..util import with_presigned_url

router = APIRouter(prefix="/skus", tags=["uploads"])


@router.post("/{sku_id}/upload", response_model=AssetOut, status_code=201)
async def upload_original(
    sku_id: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    repo = get_repo()
    if not repo.get_sku(user.uid, sku_id):
        raise HTTPException(404, "Not found")

    data = await file.read()
    norm = validate_and_normalize_image(data)  # type/size/bomb checks + EXIF strip

    key = storage_key(norm["sha256"], ".png")
    get_storage().put_bytes(key, norm["bytes"], "image/png")
    repo.set_sku_original(user.uid, sku_id, norm["sha256"])

    asset = repo.add_asset(user.uid, {
        "sku_id": sku_id,
        "sha256": norm["sha256"],
        "b2_key": key,
        "modality": Modality.image.value,
        "style": Style.original.value,
        "is_authentic": True,
        "parent_sha256": None,
        "run_id": None,
        "provider": None,
        "model": None,
        "manifest_key": None,
        "mime_type": norm["mime_type"],
        "width": norm["width"],
        "height": norm["height"],
        "duration": None,
    })
    return with_presigned_url(asset)
