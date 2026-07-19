"""Central provider/model configuration — the single source of truth.

This is also the canonical list of providers/models for the hackathon submission.

✅ VERIFIED against the installed SDK — re-verified 2026-07-19 on genblaze 0.4.3,
   genblaze-core 0.3.6, genblaze-gmicloud 0.3.3 (the GitHub "v0.5.0" release; the umbrella
   publishes as 0.4.3 — `genblaze==0.5.0` does not exist on PyPI).
   Model IDs come from `genblaze_gmicloud.models`
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
#
#   🔁 RE-VERIFIED on genblaze-gmicloud 0.3.3 (2026-07-19) — the validation is *inverted*
#   for our account, which is why only a real generation settles entitlement:
#     validate_model("seededit-3-0-i2i-250628")  -> ok_authoritative   (but 404s on submit)
#     validate_model("gemini-3-pro-image-preview") -> unknown_permissive (our WORKING model)
#     validate_model("totally-made-up-model-xyz")  -> unknown_permissive (identical verdict)
#     validate_model("reve-edit-20250915")         -> not_found
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

# ── Chat / vision-language (QA evaluator + listing copy) ────────────────────────────
# ✅ RUNTIME-VERIFIED (2026-07-18) with real completions against GMI's OpenAI-compatible
#   endpoint — latency-probed under load, because catalog presence proves nothing here:
#   * `x-ai/grok-4.5` — vision QA. Scored on four REAL product pairs (2026-07-19), not a
#     toy image: same product/different shot → 9, same product hue-rotated → 3, different
#     object → 0, identical → 10, in 3.8–8.8s. That hue-rotated 3 is the whole point: it
#     catches an AI silently recolouring the product, which deterministic checks cannot see.
#     Its verdicts cite specifics ("two-tone speckled glaze, dark horizontal line").
#   * `moonshotai/Kimi-K2.5` — REJECTED for QA despite answering a toy 64px solid-red PNG
#     correctly: on real product photos it burns the entire token budget and returns EMPTY
#     content (completion_tokens == max_tokens, reasoning_tokens == 0, at 500/1500/3000).
#     Passing a toy vision probe does not mean a model can do the real job.
#   * `tencent/Hy3` — REJECTED: fast, but scored two photos of the SAME mug as 0
#     ("completely different product"). A confidently wrong evaluator is worse than none.
#   * `zai-org/GLM-5.1-FP8` — listing copy: 31s for a full channel of copy, zero hidden
#     reasoning tokens, clean JSON. Text-only (rejects image input — politely, inside a
#     HTTP 200).
#   Rejected with evidence: GLM-5.2-FP8 burns the whole token budget on hidden reasoning
#   (1200/1200 reasoning ⇒ empty content) and silently ACCEPTS images it cannot see;
#   Kimi-K2.6 is fast but doesn't hold the JSON contract; GLM-4.7/K2-Instruct-0905 404/400
#   despite being in the catalog; gemma-4/gpt-4o* 429 "all endpoints overloaded". Nothing
#   may hard-depend on this endpoint — every consumer degrades gracefully.
GMI_CHAT_BASE_URL = "https://api.gmi-serving.com/v1"
QA_VISION_MODEL = "x-ai/grok-4.5"
LISTING_MODEL = "zai-org/GLM-5.1-FP8"

# ── Resolve: the dispute-evidence comparison (originshot_pipelines/resolve.py) ───────
# Reuses QA_VISION_MODEL rather than introducing an unproven one — a dispute report is the
# last place to gamble on a model. Re-benchmarked 2026-07-19 for the *dispute* question,
# which is harder than QA's: the second image is a real-world photo of a delivered item, and
# the model must separate photography differences from product differences, then enumerate
# condition damage. Live runs against real product photos, 10-19s each:
#
#   same mug, studio -> lifestyle shot        ->  9/10   "matching two-tone glaze, dual dark
#                                                          horizontal lines, handle shape"
#   same mug, held in hands (hard positive)   ->  9/10   correctly ignores hands/crop/lighting
#   same mug, ARRIVED DAMAGED (scratch+chip)  ->  9/10   AND listed both defects:
#                                                          "triangular mark on inner rim",
#                                                          "diagonal line/scratch on lower body"
#   wrong item shipped (green bottle)         ->  0/10   "entirely different products"
#
# The damaged row is the one that matters, and it is why the prompt asks for score and
# condition differences SEPARATELY. A single "same product?" score cannot express "yes, the
# right item, and it arrived broken" — which is the most common real dispute, and precisely
# the failure the project's opening scenario describes (an AI quietly removing a scratch).
# Thresholds live in resolve.py (MATCH_PASS / MATCH_FAIL), deliberately wider than QA's.

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
