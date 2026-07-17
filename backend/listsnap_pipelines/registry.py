"""Central provider/model configuration — the single source of truth.

This is also the canonical list of providers/models for the hackathon submission.

✅ WEEK-1 VERIFIED against the installed SDK (genblaze 0.4.0, genblaze-core 0.3.2,
   genblaze-gmicloud 0.3.1). Model IDs come from `genblaze_gmicloud.models`
   (`build_image_registry()` / `build_video_registry()`); the reference-image kwarg and
   aspect/duration params were confirmed against each model's `param_allowlist`.
"""
from __future__ import annotations

# ── Image editing (source photo → studio / lifestyle / on-model / variant) ──────────
# ✅ RUNTIME-VERIFIED (2026-07-15) against the live GMI request-queue API for our account:
#   `gemini-3-pro-image-preview` accepts a reference `image` + prompt and returns an edited
#   image — the model that actually powers our "one authentic photo → many shots" flow.
#
# ⚠️ IMPORTANT: the SDK's static catalog lists `seededit-3-0-i2i-250628` and the `reve-*`
#   models, and they run in the GMI *console playground*, but they 404 against the
#   request-queue API this app must use (`.../ie/requestqueue/.../requests`) — i.e. they are
#   NOT callable via the API for our account. `reve-*` additionally probe as upstream DEAD.
#   Do not put them back without a fresh live check (`validate_model`/probe LIE about these).
IMAGE_EDIT_MODEL = "gemini-3-pro-image-preview"       # Google Gemini 3 Pro image (via GMI)
# No same-signature image model is currently API-accessible as a fallback (seededit/reve are
# playground-only/dead). Bria genfill/eraser work but require a mask (different flow). Add a
# real fallback here once another edit model is entitled (or wire a second provider).
IMAGE_EDIT_FALLBACKS: list[str] = []

# ── Image → video (hero clip generated from the studio image) ───────────────────────
# Verified GMI video IDs: Kling-Image2Video-V2.1-Master · Kling-Text2Video-V2.1-Master
#   Veo3 · Veo3-Fast · pixverse-v5.6-i2v · pixverse-v5.6-t2v · pixverse-v5.6-transition
#   wan2.6-r2v
VIDEO_MODEL = "Kling-Image2Video-V2.1-Master"
VIDEO_FALLBACKS = ["pixverse-v5.6-i2v", "wan2.6-r2v"]   # image-to-video capable fallbacks

# ── Text → video (optional single-pass demo) ────────────────────────────────────────
# NOTE: GMI Cloud has no text→image model, so a true text→image→video chain would need a
# text→image provider (e.g. Google Imagen) for the first step. We expose a real single-step
# text→video instead; lineage/chaining is already demonstrated by the studio→hero-video flow.
TEXT2VIDEO_MODEL = "Kling-Text2Video-V2.1-Master"

# The kwarg used to pass a reference/source image into a provider step.
# ✅ Confirmed: both the image and video model `param_allowlist`s accept `image` (and
#    `image_url`). `aspect_ratio` and (for video) `duration` are also allow-listed params.
REFERENCE_IMAGE_KWARG = "image"

# Aspect ratios per style (passed through as the `aspect_ratio` step param).
ASPECT = {
    "studio": "1:1",
    "lifestyle": "4:5",
    "onmodel": "4:5",
    "variant": "1:1",
    "video": "1:1",
}

# Providers/models summary for the README / submission. This lists ONLY what the app
# actually calls today (runtime-verified against our GMI account) — no aspirational or
# playground-only models. The `SWAPPABLE_PROVIDERS` note below records the alternatives that
# Genblaze's unified provider API makes drop-in, without claiming they're currently wired.
PROVIDERS = {
    "GMI Cloud (gmicloud-image / gmicloud)": {
        # Source photo → studio / lifestyle / on-model / variant edits.
        "image": ["gemini-3-pro-image-preview"],
        # Hero image → 5s product video (primary + image-to-video fallbacks), plus an
        # optional single-step text → video path.
        "video": ["Kling-Image2Video-V2.1-Master", "pixverse-v5.6-i2v", "wan2.6-r2v",
                  "Kling-Text2Video-V2.1-Master"],
    },
}

# Alternatives that require only a per-step provider swap under Genblaze's unified Pipeline
# API (each ships as its own genblaze-* package). Documented as the app's provider-portability
# story — NOT currently entitled/wired, so they're deliberately kept out of PROVIDERS above.
SWAPPABLE_PROVIDERS = {
    "OpenAI (openai-image)": {"image": ["gpt-image-1"]},
    "Google (google-imagen / google-veo)": {"image": ["imagen"], "video": ["veo"]},
    "Luma (luma)": {"video": ["dream-machine"]},
}
