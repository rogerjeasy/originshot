"""Hero product video: image → 5-second clip (with provider fallback)."""
from __future__ import annotations

from .registry import ASPECT, REFERENCE_IMAGE_KWARG, VIDEO_FALLBACKS, VIDEO_MODEL


def build_hero_video(hero_image_uri: str, product_desc: str, *, provider=None, brand_suffix: str = ""):
    """Image-to-video from an already-generated, provenance-anchored hero image."""
    from genblaze_core import Modality, Pipeline

    if provider is None:
        from genblaze_gmicloud import GMICloudVideoProvider

        provider = GMICloudVideoProvider()

    prompt = (
        "slow turntable rotation with a gentle camera push-in, premium product reveal, "
        "clean background"
    )
    if brand_suffix:
        prompt += f". Brand tone: {brand_suffix}"
    step_kwargs = {
        "model": VIDEO_MODEL,
        "prompt": prompt,
        "modality": Modality.VIDEO,
        "aspect_ratio": ASPECT["video"],
        "duration": 5,
        "fallback_models": VIDEO_FALLBACKS,
        REFERENCE_IMAGE_KWARG: hero_image_uri,
    }
    return Pipeline("listsnap-hero-video").step(provider, **step_kwargs)


def build_text_to_video(product_desc: str):
    """Single-step text → video (no source photo needed).

    GMI Cloud has no text→image model, so a true text→image→video chain would require a
    text→image provider (e.g. Google Imagen) for the first step. The main product flow
    already demonstrates chaining + lineage (studio image → hero video via parent_sha256),
    so this helper stays a real, runnable single-step text→video pipeline.
    """
    from genblaze_core import Modality, Pipeline
    from genblaze_gmicloud import GMICloudVideoProvider

    from .registry import TEXT2VIDEO_MODEL

    return Pipeline("listsnap-text-to-video").step(
        GMICloudVideoProvider(),
        model=TEXT2VIDEO_MODEL,
        prompt=f"{product_desc}, premium product reveal, slow turntable, clean background",
        modality=Modality.VIDEO,
        duration=5,
        aspect_ratio=ASPECT["video"],
    )
