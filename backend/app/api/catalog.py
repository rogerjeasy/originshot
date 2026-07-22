"""Catalog Intelligence — search and integrity over the seller's own stored catalog.

Three authenticated reads (plus a reindex) over everything a seller has in B2:

  * `/library/similar` — visual near-neighbours by pHash (no model);
  * `/library/search`  — semantic search over the SKU text (OpenAI embeddings, degradable);
  * `/catalog/integrity` — reused-original + near-duplicate signals (no model);
  * `/catalog/reindex` — (re)embed the catalog and publish the vector index to B2.

All owner-scoped — this is the seller's view of their own shop — so nothing here presigns or
returns another user's media, the same isolation the Library holds.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import catalog_intel
from ..auth import CurrentUser, get_current_user
from ..models import (CatalogSearchOut, IntegrityOut, ReindexOut, SimilarAssetOut)
from ..util import with_presigned_url

router = APIRouter(tags=["catalog"])


@router.get("/library/similar", response_model=list[SimilarAssetOut])
def find_similar(
    sha256: str = Query(..., min_length=64, max_length=64, description="a hash you own"),
    limit: int = Query(default=24, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
):
    """The seller's other assets that look like one of theirs, nearest (lowest pHash distance)
    first. Runs on the perceptual hash already stored on every asset — no model call."""
    hits = catalog_intel.visual_similar(user.uid, sha256.strip().lower(), limit)
    # Presign only the rows actually being returned, exactly as the Library does. `phash_distance`
    # is already on each hit dict, so it flows through with_presigned_url into the model.
    return [SimilarAssetOut(**with_presigned_url(a)) for a in hits]


@router.get("/library/search", response_model=CatalogSearchOut)
def semantic_search(
    q: str = Query(..., min_length=1, max_length=200, description="free-text query"),
    limit: int = Query(default=24, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
):
    """Rank the seller's SKUs by meaning. Returns `available=false` (not an empty result) when
    semantic search is off, so the UI can prompt to configure it rather than imply an empty shop."""
    return CatalogSearchOut(**catalog_intel.semantic_search(user.uid, q.strip(), limit))


@router.get("/catalog/integrity", response_model=IntegrityOut)
def catalog_integrity(user: CurrentUser = Depends(get_current_user)):
    """Cross-catalog integrity signals: one real photo behind several 'distinct' listings, and
    near-duplicate source uploads across SKUs. Signals for review, never accusations."""
    return IntegrityOut(**catalog_intel.integrity(user.uid))


@router.post("/catalog/reindex", response_model=ReindexOut)
def reindex(user: CurrentUser = Depends(get_current_user)):
    """(Re)embed the catalog's text and publish the vector index to B2. Idempotent — SKUs whose
    text is unchanged since the last run are skipped."""
    return ReindexOut(**catalog_intel.reindex_user(user.uid))
