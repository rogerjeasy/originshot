"""Lifestyle scenes: product composited into believable contexts (parallel fan-out).

Owns the scene prompts; `providers.py` owns how each one reaches a provider.
"""
from __future__ import annotations

import asyncio

from .providers import ImageEditRequest, run_image_edit, with_feedback
from .registry import ASPECT

SCENES = [
    "on a sunlit wooden kitchen counter, soft morning light",
    "on a modern marble bathroom shelf, spa atmosphere",
    "on a minimalist office desk beside a laptop, clean and bright",
    "outdoors on a rustic cafe table, shallow depth of field",
]


def build_scene_prompt(product_desc: str, scene: str, *, brand_suffix: str = "") -> str:
    prompt = (
        f"{product_desc} placed {scene}, realistic shadows and reflections, "
        "lifestyle product photography"
    )
    if brand_suffix:
        prompt += f". Brand style: {brand_suffix}"
    return prompt


def scene_request(
    source_image_uri: str,
    product_desc: str,
    scene: str,
    *,
    brand_suffix: str = "",
    source_sha256: str | None = None,
    source_media_type: str = "image/png",
    feedback: str | None = None,
) -> ImageEditRequest:
    return ImageEditRequest(
        prompt=with_feedback(build_scene_prompt(product_desc, scene, brand_suffix=brand_suffix), feedback),
        source_uri=source_image_uri,
        prompt_name="originshot-lifestyle",
        aspect=ASPECT["lifestyle"],
        source_sha256=source_sha256,
        source_media_type=source_media_type,
    )


def build_scene_pipeline(
    source_image_uri: str, product_desc: str, scene: str, *,
    provider=None, brand_suffix: str = "", adapter=None, source_sha256: str | None = None,
):
    """One scene as an explicit single-provider Pipeline (tests / replay)."""
    from .providers import build_image_pipeline, default_adapter

    adapter = adapter or default_adapter()
    req = scene_request(
        source_image_uri, product_desc, scene, brand_suffix=brand_suffix,
        source_sha256=source_sha256,
    )
    return build_image_pipeline(req, adapter, provider=provider)


async def run_lifestyle(source_image_uri, product_desc, sink, scenes=SCENES,
                        brand_suffix: str = "", *, timeout: int = 300,
                        source_sha256: str | None = None, feedback: str | None = None):
    """Run several scene requests concurrently. Returns a list of (result, adapter).

    Each scene falls across the provider chain independently: one scene exhausting a
    provider's credit must not cancel the others, and a pack where three scenes came from
    one provider and the fourth from another is a *correct* partial outcome, recorded
    per-asset rather than smoothed over. `feedback` refines a retry across all scenes.
    """
    reqs = [
        scene_request(source_image_uri, product_desc, s, brand_suffix=brand_suffix,
                      source_sha256=source_sha256, feedback=feedback)
        for s in scenes
    ]
    return await asyncio.gather(
        *[run_image_edit(r, sink=sink, timeout=timeout) for r in reqs]
    )
