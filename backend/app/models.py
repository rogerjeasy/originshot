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
    finished_at: datetime | None = None


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
