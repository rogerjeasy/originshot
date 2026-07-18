"""Lifestyle scenes: product composited into believable contexts (parallel fan-out)."""
from __future__ import annotations

import asyncio

from .registry import (
    ASPECT,
    IMAGE_EDIT_FALLBACKS,
    IMAGE_EDIT_MODEL,
    REFERENCE_IMAGE_KWARG,
)

SCENES = [
    "on a sunlit wooden kitchen counter, soft morning light",
    "on a modern marble bathroom shelf, spa atmosphere",
    "on a minimalist office desk beside a laptop, clean and bright",
    "outdoors on a rustic cafe table, shallow depth of field",
]


def build_scene_pipeline(
    source_image_uri: str, product_desc: str, scene: str, *, provider=None, brand_suffix: str = ""
):
    from genblaze_core import Modality, Pipeline

    if provider is None:
        from genblaze_gmicloud import GMICloudImageProvider

        provider = GMICloudImageProvider()

    prompt = (
        f"{product_desc} placed {scene}, realistic shadows and reflections, "
        "lifestyle product photography"
    )
    if brand_suffix:
        prompt += f". Brand style: {brand_suffix}"
    step_kwargs = {
        "model": IMAGE_EDIT_MODEL,
        "prompt": prompt,
        "modality": Modality.IMAGE,
        "aspect_ratio": ASPECT["lifestyle"],
        "fallback_models": IMAGE_EDIT_FALLBACKS,
        REFERENCE_IMAGE_KWARG: source_image_uri,
    }
    return Pipeline("listsnap-lifestyle").step(provider, **step_kwargs)


async def run_lifestyle(source_image_uri, product_desc, sink, scenes=SCENES, brand_suffix: str = ""):
    """Run several scene pipelines concurrently and return their results."""
    pipes = [
        build_scene_pipeline(source_image_uri, product_desc, s, brand_suffix=brand_suffix)
        for s in scenes
    ]
    return await asyncio.gather(*[p.arun(sink=sink, timeout=300) for p in pipes])
