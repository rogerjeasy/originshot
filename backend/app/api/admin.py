"""Admin API — platform-wide operational view.

Every route here is guarded by `require_admin` and reads across all users, which is the one
place in this codebase that deliberately breaks the owner-scoping rule the rest of the API
enforces (SECURITY.md §4). That exception is why the guard is a hard dependency on every
route rather than a check inside each handler — there is no path into this module that
skips it.

Aggregates are computed on read from the repo. At real scale these become maintained rollup
documents; the scan is honest and correct for the data volumes this app actually holds, and
`AdminOverviewOut.b2` reports whether its own numbers were truncated rather than pretending
to completeness.
"""
from __future__ import annotations

import logging
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import credits as credits_mod
from ..admin import require_admin
from ..auth import CurrentUser
from ..config import get_settings
from ..models import (
    AdminHealthOut,
    AdminJobRow,
    AdminOverviewOut,
    AdminUserRow,
    GrantRequest,
    JobStatus,
    LedgerEntryOut,
    Modality,
    ProviderBudgetOut,
    ProviderBudgetRequest,
    RolesRequest,
    ServiceCheck,
    utcnow,
)
from ..repo import get_repo

log = logging.getLogger("originshot.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_STARTED_AT = time.time()


def _duration_ms(job: dict) -> int | None:
    """Wall-clock time for a finished job. Prefers `started_at` (when the worker actually
    picked it up) over `created_at` so queue wait isn't reported as generation time."""
    start = job.get("started_at") or job.get("created_at")
    end = job.get("finished_at")
    if not start or not end:
        return None
    try:
        return max(0, int((end - start).total_seconds() * 1000))
    except TypeError:  # mixed tz-aware/naive from different stores
        return None


def _percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[idx]


@router.get("/overview", response_model=AdminOverviewOut)
def overview(user: CurrentUser = Depends(require_admin)):
    """Single-call platform snapshot: scale, reliability, spend, media, storage."""
    repo = get_repo()
    users = repo.list_users()
    skus = repo.list_all_skus()
    assets = repo.list_all_assets()
    jobs = repo.list_all_jobs(limit=1000)

    now = utcnow()
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)

    def _recent(rows: list[dict], field: str, since) -> int:
        count = 0
        for r in rows:
            ts = r.get(field)
            try:
                if ts and ts > since:
                    count += 1
            except TypeError:
                continue
        return count

    succeeded = sum(1 for j in jobs if j.get("status") == JobStatus.done.value)
    partial = sum(1 for j in jobs if j.get("status") == JobStatus.partial.value)
    failed = sum(1 for j in jobs if j.get("status") == JobStatus.failed.value)
    # A job still queued/running hasn't succeeded or failed yet — excluding it keeps the
    # rate from dipping every time a job is merely in flight.
    resolved = succeeded + partial + failed
    # Partial counts as a success: the user got a usable pack, just not every style.
    success_rate = ((succeeded + partial) / resolved * 100) if resolved else 100.0

    durations = [d for j in jobs if (d := _duration_ms(j)) is not None]

    total_assets = len(assets)
    unique = len({a.get("sha256") for a in assets if a.get("sha256")})
    dedup = (1 - unique / total_assets) * 100 if total_assets else 0.0
    embedded = sum(1 for a in assets if a.get("embedded"))
    generated = [a for a in assets if not a.get("is_authentic")]

    provider_mix: dict[str, int] = {}
    for a in assets:
        key = a.get("provider") or "original"
        provider_mix[key] = provider_mix.get(key, 0) + 1

    spend = round(sum(float(u.get("credits_spent_total") or 0.0) for u in users), 4)
    outstanding = round(sum(float(u.get("credits_balance") or 0.0) for u in users), 4)
    granted = round(sum(float(u.get("credits_granted_total") or 0.0) for u in users), 4)

    # Per-user counts, so the users table doesn't re-scan.
    sku_by_uid: dict[str, int] = {}
    for s in skus:
        sku_by_uid[s.get("owner_uid", "")] = sku_by_uid.get(s.get("owner_uid", ""), 0) + 1

    return AdminOverviewOut(
        users_total=len(users),
        users_active_7d=_recent(users, "updated_at", week_ago),
        skus_total=len(skus),
        assets_total=total_assets,
        jobs_total=len(jobs),
        jobs_succeeded=succeeded,
        jobs_partial=partial,
        jobs_failed=failed,
        success_rate_pct=round(success_rate, 1),
        p50_duration_ms=_percentile(durations, 50),
        p95_duration_ms=_percentile(durations, 95),
        spend_total_usd=spend,
        credits_outstanding_usd=outstanding,
        credits_granted_usd=granted,
        images=sum(1 for a in assets if a.get("modality") == Modality.image.value),
        videos=sum(1 for a in assets if a.get("modality") == Modality.video.value),
        provider_mix=provider_mix,
        dedup_savings_pct=round(dedup, 1),
        embedded_pct=round(embedded / total_assets * 100, 1) if total_assets else 0.0,
        b2=_b2_stats(),
        generated_24h=_recent(generated, "created_at", day_ago),
        provider_budget=_provider_budget(),
    )


