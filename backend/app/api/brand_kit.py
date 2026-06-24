"""Brand kit endpoints — per-user style guidance injected into generation prompts."""
from fastapi import APIRouter, Depends

from ..auth import CurrentUser, get_current_user, require_verified_email
from ..models import BrandKit
from ..repo import get_repo

router = APIRouter(prefix="/brand-kit", tags=["brand-kit"])


@router.get("", response_model=BrandKit)
def get_brand_kit(user: CurrentUser = Depends(get_current_user)):
    return get_repo().get_brand_kit(user.uid) or BrandKit().model_dump()


@router.put("", response_model=BrandKit)
def put_brand_kit(body: BrandKit, user: CurrentUser = Depends(require_verified_email)):
    return get_repo().set_brand_kit(user.uid, body.model_dump())
