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
    # Spoken product-video narration (OpenAI TTS via Genblaze). The app's audio modality —
    # reached by a provider swap, not the blocked GMI audio path (originshot_pipelines/
    # voiceover.py; docs/genblaze-issues/04). Opt-in: it is not in the default style set.
    voiceover = "voiceover"


class Modality(str, Enum):
    image = "image"
    video = "video"
    audio = "audio"


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


class SkuUpdate(BaseModel):
    """Partial update — every field optional; only those supplied are changed.

    Same length bounds as SkuCreate so an edit can't smuggle past validation that a create
    enforces. `title` keeps its non-empty floor: a product with a blank title is not a valid
    edit, only an omitted one.
    """
    title: str | None = Field(default=None, min_length=1, max_length=140)
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
    # Post-generation QA report (originshot_pipelines/qa.py): passed, checks[], scorer,
    # vlm_score/verdict, attempt(s). None ⇒ QA didn't run for this asset (video, mock, or
    # the bytes couldn't be fetched) — absence of a report is never presented as a pass.
    qa: dict | None = None
    # SHA-256 of the asset this one was replayed from (its manifest supplied the spec).
    # Distinct from parent_sha256, which always points at the authentic original.
    replay_of: str | None = None
    # Voiceover audio: the narration text and how the SCRIPT itself was produced (model vs
    # deterministic template) — disclosed, never passed off as human copy.
    script: str | None = None
    script_source: str | None = None
    script_model: str | None = None
    # Narrated video: the [video_sha, audio_sha] this MP4 was muxed from — both individually
    # provenance-tracked, so the composite's lineage is two verifiable parents.
    muxed_from: list[str] | None = None
    created_at: datetime


# ── Catalog Intelligence: search + integrity (app/catalog_intel.py) ───
class SimilarAssetOut(AssetOut):
    """A library asset that visually resembles a query asset, with its pHash bit-distance."""
    phash_distance: int


class CatalogSearchHit(BaseModel):
    sku_id: str
    title: str | None = None
    category: str | None = None
    score: float  # cosine similarity of the SKU's text embedding to the query


class CatalogSearchOut(BaseModel):
    """Semantic search over the catalog. `available` is False when it's off (no OpenAI key) —
    a distinct state from "ran and found nothing", so the UI never implies an empty catalog."""
    available: bool
    indexed: int          # SKUs that carry an embedding (0 ⇒ run a reindex)
    hits: list[CatalogSearchHit]


class ReusedOriginalFinding(BaseModel):
    """One authentic original (pre-AI photo) anchoring more than one distinct SKU."""
    parent_sha256: str
    sku_ids: list[str]
    sku_count: int


class NearDuplicateFinding(BaseModel):
    """SKUs whose authentic source photos are perceptually near-identical across products."""
    sku_ids: list[str]
    sku_count: int


class IntegrityOut(BaseModel):
    """Cross-catalog integrity signals — flags for a human, never accusations of fraud."""
    reused_originals: list[ReusedOriginalFinding]
    near_duplicate_sources: list[NearDuplicateFinding]
    skus_analyzed: int
    generated_at: str


class ReindexOut(BaseModel):
    available: bool
    embedded: int
    skipped: int
    total: int


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
    # Where `cost_usd` came from: "provider" (the provider billed it), "estimate" (the
    # provider's SDK reports no cost — currently every OpenAI step — so this is list price),
    # "mixed", or "none". Carried so the UI can label an estimate as an estimate instead of
    # presenting it as a bill. See pricing.billable_cost.
    cost_source: str | None = None
    asset_count: int = 0
    error: str | None = None
    # QA rollup for the step: None when no asset carried a report.
    qa_passed: bool | None = None
    qa_attempts: int | None = None


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
    # Provenance of the cost figure above — see JobStep.cost_source.
    cost_source: str | None = None
    # Set when this job is a replay: the content hash of the asset whose manifest is being
    # re-executed (see api/generate.replay).
    replay_of_sha256: str | None = None


