"""Generation must never fabricate assets outside the test suite.

The mock copies the user's own upload and labels it `provider="mock-dev"`. Those rows are
indistinguishable from real generations in analytics, the admin dashboard and the ledger,
so the app refuses to run rather than serving them. These tests pin that down — if someone
later flips the default, they fail.
"""
import pytest

from app.config import get_settings
from app.generation import (
    GenerationUnavailable,
    generate_assets,
    generation_mode,
    missing_generation_requirements,
)


@pytest.fixture
def unconfigured(monkeypatch):
    """The app's real default: no provider keys and mocking not permitted."""
    get_settings.cache_clear()
    monkeypatch.setenv("MOCK_GENERATION_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_mock_is_disabled_by_default():
    """The field default must be off.

    Checked on the model field rather than an instance: this suite sets
    MOCK_GENERATION_ENABLED in the environment, which any instantiation would pick up.
    """
    from app.config import Settings

    assert Settings.model_fields["mock_generation_enabled"].default is False


def test_mode_is_unconfigured_not_mock_when_keys_are_absent(unconfigured):
    assert generation_mode() == "unconfigured"


def test_missing_requirements_are_named(unconfigured):
    missing = missing_generation_requirements()
    assert any("GMI_API_KEY" in m for m in missing)
    assert any("B2" in m for m in missing)


@pytest.mark.anyio
async def test_generate_assets_refuses_rather_than_fabricating(unconfigured):
    sku = {"id": "s", "title": "X", "description": None}
    original = {"sha256": "orig", "b2_key": "assets/o.png", "mime_type": "image/png",
                "width": 10, "height": 10}

    with pytest.raises(GenerationUnavailable) as exc:
        await generate_assets("u", sku, original, ["studio"], storage=None)
    assert "GMI_API_KEY" in str(exc.value)


def test_generate_endpoint_returns_503_when_unconfigured(client, png_bytes, unconfigured):
    """The refusal reaches the user as an actionable 503, before any credit is held."""
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes(), "image/png")})

    res = client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})
    assert res.status_code == 503
    assert "unavailable" in res.json()["detail"].lower()

    # Nothing was charged: the refusal happens before the hold, so the ledger is untouched.
    from app.repo import get_repo

    assert [e for e in get_repo().list_ledger("dev-user") if e["kind"] == "hold"] == []


def test_health_reports_unconfigured_generation_as_not_ok(unconfigured):
    from app.health import check_generation

    status = check_generation()
    assert status["ok"] is False
    assert status["error"] == "not_configured"
    assert status["missing"]


def test_health_flags_mock_mode_loudly(client):
    """When the suite's mock IS on, health must say the assets are fabricated."""
    from app.health import check_generation

    status = check_generation()
    assert status["mode"] == "mock"
    assert "MOCK" in status["warning"]
