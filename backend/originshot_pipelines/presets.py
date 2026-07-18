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


def render_for_preset(data: bytes, preset: Preset) -> tuple[bytes, str]:
    """Render image `data` to `preset`'s exact dimensions. Returns (bytes, extension).

    Two strategies, driven by the preset's background rule:

    * ``background == "white"`` (Amazon/eBay main images) — *contain* the product on a pure
      white canvas, scaled so it occupies ``min_fill_ratio`` of the frame. Never crops, so
      the product is always whole, which is exactly what those listing rules require.
    * ``background == "any"`` (Etsy/Shopify/Social) — *cover* the frame and centre-crop, so
      lifestyle scenes fill the tile edge to edge with no letterboxing.

    Output is JPEG (quality 90): every marketplace accepts it and it keeps packs small.
    NOTE: re-encoding necessarily drops the embedded provenance manifest, which is why the
    export also ships byte-exact verifiable masters — see `app/api/export.py`.
    """
    import io

    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        target_w, target_h = preset.width, preset.height

        if preset.background == "white":
            fit = min(target_w / img.width, target_h / img.height) * preset.min_fill_ratio
            new_size = (max(1, round(img.width * fit)), max(1, round(img.height * fit)))
            canvas = Image.new("RGB", (target_w, target_h), (255, 255, 255))
            canvas.paste(
                img.resize(new_size, Image.LANCZOS),
                ((target_w - new_size[0]) // 2, (target_h - new_size[1]) // 2),
            )
        else:
            scale = max(target_w / img.width, target_h / img.height)
            scaled = img.resize(
                (max(target_w, round(img.width * scale)), max(target_h, round(img.height * scale))),
                Image.LANCZOS,
            )
            left, top = (scaled.width - target_w) // 2, (scaled.height - target_h) // 2
            canvas = scaled.crop((left, top, left + target_w, top + target_h))

        out = io.BytesIO()
        canvas.save(out, format="JPEG", quality=90, optimize=True)
        return out.getvalue(), ".jpg"


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