# ── Catalog batches ───────────────────────────────────────────────────
class BatchItemStatus(str, Enum):
    """Per-SKU state within a catalog run.

    `blocked` is distinct from `failed` on purpose: it means the run never started for this
    item (credit exhausted, daily quota reached), so nothing was spent and re-running it
    later is the obvious fix. Collapsing the two would tell a seller their photos failed
    when in fact they simply ran out of balance.
    """
    pending = "pending"
    running = "running"
    done = "done"
    partial = "partial"
    failed = "failed"
    blocked = "blocked"


class BatchStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    partial = "partial"
    failed = "failed"


class BatchCreate(BaseModel):
    """SKUs are created and their photos uploaded through the existing per-SKU routes, then
    handed here as ids. That keeps one hardened upload path rather than a second bulk one,
    and keeps a 10-photo catalog off a single multi-hundred-megabyte request."""
    sku_ids: list[str] = Field(min_length=1, max_length=100)
    styles: list[Style] = Field(default_factory=lambda: [Style.studio, Style.lifestyle])
    marketplaces: list[Marketplace] = Field(default_factory=list)
    title: str | None = Field(default=None, max_length=140)


class BatchItemOut(BaseModel):
    sku_id: str
    title: str | None = None
    job_id: str | None = None
    status: BatchItemStatus = BatchItemStatus.pending
    asset_count: int = 0
    cost_actual: float | None = None
    duration_ms: int | None = None
    error: str | None = None


class BatchOut(BaseModel):
    id: str
    owner_uid: str
    title: str | None = None
    status: BatchStatus
    styles: list[Style]
    marketplaces: list[Marketplace] = Field(default_factory=list)
    items: list[BatchItemOut] = Field(default_factory=list)
    concurrency: int = 1
    cost_estimate: float | None = None
    cost_actual: float | None = None
    eta_seconds: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BatchEstimateOut(BaseModel):
    """Pre-flight quote for a whole catalog, so the cost is on screen before committing."""
    skus: int
    styles: list[Style]
    per_sku_usd: float
    total_estimate_usd: float
    balance_usd: float
    affordable: bool
    eta_seconds: int
    quota_remaining: int
    basis: str


# ── Marketplace compliance ────────────────────────────────────────────
class ComplianceOut(BaseModel):
    """Scorecard for the SKU's main image across marketplace presets. `items` entries:
    {marketplace, preset, passed, checks[]} — measured on rendered output, not intent."""
    source_style: str | None = None
    source_sha256: str | None = None
    items: list[dict]


# ── Listing copy ──────────────────────────────────────────────────────
class ListingRequest(BaseModel):
    marketplaces: list[Marketplace] = Field(default_factory=list)  # empty ⇒ all channels


class ListingOut(BaseModel):
    """Per-marketplace listing copy, stored on the SKU document. `marketplaces` maps
    channel → {title, description, bullets[], keywords[], title_max}; the hard limits are
    enforced server-side (originshot_pipelines/listing.py), not trusted from the model."""
    generated_at: str
    provider: str
    model: str
    disclosure: str
    marketplaces: dict[str, dict]


# ── Provenance / verify ───────────────────────────────────────────────
class PerceptualMatch(BaseModel):
    """A "Verify in the Wild" hit: the uploaded image looks like a known OriginShot asset.

    The uploaded file carried no usable manifest and matched no stored hash — consistent with
    a marketplace having re-encoded it — but its perceptual hash is close to a generated
    asset we hold. Everything here is a *similarity* claim; the wording throughout says so,
    and `distance`/`confidence` are always shown together so a reader can weigh it.
    """
    matched_sha256: str          # the known asset this resembles
    distance: int                # Hamming distance over the 64-bit pHash (0 = identical)
    confidence: float            # 0–1, for display; the honest signal is `distance`
    strong: bool                 # distance ≤ the confident-match threshold
    style: Style | None = None
    provider: str | None = None
    model: str | None = None
    # Lineage of the matched asset — lets the buyer trace a re-encoded listing photo back to
    # the authentic pre-AI original, which is the whole point of showing this.
    parent_sha256: str | None = None
    matched_in_ledger: bool = False


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
    # Position in the append-only transparency log, when this hash was recorded there.
    # None means "not in the log", which is deliberately NOT presented as a negative signal:
    # appends are best-effort, so absence proves nothing (see app/transparency.py).
    ledger: LedgerPosition | None = None
    # ── Verify in the Wild: the perceptual-match tier ─────────────────
    # Populated ONLY when the cryptographic tiers found nothing (no manifest, no exact-hash
    # record) but the image is perceptually close to a known asset — i.e. a re-encoded
    # marketplace copy whose manifest was stripped. This is EVIDENCE, never proof: it never
    # sets `content_bound` and is always reported with its raw bit-distance so the strength of
    # the claim is visible. None on every cryptographically-resolved verification.
    perceptual: PerceptualMatch | None = None


