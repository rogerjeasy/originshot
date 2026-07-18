"""Variant fan-out: color / angle variations from one base photo."""
from __future__ import annotations

import asyncio

from .registry import (
    ASPECT,
    IMAGE_EDIT_FALLBACKS,
    IMAGE_EDIT_MODEL,
    REFERENCE_IMAGE_KWARG,
)


def build_variant_prompts(product_desc: str, colors=(), angles=()) -> list[str]:
    base = "studio product photo on pure white background, soft lighting"
    prompts = [f"{product_desc} in {c} color, {base}" for c in colors]
    prompts += [f"{product_desc}, {a} view, {base}" for a in angles]
    return prompts


def build_variant_pipeline(source_image_uri: str, prompt: str, *, provider=None, brand_suffix: str = ""):
    from genblaze_core import Modality, Pipeline

    if provider is None:
        from genblaze_gmicloud import GMICloudImageProvider

        provider = GMICloudImageProvider()

    if brand_suffix:
        prompt += f". Brand style: {brand_suffix}"
    step_kwargs = {
        "model": IMAGE_EDIT_MODEL,
        "prompt": prompt,
        "modality": Modality.IMAGE,
        "aspect_ratio": ASPECT["variant"],
        "fallback_models": IMAGE_EDIT_FALLBACKS,
        REFERENCE_IMAGE_KWARG: source_image_uri,
    }
    return Pipeline("originshot-variant").step(provider, **step_kwargs)


async def run_variants(source_image_uri, product_desc, sink, colors=(), angles=(), brand_suffix: str = ""):
    prompts = build_variant_prompts(product_desc, colors, angles)
    pipes = [build_variant_pipeline(source_image_uri, p, brand_suffix=brand_suffix) for p in prompts]
    return await asyncio.gather(*[p.arun(sink=sink, timeout=300) for p in pipes])
