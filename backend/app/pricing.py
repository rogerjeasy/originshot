"""Per-style cost model — used to reserve credit *before* a run and to explain spend after.

Two different numbers matter here and conflating them is how a credit system starts lying:

  * **estimate** — what we quote up front, before any provider has been called. Derived from
    this table. Used to reject a run the user can't afford (402) and to show "this pack will
    cost about $X" in the UI.
  * **actual** — `Step.cost_usd`, reported by Genblaze once the provider has actually billed.
    This is what we debit. It is authoritative and can differ from the estimate (fallbacks,
    retries, a variant sweep that produced fewer images than asked).

The estimate is deliberately the *ceiling*: `variant` quotes the full sweep and `lifestyle`
the full scene set, so a user is never surprised by a debit larger than their quote. When the
actual comes in lower we refund the difference rather than pocketing it (see credits.settle).

Rates are list prices for the models in originshot_pipelines as of 2026-07. They are an
estimate, not a bill from the provider — `ESTIMATE_ONLY` is surfaced in the API so the UI can
say so out loud instead of implying we know the provider's ledger.
"""
from __future__ import annotations

from .models import Style

ESTIMATE_ONLY = "estimated from list prices; actual cost is read from the provider's Step.cost_usd"

# USD per generated output. Public because analytics derives its labeled estimate from the
# same list prices the quote uses — two cost tables would drift apart.
IMAGE_UNIT_USD = 0.04
VIDEO_UNIT_USD = 0.50

# How many outputs each style produces. Must track originshot_pipelines: lifestyle runs a
# scene set, variants sweeps VARIANT_COLORS x VARIANT_ANGLES.
_OUTPUTS: dict[Style, int] = {
    Style.studio: 1,
    Style.lifestyle: 2,
    Style.onmodel: 1,
    Style.variant: 2,
    Style.video: 1,
}

_UNIT: dict[Style, float] = {
    Style.studio: IMAGE_UNIT_USD,
    Style.lifestyle: IMAGE_UNIT_USD,
    Style.onmodel: IMAGE_UNIT_USD,
    Style.variant: IMAGE_UNIT_USD,
    Style.video: VIDEO_UNIT_USD,
}

# Rough wall-clock seconds per style, used only to show an ETA next to the live timer.
# Image styles run one provider call each; video is a different order of magnitude.
_ETA_SECONDS: dict[Style, int] = {
    Style.studio: 25,
    Style.lifestyle: 45,
    Style.onmodel: 30,
    Style.variant: 45,
    Style.video: 150,
}


def estimate_style(style: Style) -> float:
    """Ceiling cost for one style, in USD."""
    return round(_OUTPUTS.get(style, 1) * _UNIT.get(style, IMAGE_UNIT_USD), 4)


def estimate_styles(styles: list[Style] | list[str]) -> float:
    """Ceiling cost for a whole pack, in USD."""
    total = sum(estimate_style(Style(s)) for s in styles)
    return round(total, 4)


def eta_seconds(styles: list[Style] | list[str]) -> int:
    """Rough wall-clock estimate for a pack. Styles run sequentially, so this sums."""
    return sum(_ETA_SECONDS.get(Style(s), 30) for s in styles)


def breakdown(styles: list[Style] | list[str]) -> list[dict]:
    """Per-style quote, for the UI to show before the user commits to a run."""
    out = []
    for s in styles:
        style = Style(s)
        out.append({
            "style": style.value,
            "outputs": _OUTPUTS.get(style, 1),
            "estimate_usd": estimate_style(style),
            "eta_seconds": _ETA_SECONDS.get(style, 30),
        })
    return out
