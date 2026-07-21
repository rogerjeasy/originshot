"""Studio shot pipeline: source photo → pure-white-background studio image.

This module owns the *prompt* and nothing else. How the reference photo is handed to a
provider — a step param on GMI, `Step.inputs` on OpenAI — belongs to `providers.py`, so that
the same studio prompt runs unchanged on whichever provider is serving.
"""
from __future__ import annotations

from .providers import ImageEditRequest, with_feedback
from .registry import ASPECT


def build_studio_prompt(product_desc: str, *, brand_suffix: str = "") -> str:
    prompt = (
        f"Professional e-commerce product photograph of {product_desc}. "
        "Pure white seamless background (#FFFFFF), soft even studio lighting, centered, "
        "sharp focus, true-to-life color, no props, no text."
    )
    if brand_suffix:
        prompt += f" Brand tone: {brand_suffix}."
    return prompt


def studio_request(
    source_image_uri: str,
    product_desc: str,
    *,
    brand_suffix: str = "",
    aspect: str | None = None,
    source_sha256: str | None = None,
    source_media_type: str = "image/png",
    feedback: str | None = None,
) -> ImageEditRequest:
    """The provider-neutral studio request. `feedback` refines a retry (see qa.feedback_*)."""
    return ImageEditRequest(
        prompt=with_feedback(build_studio_prompt(product_desc, brand_suffix=brand_suffix), feedback),
        source_uri=source_image_uri,
        prompt_name="originshot-studio",
        aspect=aspect or ASPECT["studio"],
        source_sha256=source_sha256,
        source_media_type=source_media_type,
    )


def build_studio_pipeline(
    source_image_uri: str,
    product_desc: str,
    *,
    provider=None,
    brand_suffix: str = "",
    aspect: str | None = None,
    adapter=None,
    source_sha256: str | None = None,
):
    """Return a Genblaze Pipeline that produces a studio shot on a single provider.

    Retained for replay, tests and any caller that wants one explicit provider rather than
    the fallback chain. `provider` may be injected for testing; `adapter` selects whose
    parameter contract to build for (default: the first configured provider).
    """
    from .providers import build_image_pipeline, default_adapter

    adapter = adapter or default_adapter()
    req = studio_request(
        source_image_uri, product_desc, brand_suffix=brand_suffix, aspect=aspect,
        source_sha256=source_sha256,
    )
    return build_image_pipeline(req, adapter, provider=provider)