class CheckResult(BaseModel):
    """A "Verify Anywhere" result — the buyer-facing wrapper around a `VerifyResult`.

    `POST /api/check` is the public buyer surface: paste a listing/image link or drop a photo,
    and it runs the *same* verification core as `/verify`. This wrapper only records where the
    checked image came from, so the UI can say "we scanned the photo on that page" honestly.
    The verdict itself lives entirely in `result`; nothing here weakens or restates it.
    """
    # How the checked image was obtained: a dropped/pasted file, a direct image URL, or an
    # image extracted from an HTML listing page.
    source: str                          # "upload" | "url_image" | "listing_page"
    source_url: str | None = None        # the link the caller supplied, echoed back
    images_scanned: int = 1              # >1 only for a listing page with several photos
    result: VerifyResult


# ── Signing ───────────────────────────────────────────────────────────
class SignatureRecord(BaseModel):
    """A detached Ed25519 signature over an artefact's content hash. See app/signing.py.

    The same shape is attached to transparency checkpoints, audit reports and dispute reports:
    the signature is over the hex digest the artefact already carries, and it verifies against
    the public key committed in the repository (`signing.PUBLISHED_PUBLIC_KEY_HEX`).
    """
    algorithm: str = "ed25519"
    key_id: str
    signature: str


# ── Transparency log ──────────────────────────────────────────────────
class LedgerEntryRow(BaseModel):
    """One append-only log entry. Every field here is covered by `entry_hash`."""
    seq: int
    prev_hash: str
    subject_sha256: str
    manifest_hash: str = ""
    kind: str
    recorded_at: str
    entry_hash: str


class CheckpointWitness(BaseModel):
    """An independent, operator-uncontrollable timestamp for a checkpoint (see app/witness.py).

    Object Lock (our bucket, our config) and the Ed25519 signature (our key) both rest on
    infrastructure the operator controls. This anchors the checkpoint hash into **Bitcoin** via
    OpenTimestamps — a party the operator does not control — so "this head existed by time T and
    was not rewritten" becomes checkable against Bitcoin, needing nothing from us.
    """
    type: str = "opentimestamps"
    proof_key: str | None = None            # where the .ots proof lives on B2
    # Calendars that accepted the hash, before Bitcoin confirmation. The proof is a verifiable
    # calendar commitment immediately; the Auditor upgrades it to a Bitcoin attestation later.
    pending_calendars: list[str] = Field(default_factory=list)
    # Set once the proof is anchored in a Bitcoin block — the honest bound on "existed no later
    # than". Absent (None) while the anchor is still a calendar commitment, never overstated.
    bitcoin_block_height: int | None = None
    complete: bool = False                  # True iff a Bitcoin attestation is present


class LedgerCheckpointOut(BaseModel):
    """A published commitment to the log up to `size` entries."""
    log_id: str
    size: int
    head: str
    issued_at: str
    checkpoint_hash: str
    b2_key: str | None = None      # where the published copy lives on B2
    # Set only when this checkpoint was published under B2 Object Lock — i.e. it is physically
    # immutable (cannot be altered or deleted, even by the operator) until this instant. Its
    # absence means the checkpoint was published without a lock; the field never overstates.
    retained_until: str | None = None
    # Ed25519 signature over `checkpoint_hash` — attests THIS instance issued this head,
    # verifiable offline against the repo-published public key. Absent when signing is off.
    signature: SignatureRecord | None = None
    # Independent Bitcoin timestamp (OpenTimestamps). Absent when witnessing is off or the
    # calendars were unreachable — never a claim of an anchor that isn't there.
    witness: CheckpointWitness | None = None


