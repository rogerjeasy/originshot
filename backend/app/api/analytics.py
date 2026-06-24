"""Analytics — storage/dedup/cost overview for the authenticated user.

Dev computes from the repo. Production should read the Genblaze ParquetSink with DuckDB
(install the [analytics] extra) for richer, scalable metrics.
"""
from fastapi import APIRouter, Depends

from ..auth import CurrentUser, get_current_user
from ..models import AnalyticsOut, Modality
from ..repo import get_repo

router = APIRouter(tags=["analytics"])

# Rough per-asset cost estimate (USD) for the dev dashboard.
_IMAGE_COST = 0.04
_VIDEO_COST = 0.50


@router.get("/analytics", response_model=AnalyticsOut)
def analytics(user: CurrentUser = Depends(get_current_user)):
    repo = get_repo()
    assets = [a for s in repo.list_skus(user.uid) for a in repo.list_assets(user.uid, s["id"])]

    total = len(assets)
    unique = len({a["sha256"] for a in assets})
    dedup = (1 - unique / total) * 100 if total else 0.0
    images = sum(1 for a in assets if a.get("modality") == Modality.image.value)
    videos = sum(1 for a in assets if a.get("modality") == Modality.video.value)

    provider_mix: dict[str, int] = {}
    for a in assets:
        key = a.get("provider") or "original"
        provider_mix[key] = provider_mix.get(key, 0) + 1

    cost = round(images * _IMAGE_COST + videos * _VIDEO_COST, 2)

    return AnalyticsOut(
        total_assets=total,
        unique_objects=unique,
        dedup_savings_pct=round(dedup, 1),
        images=images,
        videos=videos,
        estimated_cost_usd=cost,
        provider_mix=provider_mix,
        fallback_rate=0.0,
    )
