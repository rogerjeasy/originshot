"""Listing copy — generate and fetch per-marketplace copy for a SKU.

POST runs one GMI chat completion (originshot_pipelines/listing.py) and stores the result
on the SKU document; GET returns what's stored. Generation needs the GMI key — without it
the endpoint refuses with an actionable 503 rather than fabricating copy, mirroring how
image generation refuses (generation.GenerationUnavailable). Transient provider failures
(the chat endpoint 429s under load) surface as 503 "try again", never as a broken SKU.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from originshot_pipelines import listing as listing_mod
from originshot_pipelines.registry import GMI_CHAT_BASE_URL, LISTING_MODEL

from ..auth import CurrentUser, get_current_user
from ..config import get_settings
from ..models import ListingOut, ListingRequest
from ..repo import get_repo

router = APIRouter(tags=["listing"])
log = logging.getLogger("originshot.listing")


@router.get("/skus/{sku_id}/listing", response_model=ListingOut | None)
def get_listing(sku_id: str, user: CurrentUser = Depends(get_current_user)):
    """Stored listing copy, or `null` when none has been generated yet.

    "Not generated yet" is the normal state of a SKU, not an error: a 404 here made the
    browser console log a failed request on every studio page load, which trains people to
    ignore red lines in the console. A missing SKU is still a 404.
    """
    sku = get_repo().get_sku(user.uid, sku_id)
    if not sku:
        raise HTTPException(404, "Not found")
    return sku.get("listing")


@router.post("/skus/{sku_id}/listing", response_model=ListingOut)
def create_listing(sku_id: str, body: ListingRequest | None = None,
                   user: CurrentUser = Depends(get_current_user)):
    settings = get_settings()
    if not settings.gmi_api_key:
        raise HTTPException(503, "Listing copy needs a configured GMI_API_KEY")

    repo = get_repo()
    sku = repo.get_sku(user.uid, sku_id)
    if not sku:
        raise HTTPException(404, "Not found")

    marketplaces = [m.value for m in body.marketplaces] if body and body.marketplaces else []
    try:
        result = listing_mod.generate_listing(
            sku, repo.get_brand_kit(user.uid), marketplaces,
            api_key=settings.gmi_api_key,
            base_url=GMI_CHAT_BASE_URL,
            model=LISTING_MODEL,
        )
    except Exception as exc:  # noqa: BLE001 — transport/parse problems are retryable
        log.warning("listing generation failed for sku %s: %s", sku_id, exc)
        raise HTTPException(
            503, "The copy model is unavailable right now — try again in a moment."
        ) from exc

    repo.update_sku(user.uid, sku_id, {"listing": result})
    return result