class LedgerStatusOut(BaseModel):
    log_id: str
    size: int
    head: str
    checkpoint: LedgerCheckpointOut | None = None
    # Entries appended since the last checkpoint: they are in the log but not yet committed
    # to by any published head, which is a real distinction and shown rather than smoothed.
    checkpoint_lag: int = 0


class LedgerProofOut(BaseModel):
    entry: LedgerEntryRow
    following: list[LedgerEntryRow]
    checkpoint: LedgerCheckpointOut
    note: str


class LedgerVerifyOut(BaseModel):
    consistent: bool
    size: int
    head: str
    broken_at: int | None = None
    reason: str | None = None
    checkpoint_reproduced: bool | None = None
    caveat: str


class LedgerAuditOut(BaseModel):
    """One integrity-audit pass (app/auditor.py): what ran, what it verified, what it found.

    `failures` rows carry {sha256, style, kind, checks, error?} — enough to name the exact
    asset and the exact check that failed, because "1 failure" without a subject is an
    alarm nobody can act on. `sha256` is the hash of the report as published to B2, so the
    stored object can be checked against this very response.
    """
    audit_id: str
    started_at: str
    finished_at: str
    duration_ms: int
    assets_sampled: int
    assets_passed: int
    failures: list[dict] = Field(default_factory=list)
    ledger_entries: int
    chain_consistent: bool | None = None
    checkpoint_reproduced: bool | None = None
    checkpoint: LedgerCheckpointOut | None = None
    b2_key: str | None = None
    sha256: str | None = None
    caveat: str


class LedgerPosition(BaseModel):
    """Where an asset sits in the log — attached to a verification result."""
    seq: int
    entry_hash: str
    recorded_at: str
    log_size: int
    checkpoint_hash: str | None = None
    checkpoint_size: int | None = None
    checkpoint_covers_entry: bool = False


# ── Resolve (dispute evidence) ────────────────────────────────────────
class ResolveListing(BaseModel):
    """What the listing file's own bytes say about themselves."""
    sha256: str | None = None
    present: bool = False           # an embedded manifest was found
    verified: bool = False          # that manifest passes verify()
    content_bound: bool | None = None
    found: bool = False             # a matching record exists in this ledger
    is_authentic: bool = False
    provider: str | None = None
    model: str | None = None
    created_at: datetime | None = None


class ResolveAnchor(BaseModel):
    """The authentic original the listing descends from — the comparison reference."""
    sha256: str | None = None
    created_at: datetime | None = None


class ResolveReceived(BaseModel):
    """The delivered-item photo. Hash only: the bytes are never stored (see resolve.py)."""
    sha256: str | None = None


class ResolveMatch(BaseModel):
    score: int
    verdict: str
    differences: list[str] = Field(default_factory=list)
    model: str


class ResolveOut(BaseModel):
    """A Dispute Evidence Report. `report_url` is a short-lived presigned link to the PDF."""
    id: str
    issued_at: str
    finding: str
    severity: str
    headline: str
    detail: str
    listing: ResolveListing
    anchor: ResolveAnchor | None = None
    received: ResolveReceived | None = None
    match: ResolveMatch | None = None
    match_unavailable: str | None = None
    report_sha256: str | None = None
    report_url: str | None = None
    # Detached Ed25519 signature over `report_sha256` — proves this instance issued the PDF,
    # verifiable against the repo-published public key. None when signing isn't configured.
    report_signature: SignatureRecord | None = None


# ── Analytics ─────────────────────────────────────────────────────────
class AnalyticsOut(BaseModel):
    total_assets: int
    unique_objects: int
    dedup_savings_pct: float
    images: int
    videos: int
    # Two cost figures, deliberately kept apart (see app/pricing.py's module docstring):
    # `actual_cost_usd` is the ledger-settled sum of provider-billed Step.cost_usd;
    # `estimated_cost_usd` is derived from list prices and exists for assets that predate
    # cost capture (and the dev mock, which bills nothing). `cost_source` says which is which
    # so the UI never has to guess.
    actual_cost_usd: float
    estimated_cost_usd: float
    cost_source: str
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
