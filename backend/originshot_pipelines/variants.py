"""Variant fan-out: color / angle variations from one base photo.

Owns the prompts; `providers.py` owns how each reaches a provider.
"""
from __future__ import annotations

import asyncio

from .providers import ImageEditRequest, run_image_edit
from .registry import ASPECT


def build_variant_prompts(product_desc: str, colors=(), angles=()) -> list[str]:
    base = "studio product photo on pure white background, soft lighting"
    prompts = [f"{product_desc} in {c} color, {base}" for c in colors]
    prompts += [f"{product_desc}, {a} view, {base}" for a in angles]
    return prompts


def variant_request(
    source_image_uri: str,
    prompt: str,
    *,
    brand_suffix: str = "",
    source_sha256: str | None = None,
    source_media_type: str = "image/png",
) -> ImageEditRequest:
    if brand_suffix:
        prompt += f". Brand style: {brand_suffix}"
    return ImageEditRequest(
        prompt=prompt,
        source_uri=source_image_uri,
        prompt_name="originshot-variant",
        aspect=ASPECT["variant"],
        source_sha256=source_sha256,
        source_media_type=source_media_type,
    )


def build_variant_pipeline(source_image_uri: str, prompt: str, *, provider=None,
                           brand_suffix: str = "", adapter=None,
                           source_sha256: str | None = None):
    """One variant as an explicit single-provider Pipeline (tests / replay)."""
    from .providers import build_image_pipeline, default_adapter

    adapter = adapter or default_adapter()
    req = variant_request(
        source_image_uri, prompt, brand_suffix=brand_suffix, source_sha256=source_sha256,
    )
    return build_image_pipeline(req, adapter, provider=provider)


async def run_variants(source_image_uri, product_desc, sink, colors=(), angles=(),
                       brand_suffix: str = "", *, timeout: int = 300,
                       source_sha256: str | None = None):
    """Run the sweep concurrently. Returns a list of (result, adapter) — see run_lifestyle."""
    prompts = build_variant_prompts(product_desc, colors, angles)
    reqs = [
        variant_request(source_image_uri, p, brand_suffix=brand_suffix,
                        source_sha256=source_sha256)
        for p in prompts
    ]
    return await asyncio.gather(
        *[run_image_edit(r, sink=sink, timeout=timeout) for r in reqs]
    )
