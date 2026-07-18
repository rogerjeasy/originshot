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


def test_user_cannot_reach_another_users_sku(client, png_bytes):
    """IDOR: knowing another user's SKU id must not grant read or write access.

    Ownership is enforced per-request from the authenticated uid (never client input), so
    every owner-scoped route must 404 for a second user — not 403, which would confirm the
    id exists.
    """
    from app.auth import CurrentUser, get_current_user
    from app.main import app as fastapi_app

    # User A (the dev-bypass user) creates a SKU and uploads an original.
    sku = client.post("/api/skus", json={"title": "A's mug"}).json()
    client.post(
        f"/api/skus/{sku['id']}/upload", files={"file": ("p.png", png_bytes(), "image/png")}
    )

    # Become user B, holding A's SKU id.
    fastapi_app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        uid="user-b", email="b@example.com", email_verified=True
    )
    try:
        assert client.get(f"/api/skus/{sku['id']}").status_code == 404
        assert client.get(f"/api/skus/{sku['id']}/assets").status_code == 404
        assert client.post(
            f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]}
        ).status_code == 404
        assert client.post(
            f"/api/skus/{sku['id']}/export", json={"marketplaces": []}
        ).status_code == 404
        assert client.post(
            f"/api/skus/{sku['id']}/upload", files={"file": ("p.png", png_bytes(), "image/png")}
        ).status_code == 404
        # B's own listing must not leak A's products.
        assert client.get("/api/skus").json() == []
    finally:
        fastapi_app.dependency_overrides.clear()


def test_auth_required_without_dev_bypass(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_BYPASS", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    assert c.get("/api/skus").status_code == 401
    get_settings.cache_clear()  # restore for later tests