def _b2_stats() -> dict:
    """Live object/byte counts from storage. Never let a storage hiccup 500 the dashboard."""
    try:
        from ..storage import get_storage

        return get_storage().stats(prefix="")
    except Exception as exc:  # noqa: BLE001
        log.warning("b2 stats unavailable: %s: %s", type(exc).__name__, exc)
        return {"backend": "unknown", "error": type(exc).__name__, "objects": 0, "bytes": 0}


@router.get("/users", response_model=list[AdminUserRow])
def list_users(user: CurrentUser = Depends(require_admin)):
    """Every user with their credit position and activity counts."""
    repo = get_repo()
    users = repo.list_users()
    skus = repo.list_all_skus()
    assets = repo.list_all_assets()
    jobs = repo.list_all_jobs(limit=1000)

    def _tally(rows: list[dict]) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in rows:
            uid = r.get("owner_uid") or ""
            out[uid] = out.get(uid, 0) + 1
        return out

    sku_counts, asset_counts, job_counts = _tally(skus), _tally(assets), _tally(jobs)

    rows = [
        AdminUserRow(
            uid=u.get("uid", ""),
            email=u.get("email"),
            username=u.get("username"),
            roles=u.get("roles", []),
            credits_balance=round(float(u.get("credits_balance") or 0.0), 4),
            credits_spent_total=round(float(u.get("credits_spent_total") or 0.0), 4),
            skus=sku_counts.get(u.get("uid", ""), 0),
            assets=asset_counts.get(u.get("uid", ""), 0),
            jobs=job_counts.get(u.get("uid", ""), 0),
            last_active=u.get("updated_at"),
            created_at=u.get("created_at"),
        )
        for u in users
    ]
    rows.sort(key=lambda r: r.assets, reverse=True)
    return rows


@router.get("/jobs", response_model=list[AdminJobRow])
def list_jobs(limit: int = Query(default=50, ge=1, le=200),
              status: JobStatus | None = None,
              user: CurrentUser = Depends(require_admin)):
    """Recent jobs across all users — the operational feed for spotting failures."""
    repo = get_repo()
    jobs = repo.list_all_jobs(limit=500)
    if status:
        jobs = [j for j in jobs if j.get("status") == status.value]
    emails = {u.get("uid"): u.get("email") for u in repo.list_users()}
    return [
        AdminJobRow(
            id=j.get("id", ""),
            owner_uid=j.get("owner_uid", ""),
            owner_email=emails.get(j.get("owner_uid")),
            sku_id=j.get("sku_id", ""),
            status=j.get("status", JobStatus.queued.value),
            requested_styles=j.get("requested_styles", []),
            asset_count=len(j.get("asset_ids") or []),
            cost_actual=j.get("cost_estimate"),
            duration_ms=_duration_ms(j),
            error=j.get("error"),
            created_at=j.get("created_at"),
        )
        for j in jobs[:limit]
    ]


@router.get("/ledger", response_model=list[LedgerEntryOut])
def list_ledger(limit: int = Query(default=100, ge=1, le=200),
                user: CurrentUser = Depends(require_admin)):
    """Platform-wide credit transactions, newest first."""
    return get_repo().list_all_ledger(limit=limit)


@router.post("/users/{uid}/credits", response_model=LedgerEntryOut)
def grant_credits(uid: str, body: GrantRequest, actor: CurrentUser = Depends(require_admin)):
    """Top up (or correct) a user's balance. Attributed to the acting admin in the ledger."""
    if get_repo().get_user(uid) is None:
        raise HTTPException(404, "User not found")
    return credits_mod.grant(uid, body.amount_usd, actor_uid=actor.uid, note=body.note)


