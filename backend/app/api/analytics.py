"""Analytics — storage/dedup/cost overview for the authenticated user.

Cost is reported as two figures that must never be conflated (see app/pricing.py):
`actual_cost_usd` comes from the credit ledger — `credits.settle` writes the provider-billed
`Step.cost_usd` total into `credits_spent_total` transactionally when each job settles, so
that field IS the aggregation of real spend and needs no re-summation here. The list-price
`estimated_cost_usd` is kept alongside it, labeled, for context.

The fallback rate is likewise measured, not assumed: a finished step "fell back" exactly
when the model that ultimately served it is one of the registry's fallback models — the
primary would have been recorded otherwise. The dev mock records `passthrough`, which is in
neither list, so mock runs count as zero fallbacks rather than polluting the rate.
"""
from fastapi import APIRouter, Depends

from originshot_pipelines.registry import IMAGE_EDIT_FALLBACKS, VIDEO_FALLBACKS

from ..auth import CurrentUser, get_current_user
from ..models import AnalyticsOut, Modality, StepStatus
from ..pricing import IMAGE_UNIT_USD, VIDEO_UNIT_USD
from ..repo import get_repo

router = APIRouter(tags=["analytics"])

COST_SOURCE = (
    "actual_cost_usd: provider-billed Step.cost_usd, settled through the credit ledger; "
    "estimated_cost_usd: list prices per asset"
)

_FALLBACK_MODELS = frozenset(IMAGE_EDIT_FALLBACKS) | frozenset(VIDEO_FALLBACKS)


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

    estimate = round(images * IMAGE_UNIT_USD + videos * VIDEO_UNIT_USD, 2)
    profile = repo.get_user(user.uid) or {}
    actual = round(float(profile.get("credits_spent_total") or 0.0), 2)

    steps_done = 0
    steps_fell_back = 0
    for job in repo.list_jobs(user.uid):
        for step in job.get("steps") or []:
            if step.get("status") != StepStatus.done.value or not step.get("model"):
                continue
            steps_done += 1
            if step["model"] in _FALLBACK_MODELS:
                steps_fell_back += 1
    fallback_rate = round(steps_fell_back / steps_done * 100, 1) if steps_done else 0.0

    return AnalyticsOut(
        total_assets=total,
        unique_objects=unique,
        dedup_savings_pct=round(dedup, 1),
        images=images,
        videos=videos,
        actual_cost_usd=actual,
        estimated_cost_usd=estimate,
        cost_source=COST_SOURCE,
        provider_mix=provider_mix,
        fallback_rate=fallback_rate,
    )
