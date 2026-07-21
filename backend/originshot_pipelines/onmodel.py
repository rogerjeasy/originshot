"""On-model shots: product shown on a person (apparel/accessories/wearables).

Owns the prompt; `providers.py` owns how it reaches a provider.
"""
from __future__ import annotations

from .providers import ImageEditRequest, with_feedback
from .registry import ASPECT


def build_onmodel_prompt(product_desc: str, *, brand_suffix: str = "") -> str:
    prompt = (
        f"{product_desc} worn/used by a natural-looking model, soft studio lighting, "
        "clean neutral background, realistic fit and scale, e-commerce on-model photography"
    )
    if brand_suffix:
        prompt += f". Brand style: {brand_suffix}"
    return prompt


def onmodel_request(
    source_image_uri: str,
    product_desc: str,
    *,
    brand_suffix: str = "",
    source_sha256: str | None = None,
    source_media_type: str = "image/png",
    feedback: str | None = None,
) -> ImageEditRequest:
    return ImageEditRequest(
        prompt=with_feedback(build_onmodel_prompt(product_desc, brand_suffix=brand_suffix), feedback),
        source_uri=source_image_uri,
        prompt_name="originshot-onmodel",
        aspect=ASPECT["onmodel"],
        source_sha256=source_sha256,
        source_media_type=source_media_type,
    )


def build_onmodel_pipeline(
    source_image_uri: str, product_desc: str, *, provider=None, brand_suffix: str = "",
    adapter=None, source_sha256: str | None = None,
):
    """One on-model shot as an explicit single-provider Pipeline (tests / replay)."""
    from .providers import build_image_pipeline, default_adapter

    adapter = adapter or default_adapter()
    req = onmodel_request(
        source_image_uri, product_desc, brand_suffix=brand_suffix,
        source_sha256=source_sha256,
    )
    return build_image_pipeline(req, adapter, provider=provider)
