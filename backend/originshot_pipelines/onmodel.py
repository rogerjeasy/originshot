"""On-model shots: product shown on a person (apparel/accessories/wearables)."""
from __future__ import annotations

from .registry import (
    ASPECT,
    IMAGE_EDIT_FALLBACKS,
    IMAGE_EDIT_MODEL,
    REFERENCE_IMAGE_KWARG,
)


def build_onmodel_pipeline(
    source_image_uri: str, product_desc: str, *, provider=None, brand_suffix: str = ""
):
    from genblaze_core import Modality, Pipeline

    if provider is None:
        from genblaze_gmicloud import GMICloudImageProvider

        provider = GMICloudImageProvider()

    prompt = (
        f"{product_desc} worn/used by a natural-looking model, soft studio lighting, "
        "clean neutral background, realistic fit and scale, e-commerce on-model photography"
    )
    if brand_suffix:
        prompt += f". Brand style: {brand_suffix}"
    step_kwargs = {
        "model": IMAGE_EDIT_MODEL,
        "prompt": prompt,
        "modality": Modality.IMAGE,
        "aspect_ratio": ASPECT["onmodel"],
        "fallback_models": IMAGE_EDIT_FALLBACKS,
        REFERENCE_IMAGE_KWARG: source_image_uri,
    }
    return Pipeline("originshot-onmodel").step(provider, **step_kwargs)
