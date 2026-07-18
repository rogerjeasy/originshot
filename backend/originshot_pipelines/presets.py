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


_WHITE_LUMA = 235  # 0–255 luminance above which a pixel reads as white background


def _product_bbox(img) -> tuple[int, int, int, int] | None:
    """Bounding box of the non-white content, at full resolution (or None if blank).

    Measured on a 1/8 downscale — within a pixel of the full-size answer — then mapped
    back with a small pad so anti-aliased product edges aren't clipped.
    """
    from PIL import Image

    small = img.resize((max(1, img.width // 8), max(1, img.height // 8)), Image.BILINEAR)
    px = small.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(small.height):
        for x in range(small.width):
            r, g, b = px[x, y][:3]
            if 0.2126 * r + 0.7152 * g + 0.0722 * b < _WHITE_LUMA:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    sx = img.width / small.width
    sy = img.height / small.height
    pad_x = max(2, round(img.width * 0.01))
    pad_y = max(2, round(img.height * 0.01))
    return (
        max(0, round(min(xs) * sx) - pad_x),
        max(0, round(min(ys) * sy) - pad_y),
        min(img.width, round((max(xs) + 1) * sx) + pad_x),
        min(img.height, round((max(ys) + 1) * sy) + pad_y),
    )


def render_for_preset(data: bytes, preset: Preset) -> tuple[bytes, str]:
    """Render image `data` to `preset`'s exact dimensions. Returns (bytes, extension).

    Two strategies, driven by the preset's background rule:

    * ``background == "white"`` (Amazon/eBay main images) — trim the master to the
      *product's* bounding box, then *contain* it on a pure white canvas scaled so the
      product occupies ``min_fill_ratio`` of the frame. The trim matters: without it a
      master with generous white margin ships a rendition whose product fills ~half of
      what the listing rule demands (caught by `compliance.studio_scorecard`, which
      measures fill on the delivered file). Never crops into the product itself.
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
            bbox = _product_bbox(img)
            product = img.crop(bbox) if bbox else img
            fit = (min(target_w / product.width, target_h / product.height)
                   * preset.min_fill_ratio)
            new_size = (max(1, round(product.width * fit)),
                        max(1, round(product.height * fit)))
            canvas = Image.new("RGB", (target_w, target_h), (255, 255, 255))
            canvas.paste(
                product.resize(new_size, Image.LANCZOS),
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
