"""Marketplace presets: target dimensions and background rules per channel."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    name: str
    width: int
    height: int
    background: str          # "white" | "any"
    min_fill_ratio: float    # product should fill at least this fraction of the frame
    notes: str = ""


PRESETS: dict[str, Preset] = {
    "amazon": Preset("Amazon main", 2000, 2000, "white", 0.85,
                     "Pure white background; product fills ~85% of frame."),
    "etsy": Preset("Etsy", 2000, 1600, "any", 0.6, "Lifestyle context rewarded."),
    "shopify": Preset("Shopify", 2048, 2048, "any", 0.7, "Consistent square aspect across catalog."),
    "ebay": Preset("eBay", 1600, 1600, "white", 0.7, "Clean background; 1600px min."),
    "social": Preset("Social 4:5", 1080, 1350, "any", 0.6, "Portrait 4:5 for feeds."),
}


def get_preset(marketplace: str) -> Preset | None:
    return PRESETS.get(marketplace.lower())


# Marketplaces whose main image is square.
_SQUARE = {"amazon", "ebay", "shopify"}


def studio_aspect_for(marketplaces: list[str]) -> str:
    """Choose the studio aspect ratio from the selected marketplaces (default 1:1)."""
    if not marketplaces:
        return "1:1"
    if any(m in _SQUARE for m in marketplaces):
        return "1:1"
    if "social" in marketplaces:
        return "4:5"
    return "1:1"


def preset_targets(marketplaces: list[str]) -> list[dict]:
    """Per-marketplace export targets (dimensions / background) for the selected channels."""
    chosen = marketplaces or list(PRESETS.keys())
    out: list[dict] = []
    for m in chosen:
        p = get_preset(m)
        if p:
            out.append({
                "marketplace": m,
                "name": p.name,
                "width": p.width,
                "height": p.height,
                "background": p.background,
                "notes": p.notes,
            })
    return out
