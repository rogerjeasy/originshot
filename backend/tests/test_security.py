import pytest
from fastapi import HTTPException

from app.security import validate_and_normalize_image


def test_rejects_non_image():
    with pytest.raises(HTTPException):
        validate_and_normalize_image(b"definitely not an image")


def test_normalizes_png_and_strips_metadata(png_bytes):
    out = validate_and_normalize_image(png_bytes(size=(20, 12)))
    assert out["mime_type"] == "image/png"
    assert out["width"] == 20 and out["height"] == 12
    assert len(out["sha256"]) == 64


def test_auth_required_without_dev_bypass(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_BYPASS", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    assert c.get("/api/skus").status_code == 401
    get_settings.cache_clear()  # restore for later tests
