"""Settlement when a provider reports no cost (app/pricing.py::billable_cost).

genblaze-core 0.3.0 removed OpenAI pricing, so every `openai-dalle` step comes back with
`cost_usd=None`. The previous settlement summed only non-None costs, which meant a real,
billed OpenAI pack settled at $0.00 — full credit refund, $0 in analytics, and a spend
figure that quietly stopped being true. These tests pin the distinction the module is built
on: *unpriced* is not *free*, and an estimate must never be reported as a provider's bill.
"""
from __future__ import annotations

from app import pricing
from app.models import Style


def _asset(style: Style, provider: str, cost: float | None) -> dict:
    return {"style": style.value, "provider": provider, "cost_usd": cost}


def test_provider_reported_costs_are_authoritative():
    assets = [
        _asset(Style.studio, "gmicloud-image", 0.04),
        _asset(Style.lifestyle, "gmicloud-image", 0.04),
    ]
    total, source = pricing.billable_cost(assets)
    assert total == 0.08
    assert source == "provider"


def test_unpriced_provider_settles_at_list_price_not_zero():
    """The generation happened and OpenAI billed for it — only our visibility is missing."""
    assets = [_asset(Style.studio, "openai-dalle", None)] * 2
    total, source = pricing.billable_cost(assets)

    assert total == round(2 * pricing.unit_usd(Style.studio), 4)
    assert total > 0                       # the bug this file exists for
    assert source == "estimate"            # and it does not claim to be a provider's bill


def test_mixed_run_is_labelled_mixed():
    """A pack served partly by each provider — the honest label for a blended number."""
    assets = [
        _asset(Style.studio, "gmicloud-image", 0.04),
        _asset(Style.lifestyle, "openai-dalle", None),
    ]
    total, source = pricing.billable_cost(assets)
    assert total == round(0.04 + pricing.unit_usd(Style.lifestyle), 4)
    assert source == "mixed"


def test_the_dev_mock_really_is_free():
    """The mock copies the user's own upload. Charging for that would invent revenue."""
    total, source = pricing.billable_cost([_asset(Style.studio, "mock-dev", None)])
    assert total == 0.0
    assert source == "none"


def test_video_is_estimated_at_the_video_rate():
    """Per-asset units, not a flat image rate — video is an order of magnitude apart."""
    total, _ = pricing.billable_cost([_asset(Style.video, "openai-dalle", None)])
    assert total == pricing.VIDEO_UNIT_USD


def test_no_assets_settles_at_zero():
    """A job that produced nothing refunds its whole hold — nobody pays for a failure."""
    assert pricing.billable_cost([]) == (0.0, "none")


def test_unknown_style_falls_back_to_the_image_rate_rather_than_crashing():
    """Settlement runs in a `finally`; it must not raise on an unexpected style value."""
    total, source = pricing.billable_cost(
        [{"style": "not-a-style", "provider": "openai-dalle", "cost_usd": None}]
    )
    assert total == pricing.IMAGE_UNIT_USD
    assert source == "estimate"
