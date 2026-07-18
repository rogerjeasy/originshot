"""Studio shot pipeline: source photo → pure-white-background studio image."""
from __future__ import annotations

from .registry import (
    ASPECT,
    IMAGE_EDIT_FALLBACKS,
    IMAGE_EDIT_MODEL,
    REFERENCE_IMAGE_KWARG,
)


def build_studio_pipeline(
    source_image_uri: str,
    product_desc: str,
    *,
    provider=None,
    brand_suffix: str = "",
    aspect: str | None = None,
):
    """Return a Genblaze Pipeline that produces a studio shot.

    `provider` may be injected for testing; otherwise the GMI Cloud image provider is used.
    """
    from genblaze_core import Modality, Pipeline

    if provider is None:
        from genblaze_gmicloud import GMICloudImageProvider

        provider = GMICloudImageProvider()

    prompt = (
        f"Professional e-commerce product photograph of {product_desc}. "
        "Pure white seamless background (#FFFFFF), soft even studio lighting, centered, "
        "sharp focus, true-to-life color, no props, no text."
    )
    if brand_suffix:
        prompt += f" Brand tone: {brand_suffix}."
    step_kwargs = {
        "model": IMAGE_EDIT_MODEL,
        "prompt": prompt,
        "modality": Modality.IMAGE,
        "aspect_ratio": aspect or ASPECT["studio"],
        "fallback_models": IMAGE_EDIT_FALLBACKS,
        REFERENCE_IMAGE_KWARG: source_image_uri,
    }
    return Pipeline("originshot-studio").step(provider, **step_kwargs)
