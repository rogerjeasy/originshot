"""Pydantic schemas — request/response bodies and Firestore document shapes."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Style(str, Enum):
    original = "original"
    studio = "studio"
    lifestyle = "lifestyle"
    onmodel = "onmodel"
    variant = "variant"
    video = "video"


class Modality(str, Enum):
    image = "image"
    video = "video"


class Marketplace(str, Enum):
    amazon = "amazon"
    etsy = "etsy"
    shopify = "shopify"
    ebay = "ebay"
    social = "social"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    partial = "partial"
    done = "done"
    failed = "failed"


# ── Users & roles ─────────────────────────────────────────────────────
class Role(str, Enum):
    """A user may hold several of these at once (see UserOut.roles)."""
    customer = "customer"   # default — everyone starts here
    seller = "seller"       # can be granted later for seller-specific features
    admin = "admin"         # elevated / staff access


# Roles are stored as an ARRAY of strings on the user document. An array (rather than a
# single field) lets one user hold multiple roles and is directly queryable in Firestore
# via `array_contains` (e.g. "all admins"). New users default to exactly ["customer"].
DEFAULT_ROLES: list[Role] = [Role.customer]


class UserRegister(BaseModel):
    """Body for POST /users, sent by the client right after Firebase sign-up.

    NOTE: the password is handled entirely by Firebase Auth on the client and is NEVER
    sent to or stored by this backend — we only persist a profile keyed by the verified uid.
    """
    username: str = Field(min_length=2, max_length=40)


class UserOut(BaseModel):
    uid: str
    email: str | None = None
    username: str | None = None
    roles: list[Role] = Field(default_factory=lambda: list(DEFAULT_ROLES))
    created_at: datetime
    updated_at: datetime | None = None
    credits_balance: float = 0.0


# ── Credits & ledger ──────────────────────────────────────────────────
class LedgerKind(str, Enum):
    """Why a balance moved. `hold` and its matching `refund`/`debit` bracket one job."""
    grant = "grant"     # credit added (signup bonus or admin top-up)
    hold = "hold"       # estimated cost reserved at job submit
    debit = "debit"     # settlement at or over the held estimate
    refund = "refund"   # settlement under the held estimate (or a failed job)
    adjust = "adjust"   # manual admin correction, may be negative


class LedgerEntryOut(BaseModel):
    id: str
    uid: str
    kind: LedgerKind
    amount_usd: float          # signed: negative means money left the balance
    balance_after: float
    seq: int = 0               # per-user monotonic; orders rows sharing a created_at
    job_id: str | None = None
    sku_id: str | None = None
    note: str | None = None
    actor_uid: str | None = None
    created_at: datetime


class CreditSummaryOut(BaseModel):
    balance_usd: float
    granted_total_usd: float
    spent_total_usd: float
    held_usd: float
    daily_quota: int
    daily_used: int
    low_balance: bool


class GrantRequest(BaseModel):
    amount_usd: float = Field(gt=-10_000, lt=10_000)
    note: str | None = Field(default=None, max_length=200)


class RolesRequest(BaseModel):
    roles: list[Role] = Field(min_length=1)


class CostEstimateOut(BaseModel):
    """Pre-flight quote shown before the user commits to a run."""
    styles: list[dict]
    total_estimate_usd: float
    eta_seconds: int
    balance_usd: float
    affordable: bool
    basis: str


# ── SKUs ──────────────────────────────────────────────────────────────
class SkuCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    category: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)


class SkuOut(BaseModel):
    id: str
    owner_uid: str
    title: str
    category: str | None = None
    description: str | None = None
    original_sha256: str | None = None
    created_at: datetime


# ── Assets ────────────────────────────────────────────────────────────
class AssetOut(BaseModel):
    id: str
    sku_id: str
    owner_uid: str
    sha256: str
    url: str | None = None  # short-lived presigned URL (filled on read)
    modality: Modality
    style: Style
    is_authentic: bool = False
    parent_sha256: str | None = None
    run_id: str | None = None
    provider: str | None = None
    model: str | None = None
    manifest_key: str | None = None
    embedded: bool = False  # True once the provenance manifest is embedded in the bytes
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    created_at: datetime


# ── Jobs ──────────────────────────────────────────────────────────────
class BrandKit(BaseModel):
    vibe: str | None = Field(default=None, max_length=120)       # e.g. "warm, minimal, premium"
    lighting: str | None = Field(default=None, max_length=120)   # e.g. "soft natural light"
    palette: str | None = Field(default=None, max_length=120)    # e.g. "earthy neutrals"
    props: str | None = Field(default=None, max_length=200)      # e.g. "linen, light oak, ceramics"
    notes: str | None = Field(default=None, max_length=500)


class GenerateRequest(BaseModel):
    styles: list[Style] = Field(default_factory=lambda: [Style.studio, Style.lifestyle])
    marketplaces: list[Marketplace] = Field(default_factory=list)


class ExportRequest(BaseModel):
    marketplaces: list[Marketplace] = Field(default_factory=list)


class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class JobStep(BaseModel):
    """One style's progress within a job.

    Written by the worker as the run advances so the client can show real per-step state
    instead of an indeterminate spinner. `duration_ms` is measured, not estimated;
    `eta_seconds` is the pre-run guess kept alongside it so the UI can show both and the
    gap between them stays visible.
    """
    style: Style
    status: StepStatus = StepStatus.pending
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    eta_seconds: int | None = None
    provider: str | None = None
    model: str | None = None
    cost_usd: float | None = None
    asset_count: int = 0
    error: str | None = None


class JobOut(BaseModel):
    id: str
    owner_uid: str
    sku_id: str
    status: JobStatus
    requested_styles: list[Style]
    marketplaces: list[Marketplace] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    cost_estimate: float | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # Live progress
    steps: list[JobStep] = Field(default_factory=list)
    eta_seconds: int | None = None
    credits_held: float | None = None
    cost_actual: float | None = None


# ── Provenance / verify ───────────────────────────────────────────────
class VerifyResult(BaseModel):
    sha256: str
    found: bool
    verified: bool
    is_authentic: bool
    embedded: bool = False  # True when verification came from a manifest embedded in the bytes
    # True/False when the bytes were checked against the manifest's signed content hash;
    # None when binding couldn't be determined (unsupported format, no record, pointer).
    content_bound: bool | None = None
    modality: Modality | None = None
    style: Style | None = None
    provider: str | None = None
    model: str | None = None
    parent_sha256: str | None = None
    created_at: datetime | None = None
    disclosure: str


# ── Analytics ─────────────────────────────────────────────────────────
class AnalyticsOut(BaseModel):
    total_assets: int
    unique_objects: int
    dedup_savings_pct: float
    images: int
    videos: int
    estimated_cost_usd: float
    provider_mix: dict[str, int]
    fallback_rate: float


# ── Admin ─────────────────────────────────────────────────────────────
class AdminUserRow(BaseModel):
    uid: str
    email: str | None = None
    username: str | None = None
    roles: list[Role] = Field(default_factory=list)
    credits_balance: float = 0.0
    credits_spent_total: float = 0.0
    skus: int = 0
    assets: int = 0
    jobs: int = 0
    last_active: datetime | None = None
    created_at: datetime | None = None


class AdminJobRow(BaseModel):
    """A job as the operator sees it — who ran it, how long it took, what it cost."""
    id: str
    owner_uid: str
    owner_email: str | None = None
    sku_id: str
    status: JobStatus
    requested_styles: list[Style] = Field(default_factory=list)
    asset_count: int = 0
    cost_actual: float | None = None
    duration_ms: int | None = None
    error: str | None = None
    created_at: datetime


class ProviderBudgetOut(BaseModel):
    """Provider (GMI Cloud) credit position, as far as we can honestly determine it.

    GMI's inference API exposes no balance endpoint (probed 2026-07-18: every billing path
    on api.gmi-serving.com hits a catch-all 405, and console.gmicloud.ai/api/v1/billing/*
    rejects an inference key with "token signature is invalid" — those routes want a console
    session JWT). So `remaining_usd` is NOT read from GMI. It is the operator-recorded
    top-up minus the spend we metered ourselves from Step.cost_usd.

    `source` says exactly that, and the UI prints it, so nobody mistakes a derived figure
    for the provider's own number.
    """
    budget_usd: float                  # what the operator recorded purchasing
    metered_spend_usd: float           # summed from real Step.cost_usd on our jobs
    remaining_usd: float               # budget − metered spend (derived, not authoritative)
    configured: bool                   # has an operator recorded a budget at all?
    updated_at: datetime | None = None
    updated_by: str | None = None
    provider_api_supports_balance: bool = False
    source: str


class ProviderBudgetRequest(BaseModel):
    budget_usd: float = Field(ge=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=200)


class AdminOverviewOut(BaseModel):
    # Platform scale
    users_total: int
    users_active_7d: int
    skus_total: int
    assets_total: int
    jobs_total: int
    # Reliability — the numbers that say whether this is production-ready
    jobs_succeeded: int
    jobs_partial: int
    jobs_failed: int
    success_rate_pct: float
    p50_duration_ms: int | None = None
    p95_duration_ms: int | None = None
    # Money
    spend_total_usd: float
    credits_outstanding_usd: float
    credits_granted_usd: float
    # Media
    images: int
    videos: int
    provider_mix: dict[str, int]
    dedup_savings_pct: float
    embedded_pct: float
    # B2
    b2: dict
    generated_24h: int
    # Provider (GMI) credit position — derived, see ProviderBudgetOut.
    provider_budget: ProviderBudgetOut | None = None


class ServiceCheck(BaseModel):
    name: str
    ok: bool
    detail: str | None = None
    latency_ms: int | None = None


class AdminHealthOut(BaseModel):
    status: str
    env: str
    checks: list[ServiceCheck]
    job_queue: str
    generation_mode: str
    providers: dict[str, bool]
    manifest_embed_mode: str
    uptime_seconds: int
    version: str
