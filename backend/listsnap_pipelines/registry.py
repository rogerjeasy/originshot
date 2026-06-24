"""Central provider/model configuration — the single source of truth.

This is also the canonical list of providers/models for the hackathon submission.

✅ WEEK-1 VERIFIED against the installed SDK (genblaze 0.4.0, genblaze-core 0.3.2,
   genblaze-gmicloud 0.3.1). Model IDs come from `genblaze_gmicloud.models`
   (`build_image_registry()` / `build_video_registry()`); the reference-image kwarg and
   aspect/duration params were confirmed against each model's `param_allowlist`.
"""
from __future__ import annotations

# ── Image editing (source photo → studio / lifestyle / on-model / variant) ──────────
# GMI Cloud's image catalog is *edit / image-to-image* focused — which fits our core
# "one authentic photo → many marketplace shots" use-case exactly. Verified IDs:
#   bria-eraser · bria-genfill · reve-edit-20250915 · reve-edit-fast-20251030
#   reve-remix-20250915 · reve-remix-fast-20251030 · seededit-3-0-i2i-250628
IMAGE_EDIT_MODEL = "seededit-3-0-i2i-250628"          # SeedEdit 3.0 image-to-image
IMAGE_EDIT_FALLBACKS = ["reve-edit-20250915", "reve-edit-fast-20251030"]

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

# Providers/models summary for the README / submission. Keys are the genblaze provider
# registry ids (see `genblaze.discover_providers()`); fallback providers ship as separate
# genblaze-* packages and are selected per step, not as `fallback_models` of a GMI step.
PROVIDERS = {
    "GMI Cloud (gmicloud-image / gmicloud / gmicloud-audio)": {
        "image": ["seededit-3-0-i2i-250628", "reve-edit-20250915", "reve-edit-fast-20251030",
                  "reve-remix-20250915", "bria-genfill", "bria-eraser"],
        "video": ["Kling-Image2Video-V2.1-Master", "Kling-Text2Video-V2.1-Master",
                  "Veo3", "Veo3-Fast", "pixverse-v5.6-i2v", "wan2.6-r2v"],
    },
    "Google (google-imagen / google-veo)": {"image": ["imagen"], "video": ["veo"]},
    "Luma (luma)": {"video": ["dream-machine"]},
    "Runway (runway)": {"video": ["gen-family"]},
    "NVIDIA (nvidia-image / nvidia-video / nvidia-audio / nvidia-chat)": {
        "image": ["nvidia"], "video": ["nvidia"],
    },
    "Decart (decart / decart-image)": {"image": ["decart"], "video": ["decart"]},
}