@router.post("/users/{uid}/roles", response_model=AdminUserRow)
def set_roles(uid: str, body: RolesRequest, actor: CurrentUser = Depends(require_admin)):
    """Replace a user's roles.

    An admin cannot strip their own admin role: doing so can leave a deployment with zero
    admins and no in-app way back, since granting the role requires being one.
    """
    repo = get_repo()
    existing = repo.get_user(uid)
    if existing is None:
        raise HTTPException(404, "User not found")

    roles = sorted({r.value for r in body.roles})
    if uid == actor.uid and "admin" not in roles:
        raise HTTPException(400, "You cannot remove your own admin role")

    repo.set_user(uid, {"roles": roles, "updated_at": utcnow()})
    log.info("roles set by %s: %s → %s", actor.uid, uid, roles)
    doc = repo.get_user(uid) or {}
    return AdminUserRow(
        uid=uid,
        email=doc.get("email"),
        username=doc.get("username"),
        roles=doc.get("roles", []),
        credits_balance=round(float(doc.get("credits_balance") or 0.0), 4),
        credits_spent_total=round(float(doc.get("credits_spent_total") or 0.0), 4),
        last_active=doc.get("updated_at"),
        created_at=doc.get("created_at"),
    )


_BUDGET_SOURCE = (
    "Derived: operator-recorded top-up minus spend metered from the provider's own "
    "per-step cost. GMI Cloud exposes no balance endpoint to the inference API key, so this "
    "is not read from GMI — reconcile against the GMI console for the authoritative figure."
)


def _metered_provider_spend() -> float:
    """Total real provider cost across every job we've run.

    Sums `cost_actual` (from Step.cost_usd) rather than our own credit ledger: the ledger
    tracks what we charged *users*, which is a different number from what the provider
    charged *us*.
    """
    jobs = get_repo().list_all_jobs(limit=10_000)
    return round(sum(float(j.get("cost_actual") or 0.0) for j in jobs), 4)


def _provider_budget() -> ProviderBudgetOut:
    config = get_repo().get_platform_config()
    budget = float(config.get("provider_budget_usd") or 0.0)
    spend = _metered_provider_spend()
    return ProviderBudgetOut(
        budget_usd=round(budget, 4),
        metered_spend_usd=spend,
        remaining_usd=round(budget - spend, 4),
        configured=bool(config.get("provider_budget_usd") is not None),
        updated_at=config.get("provider_budget_updated_at"),
        updated_by=config.get("provider_budget_updated_by"),
        provider_api_supports_balance=False,
        source=_BUDGET_SOURCE,
    )


@router.get("/provider-budget", response_model=ProviderBudgetOut)
def provider_budget(user: CurrentUser = Depends(require_admin)):
    """Provider credit position — derived, never fetched from GMI. See ProviderBudgetOut."""
    return _provider_budget()


@router.post("/provider-budget", response_model=ProviderBudgetOut)
def set_provider_budget(body: ProviderBudgetRequest,
                        actor: CurrentUser = Depends(require_admin)):
    """Record the provider credit purchased, so remaining spend can be tracked against it."""
    get_repo().set_platform_config({
        "provider_budget_usd": body.budget_usd,
        "provider_budget_note": body.note,
        "provider_budget_updated_at": utcnow(),
        "provider_budget_updated_by": actor.uid,
    })
    log.info("provider budget set to $%.2f by %s", body.budget_usd, actor.uid)
    return _provider_budget()


@router.get("/health", response_model=AdminHealthOut)
def health(user: CurrentUser = Depends(require_admin)):
    """Deep dependency health with per-check latency.

    This is the deep variant (it round-trips to B2), which the public `/healthz` avoids so
    Render's frequent liveness probe stays cheap.
    """
    from ..generation import generation_mode
    from ..health import check_b2, check_firebase

    settings = get_settings()

    def _timed(name: str, fn) -> ServiceCheck:
        start = time.perf_counter()
        result = fn()
        elapsed = int((time.perf_counter() - start) * 1000)
        return ServiceCheck(
            name=name,
            ok=bool(result.get("ok")),
            detail=result.get("error") or result.get("checked"),
            latency_ms=elapsed,
        )

    checks = [
        _timed("firebase", check_firebase),
        _timed("b2", lambda: check_b2(deep=True)),
    ]
    degraded = [c.name for c in checks if not c.ok]

    return AdminHealthOut(
        status="degraded" if degraded else "ok",
        env=settings.app_env,
        checks=checks,
        job_queue=settings.job_queue,
        generation_mode=generation_mode(),
        # Configured ≠ funded — same caveat as health.check_generation. These booleans say
        # a key is present, not that the account behind it has credit.
        providers={
            "gmi": bool(settings.gmi_api_key),
            "openai": bool(settings.openai_api_key),
            "gemini": bool(settings.gemini_api_key),
            "luma": bool(settings.luma_api_key),
            "elevenlabs": bool(settings.elevenlabs_api_key),
        },
        manifest_embed_mode=settings.manifest_embed_mode,
        uptime_seconds=int(time.time() - _STARTED_AT),
        version="0.1.0",
    )
