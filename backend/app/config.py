"""Application settings, loaded from environment / .env.

Secrets live ONLY in the environment — never in the repo. See ../docs/SECURITY.md §5.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # App
    app_env: str = "dev"
    log_level: str = "INFO"
    public_base_url: str = "http://localhost:8000"
    allowed_origins: str = "http://localhost:3000"

    # Dev-only: bypass Firebase auth with a fake user. NEVER enable in production.
    auth_dev_bypass: bool = False

    # Firebase (Auth + Firestore)
    firebase_project_id: str | None = None
    google_application_credentials: str | None = None

    # Backblaze B2 (S3-compatible)
    b2_key_id: str | None = None
    b2_app_key: str | None = None
    b2_bucket: str | None = None
    b2_region: str = "us-west-000"
    b2_endpoint_url: str | None = None

    # Redis / worker
    redis_url: str = "redis://localhost:6379"

    # Providers
    gmi_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    luma_api_key: str | None = None
    elevenlabs_api_key: str | None = None

    # Limits & quotas
    max_upload_mb: int = 25
    max_image_pixels: int = 40_000_000
    daily_generation_quota: int = 50
    presigned_url_ttl_seconds: int = 900
    rate_limit_per_minute: int = 60

    # How generation jobs run: "inline" (BackgroundTasks) or "arq" (Redis worker).
    job_queue: str = "inline"
    image_timeout_seconds: int = 300
    video_timeout_seconds: int = 600

    # Manifest embedding into generated media (provenance):
    #   "full"    — embed the complete, self-contained verifiable manifest (prompts included);
    #               best for `genblaze verify <file>` with no network. (default)
    #   "pointer" — embed only {canonical_hash, manifest_uri}; keeps prompts private in the
    #               B2 sidecar. Requires a reachable manifest_uri.
    #   "none"    — don't embed; rely on the sidecar manifest + manifest.verify() only.
    manifest_embed_mode: str = "full"

    # ── Derived helpers ───────────────────────────────────────────────
    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() in {"dev", "development", "local"}

    @property
    def b2_endpoint(self) -> str:
        return self.b2_endpoint_url or f"https://s3.{self.b2_region}.backblazeb2.com"

    @property
    def firebase_configured(self) -> bool:
        return bool(self.firebase_project_id)

    @property
    def b2_configured(self) -> bool:
        return bool(self.b2_key_id and self.b2_app_key and self.b2_bucket)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
