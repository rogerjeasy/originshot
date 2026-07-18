"""Health endpoint must report dependency truth, not env-var presence.

Regression coverage for a real outage (2026-07-18): the Render Secret File holding the
Firebase service account was never uploaded, so Firebase Admin could not initialize — yet
`/healthz` reported `firebase: true` because FIREBASE_PROJECT_ID happened to be set, and
every authenticated route returned an opaque 500 that surfaced in browsers as a CORS error.
"""
import pytest


def test_health_reports_per_dependency_status(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    # In the hermetic test env nothing external is configured, so the app is honestly
    # degraded rather than falsely "ok".
    assert body["status"] == "degraded"
    assert set(body["checks"]) == {"firebase", "b2", "generation"}
    assert body["checks"]["firebase"] == {"ok": False, "error": "not_configured"}
    assert body["checks"]["b2"]["ok"] is False
    assert "firebase" in body["degraded"] and "b2" in body["degraded"]
    assert body["depth"] == "shallow"


def test_health_stays_200_when_degraded(client):
    """Render restart-loops a service whose health check fails — degradation goes in the body."""
    assert client.get("/healthz").status_code == 200


def test_generation_check_does_not_claim_funded(client):
    """`configured` must never be reported as `working` — a provider can still 402."""
    gen = client.get("/healthz").json()["checks"]["generation"]
    assert gen["mode"] in {"genblaze", "mock"}
    assert "not checked" in gen["verified"]


def test_health_reports_firebase_failure_type(monkeypatch):
    """A configured-but-broken Firebase must report the exception type, not `ok: true`."""
    from app import health
    from app.config import get_settings

    monkeypatch.setenv("FIREBASE_PROJECT_ID", "some-project")
    get_settings.cache_clear()
    try:
        def _boom():
            raise FileNotFoundError("/etc/secrets/firebase-admin.json")

        monkeypatch.setattr("app.firebase.get_db", _boom)
        result = health.check_firebase()
        # Exception *type* only — diagnostic, but leaks no path on a public endpoint.
        assert result == {"ok": False, "error": "FileNotFoundError"}
    finally:
        get_settings.cache_clear()


def test_auth_returns_503_not_500_when_firebase_broken(monkeypatch):
    """Firebase init failure is a config problem (503), never an unhandled 500.

    The 500 path emitted no CORS headers, so the browser reported a misleading CORS error
    and hid the real cause.
    """
    from fastapi.testclient import TestClient

    from app.config import get_settings

    monkeypatch.setenv("AUTH_DEV_BYPASS", "false")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "some-project")
    get_settings.cache_clear()
    try:
        def _boom():
            raise FileNotFoundError("/etc/secrets/firebase-admin.json")

        monkeypatch.setattr("app.firebase.get_db", _boom)

        from app.main import app

        r = TestClient(app, raise_server_exceptions=False).get(
            "/api/skus", headers={"Authorization": "Bearer sometoken"}
        )
        assert r.status_code == 503
        assert r.json()["detail"] == "Auth backend unavailable"
    finally:
        get_settings.cache_clear()


def test_missing_token_still_401_not_503(monkeypatch):
    """A missing token is rejected before Firebase is ever touched."""
    from fastapi.testclient import TestClient

    from app.config import get_settings

    monkeypatch.setenv("AUTH_DEV_BYPASS", "false")
    get_settings.cache_clear()
    try:
        from app.main import app

        assert TestClient(app).get("/api/skus").status_code == 401
    finally:
        get_settings.cache_clear()
