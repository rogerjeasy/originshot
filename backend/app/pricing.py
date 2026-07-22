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
# Voiceover: OpenAI TTS reports no cost through the SDK (Step.cost_usd is None), so this is a
# list-price CEILING the run settles at, labelled `estimate` (see billable_cost). A ~60-word
# narration is a few hundred characters; at tts-1 ($15/1M chars) that is well under a cent and
# at gpt-4o-mini-tts still ~1¢, so $0.03 comfortably bounds one narration plus the script hop.
AUDIO_UNIT_USD = 0.03

# How many outputs each style produces. Must track originshot_pipelines: lifestyle runs a
# scene set, variants sweeps VARIANT_COLORS x VARIANT_ANGLES.
_OUTPUTS: dict[Style, int] = {
    Style.studio: 1,
    Style.lifestyle: 2,
    Style.onmodel: 1,
    Style.variant: 2,
    Style.video: 1,
    Style.voiceover: 1,
}

_UNIT: dict[Style, float] = {
    Style.studio: IMAGE_UNIT_USD,
    Style.lifestyle: IMAGE_UNIT_USD,
    Style.onmodel: IMAGE_UNIT_USD,
    Style.variant: IMAGE_UNIT_USD,
    Style.video: VIDEO_UNIT_USD,
    Style.voiceover: AUDIO_UNIT_USD,
}

# Rough wall-clock seconds per style, used only to show an ETA next to the live timer.
# Image styles run one provider call each; video is a different order of magnitude.
_ETA_SECONDS: dict[Style, int] = {
    Style.studio: 25,
    Style.lifestyle: 45,
    Style.onmodel: 30,
    Style.variant: 45,
    Style.video: 150,
    # Script chat hop (can 429/retry) + a short TTS synthesis.
    Style.voiceover: 20,
}


# ── Settlement: what a finished run actually costs ────────────────────
# Providers that genuinely cost nothing. The dev mock fabricates assets by copying the upload;
# charging for that would be inventing revenue. The ffmpeg compositor muxes the narration onto
# the hero video with a local binary — no provider bill — so the narrated video is free too
# (its inputs, the audio and the video, were each already billed on their own step).
FREE_PROVIDERS = frozenset({"mock-dev", "ffmpeg-compositor"})


def unit_usd(style: Style) -> float:
    """List price for ONE output of `style` — the per-asset unit, not the per-style total."""
    return _UNIT.get(style, IMAGE_UNIT_USD)


def billable_cost(assets: list[dict]) -> tuple[float, str]:
    """What a finished run should be settled at, and where that number came from.

    Returns ``(total_usd, source)`` with source in ``provider`` / ``estimate`` / ``mixed`` /
    ``none``.

    **A missing cost is not a free run.** `Step.cost_usd` is authoritative when the provider
    reports it, but not every provider does: genblaze-core 0.3.0 removed OpenAI pricing, so
    every `openai-dalle` step returns ``cost_usd=None``. Summing only the non-None values —
    which is what this code used to do — would settle a real, billed OpenAI pack at $0.00,
    refund the user's entire credit hold, and report $0 spend in analytics. The generation
    happened and OpenAI charged for it; only *our* visibility of the price is missing.

    So an unpriced asset from a real provider falls back to its list price and the result is
    labelled ``estimate`` (or ``mixed``) rather than being passed off as provider-billed.
    That distinction is the same one the module docstring opens with, carried through to
    settlement: the number is still honest, and it no longer claims to be a provider's bill.
    Only :data:`FREE_PROVIDERS` contributes a real zero.
    """
    total = 0.0
    saw_provider = saw_estimate = False
    for asset in assets:
        cost = asset.get("cost_usd")
        if cost is not None:
            total += float(cost)
            saw_provider = True
            continue
        if (asset.get("provider") or "") in FREE_PROVIDERS:
            continue
        try:
            style = Style(asset.get("style"))
        except ValueError:
            style = Style.studio
        total += unit_usd(style)
        saw_estimate = True

    if saw_provider and saw_estimate:
        source = "mixed"
    elif saw_provider:
        source = "provider"
    elif saw_estimate:
        source = "estimate"
    else:
        source = "none"
    return round(total, 4), source


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
