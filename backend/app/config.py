"""Application settings, loaded from environment / .env.

Secrets live ONLY in the environment — never in the repo. See ../docs/SECURITY.md §5.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Single repo-root env file (originshot/.env), shared with the frontend. Resolved relative to
# this module so it loads no matter where uvicorn is launched from. Missing in production
# (Render injects real env vars, which always take precedence over an env file) — pydantic
# tolerates the absent file. config.py is at originshot/backend/app/ ⇒ parents[2] == originshot/.
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT_ENV), env_file_encoding="utf-8", extra="ignore", case_sensitive=False
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

    # ── B2 Object Lock for the transparency ledger ────────────────────
    # A transparency checkpoint published to object storage is only as trustworthy as the
    # storage: an operator who controls the bucket could quietly overwrite a checkpoint that
    # later proves inconvenient. B2 Object Lock (a B2-native capability, not generic S3)
    # closes that hole — a locked object cannot be altered or deleted before its retention
    # expires, by anyone, including the account owner with root credentials. We apply it to
    # the two objects the whole trust argument rests on: transparency checkpoints and audit
    # reports.
    #
    # `b2_object_lock_days = 0` DISABLES it (default) — it stays off until the bucket has file
    # lock enabled and the app key carries `writeFileRetentions`, because a locked write with
    # a key that lacks the capability just fails. When those are in place, set the retention
    # period here. See docs: README "Backblaze B2 differentiators" and app/storage.py.
    # ── Ed25519 signing for the transparency log ──────────────────────
    # The 32-byte Ed25519 private seed (hex), used to sign transparency checkpoints, audit
    # reports and dispute reports — turning "hash-anchored against a published record" into
    # "signed by this instance", verifiable offline against the PUBLISHED public key that ships
    # in the repo (app/signing.py::PUBLISHED_PUBLIC_KEY_HEX). Unset ⇒ signing is disabled and
    # artefacts publish unsigned (best-effort, like Object Lock). Never commit this value.
    signing_private_key: str | None = None

    b2_object_lock_days: int = 0
    # COMPLIANCE (default) can be bypassed by no one until expiry — the strong claim, and the
    # only mode that actually upgrades "trust us" to "you don't have to". GOVERNANCE can be
    # bypassed with a privileged key, so it is a weaker guarantee offered only for operators
    # who need an escape hatch.
    b2_object_lock_mode: str = "COMPLIANCE"

    # Redis / worker
    redis_url: str = "redis://localhost:6379"

    # Providers
    gmi_api_key: str | None = None
    openai_api_key: str | None = None
    # Which image-edit provider serves a run: "auto" walks providers.AUTO_ORDER and uses the
    # first CONFIGURED one, falling across to the next only when a run actually fails (so a
    # provider that is out of credit costs one failed request, not a permanent misroute).
    # Pin to "gmicloud-image" or "openai-dalle" to force one — a pinned provider that isn't
    # configured refuses rather than quietly serving a different one, because provenance
    # records which provider ran and that record has to be true.
    image_provider: str = "auto"
    gemini_api_key: str | None = None
    luma_api_key: str | None = None
    elevenlabs_api_key: str | None = None

    # Limits & quotas
    max_upload_mb: int = 25
    max_image_pixels: int = 40_000_000
    daily_generation_quota: int = 50
    presigned_url_ttl_seconds: int = 900

    # Global per-IP ceiling, applied to every route by SlowAPIMiddleware. Sized as an ABUSE
    # ceiling, not a fairness knob: the studio polls `/api/jobs/{id}` every 1.2s during a run
    # (50 req/min) and reloads the asset grid on each completed step, so a limit anywhere
    # near 60/min would throttle one honest user mid-generation. Endpoints where a request
    # costs real provider money carry their own, much tighter limit on top of this.
    rate_limit_per_minute: int = 240

    # Resolve is public (a buyer in a dispute has no account) AND spends a vision-model call
    # per report, so it is the app's only unauthenticated path to a provider bill. Tight
    # per-IP limit; see app/api/resolve.py.
    resolve_rate_limit: str = "10/hour"
    resolve_enabled: bool = True

    # Credits (USD). The daily quota above bounds *request volume*; credits bound *spend* —
    # a single video pack costs 10x an image pack, so a request count alone can't cap cost.
    signup_credit_grant: float = 5.0
    low_balance_threshold: float = 1.0

    # Admin bootstrap: comma-separated emails that are treated as admins on sight and have
    # the role written back to their user document on first authenticated request. Without
    # this there is no way to mint the first admin — every grant path already requires one.
    # Roles in Firestore remain the source of truth; this only seeds them.
    admin_emails: str = ""

    # How generation jobs run: "inline" (BackgroundTasks) or "arq" (Redis worker).
    job_queue: str = "inline"

    # Transparency log: an append-only hash chain over every manifest issued, with heads
    # published to B2 as checkpoints. Appends are best-effort — a ledger outage must never
    # fail a generation the provider already billed for. See app/transparency.py.
    transparency_enabled: bool = True
    # Cut a checkpoint every N entries. Low enough that a demo produces several; the
    # Auditor (app/auditor.py) supplies the timer-based cut so a quiet period still gets
    # committed.
    transparency_checkpoint_every: int = 10

    # ── The Auditor: scheduled integrity agent (app/auditor.py) ────────
    # POST /api/ledger/audit runs one audit pass: re-verify a sample of stored assets
    # against their own B2 bytes, replay the ledger against the last published checkpoint,
    # publish a fresh checkpoint, and write the report to B2. The trigger authenticates
    # with this shared token because the caller is a scheduler (GitHub Actions cron), not
    # a person — unset ⇒ the trigger endpoint refuses with 503.
    audit_trigger_token: str | None = None
    # How many assets one audit pass downloads and re-verifies. Bounds the B2 transaction
    # cost of a scheduled run; a small random sample every few hours covers the library
    # over time without ever making the audit itself expensive.
    audit_sample_size: int = 25

    # Catalog Mode: how many SKUs generate at once within one batch. Generation is I/O-bound
    # on the provider so parallelism buys wall-clock cheaply, but each in-flight job also
    # holds decoded image bytes for QA scoring in this same process, and the deployment
    # target is a 512 MB free-tier instance. See app/batches.py::concurrency_for.
    catalog_concurrency: int = 2
    # Ceiling on SKUs per batch — bounds one request's blast radius on quota and spend.
    catalog_max_skus: int = 100
    image_timeout_seconds: int = 300
    video_timeout_seconds: int = 600

    # ── Mock generation: TESTS ONLY ───────────────────────────────────
    # The mock fabricates assets by copying the uploaded original and labelling them
    # `provider="mock-dev"`. That is useful in the suite (real provider calls cost money and
    # would make `pytest` billable) and actively harmful anywhere else: fabricated assets
    # flow into analytics, the admin dashboard, provider-mix charts and the credit ledger,
    # where they are indistinguishable from real generations at a glance.
    #
    # So it is OFF by default and must be switched on explicitly. When generation isn't
    # configured, the API refuses the request with an actionable 503 rather than quietly
    # serving fake media. Only `tests/conftest.py` sets this.
    mock_generation_enabled: bool = False
    # Per-style pause in the mock, so the live progress UI is demonstrable. Tests set 0.
    mock_step_delay_seconds: float = 0.0

    # ── Post-generation QA (generate → evaluate → retry → store) ──────
    # Deterministic Pillow checks always run when qa_enabled; the VLM product-fidelity tier
    # additionally needs the GMI key and is best-effort (the chat endpoint 429s under load).
    # qa_retry_enabled regenerates a style ONCE when its output fails QA. A retry can push
    # the actual cost over the up-front quote; the ledger's overage-debit path handles that
    # honestly (see credits.settle), and the retry cap bounds it to 2x per style.
    qa_enabled: bool = True
    qa_vlm_enabled: bool = True
    qa_retry_enabled: bool = True
    qa_vlm_timeout_seconds: int = 60

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
    def admin_email_set(self) -> set[str]:
        """Lowercased for comparison — email case must not decide an authorization outcome."""
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def b2_endpoint(self) -> str:
        # boto3 requires a scheme; tolerate a bare host in B2_ENDPOINT_URL (e.g.
        # "s3.eu-central-003.backblazeb2.com") by defaulting it to https://.
        raw = self.b2_endpoint_url or f"s3.{self.b2_region}.backblazeb2.com"
        return raw if "://" in raw else f"https://{raw}"

    @property
    def firebase_configured(self) -> bool:
        return bool(self.firebase_project_id)

    @property
    def b2_configured(self) -> bool:
        return bool(self.b2_key_id and self.b2_app_key and self.b2_bucket)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


# Keys that downstream libraries read straight from `os.environ` rather than from our
# Settings object: the Genblaze GMICloud providers (`GMI_API_KEY`), the Genblaze B2 sink
# (`originshot_pipelines/storage.py` → `B2_*`), and the Firebase Admin SDK
# (`GOOGLE_APPLICATION_CREDENTIALS`). `pydantic-settings` reads the `.env` FILE into this
# object but does NOT populate `os.environ`, so we mirror these across explicitly. Without
# this, flipping on real keys makes `make_sink()` KeyError and the providers auth-fail.
_ENV_MIRROR = {
    "GMI_API_KEY": "gmi_api_key",
    "OPENAI_API_KEY": "openai_api_key",
    "GEMINI_API_KEY": "gemini_api_key",
    "LUMA_API_KEY": "luma_api_key",
    "ELEVENLABS_API_KEY": "elevenlabs_api_key",
    "B2_KEY_ID": "b2_key_id",
    "B2_APP_KEY": "b2_app_key",
    "B2_BUCKET": "b2_bucket",
    "B2_REGION": "b2_region",
    "B2_ENDPOINT_URL": "b2_endpoint_url",
    "GOOGLE_APPLICATION_CREDENTIALS": "google_application_credentials",
    "FIREBASE_PROJECT_ID": "firebase_project_id",
}


def _mirror_to_environ(settings: Settings) -> None:
    """Publish `.env`-loaded secrets into `os.environ` for libraries that read it directly.

    `setdefault` so a real process env var (e.g. on Render) always wins over the `.env` file.
    """
    for env_key, attr in _ENV_MIRROR.items():
        val = getattr(settings, attr, None)
        if val:
            os.environ.setdefault(env_key, str(val))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    _mirror_to_environ(settings)
    return settings
