"""Marketplace compliance checks — prove the renditions meet the listing rules.

`presets.render_for_preset` *aims* at each channel's rules; this module *measures* the
result, because "we resized it" and "Amazon won't suppress it" are different claims. The
checks mirror the real rejection reasons:

  * exact pixel dimensions (every channel),
  * white background on the main image (Amazon, eBay) — measured on the border strip,
  * product fill ratio (white-background channels) — measured as the larger side of the
    product bounding box over the frame, the way "product fills 85% of the image" is
    actually policed,
  * a non-blank frame for cover-cropped channels (a black or empty crop is a silent
    failure the dimension check can't see).

The scorecard runs on the same bytes the export ships, so a green check is a statement
about the delivered file, not about intent.
"""
from __future__ import annotations

import io

from .presets import Preset, render_for_preset
from .qa import _luma, _WHITE_LUMA

WHITE_BORDER_MIN = 0.97   # renditions put product on a synthetic white canvas — stricter
                          # than generation QA, because here white is constructed, not lit
FILL_TOLERANCE = 0.05     # rendering rounds; a hair under the preset target still passes
_BORDER_FRAC = 0.02


def check_rendition(data: bytes, preset: Preset) -> dict:
    """Measure one rendered file against its channel's rules."""
    from PIL import Image

    checks: list[dict] = []
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")

        checks.append({
            "name": "dimensions",
            "passed": (img.width, img.height) == (preset.width, preset.height),
            "value": f"{img.width}x{img.height}",
            "threshold": f"{preset.width}x{preset.height}",
        })

        if preset.background == "white":
            checks.append(_white_border(img))
            checks.append(_linear_fill(img, preset.min_fill_ratio))
        else:
            checks.append(_not_blank(img))

    return {"passed": all(c["passed"] for c in checks), "checks": checks}


def studio_scorecard(master: bytes, marketplaces: list[str] | None = None) -> list[dict]:
    """Render the master through each channel's preset and measure the result.

    This is the pre-export answer to "will my main image be accepted?" — same render code,
    same checks, no ZIP required.
    """
    from .presets import PRESETS, get_preset

    out: list[dict] = []
    for market in (marketplaces or list(PRESETS)):
        preset = get_preset(market)
        if not preset:
            continue
        try:
            rendered, _ext = render_for_preset(master, preset)
            report = check_rendition(rendered, preset)
        except Exception as exc:  # noqa: BLE001 — a failed render is itself the finding
            report = {"passed": False,
                      "checks": [{"name": "render", "passed": False, "detail": str(exc)}]}
        out.append({"marketplace": market, "preset": preset.name, **report})
    return out


def _white_border(img) -> dict:
    w, h = img.width, img.height
    bw = max(1, round(w * _BORDER_FRAC))
    bh = max(1, round(h * _BORDER_FRAC))
    px = img.load()
    total = white = 0
    for y in range(h):
        xs = range(w) if (y < bh or y >= h - bh) else list(range(bw)) + list(range(w - bw, w))
        for x in xs:
            total += 1
            if _luma(px[x, y]) >= _WHITE_LUMA:
                white += 1
    frac = white / total if total else 0.0
    return {"name": "white_background", "passed": frac >= WHITE_BORDER_MIN,
            "value": round(frac, 3), "threshold": WHITE_BORDER_MIN}


def _linear_fill(img, min_fill: float) -> dict:
    """Larger side of the product bbox over the frame — how 'fills X%' is policed."""
    from PIL import Image

    small = img.resize((max(1, img.width // 8), max(1, img.height // 8)), Image.BILINEAR)
    px = small.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(small.height):
        for x in range(small.width):
            if _luma(px[x, y]) < _WHITE_LUMA:
                xs.append(x)
                ys.append(y)
    if not xs:
        return {"name": "product_fill", "passed": False, "value": 0.0,
                "threshold": min_fill, "detail": "no product found on canvas"}
    linear = max((max(xs) - min(xs) + 1) / small.width,
                 (max(ys) - min(ys) + 1) / small.height)
    return {"name": "product_fill", "passed": linear >= min_fill - FILL_TOLERANCE,
            "value": round(linear, 3), "threshold": min_fill}


def _not_blank(img) -> dict:
    """Cover-cropped channels: catch an all-black or all-white crop the dimension check
    can't see. Mean-luminance bounds only — flat but valid scenes (a plain backdrop)
    must not be flagged, so no texture requirement."""
    from PIL import Image

    small = img.resize((32, 32), Image.BILINEAR)
    px = small.load()
    lumas = [_luma(px[x, y]) for y in range(32) for x in range(32)]
    mean = sum(lumas) / len(lumas)
    ok = 5 < mean < 250
    return {"name": "not_blank", "passed": ok,
            "value": f"mean={mean:.0f}", "threshold": "5<mean<250"}
