"""The Auditor — the scheduled integrity agent.

The test that matters most here is the tampered one: an object whose bytes were swapped
under its content address must surface as a named failure. An auditor that only ever
reports green is a status page, not an audit.
"""
import hashlib
import json

import pytest

UID = "dev-user"


@pytest.fixture
def audit_env(monkeypatch):
    """Configure the trigger token BEFORE the client fixture builds (and caches) settings."""
    monkeypatch.setenv("AUDIT_TRIGGER_TOKEN", "test-audit-token")


def _seed_pack(client, png_bytes, title="Mug"):
    """Upload an original and run a mock generation so the library has assets to audit."""
    sku = client.post("/api/skus", json={"title": title}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes(), "image/png")})
    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio", "lifestyle"]})
    return sku


def test_trigger_refuses_without_configuration(client):
    r = client.post("/api/ledger/audit")
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]


def test_trigger_refuses_a_bad_token(audit_env, client):
    assert client.post("/api/ledger/audit").status_code == 403
    r = client.post("/api/ledger/audit", headers={"X-Audit-Token": "wrong"})
    assert r.status_code == 403


def test_no_audit_yet_is_a_distinct_state(client):
    """Absence must not render as success — 404 until a pass has actually run."""
    assert client.get("/api/ledger/audit").status_code == 404


def test_audit_verifies_library_and_ledger(audit_env, client, png_bytes):
    _seed_pack(client, png_bytes)

    r = client.post("/api/ledger/audit", headers={"X-Audit-Token": "test-audit-token"})
    assert r.status_code == 200
    report = r.json()

    # Original + two mock assets share bytes but are distinct records; all must pass.
    assert report["assets_sampled"] >= 1
    assert report["assets_passed"] == report["assets_sampled"]
    assert report["failures"] == []
    assert report["chain_consistent"] is True
    # The audit is the timer-based checkpoint cut, so one exists after the first pass...
    assert report["checkpoint"] is not None
    assert report["ledger_entries"] >= 3
    assert report["caveat"]  # self-audit says what it is

    # ...and the SECOND pass replays the chain against the head the first one published.
    r2 = client.post("/api/ledger/audit", headers={"X-Audit-Token": "test-audit-token"})
    assert r2.json()["checkpoint_reproduced"] is True

    # GET returns the latest pass.
    latest = client.get("/api/ledger/audit").json()
    assert latest["audit_id"] == r2.json()["audit_id"]


def test_audit_report_is_published_under_its_own_hash(audit_env, client, png_bytes):
    from app.storage import get_storage

    _seed_pack(client, png_bytes)
    report = client.post(
        "/api/ledger/audit", headers={"X-Audit-Token": "test-audit-token"}
    ).json()

    assert report["b2_key"] and report["b2_key"].startswith("ledger/audits/")
    stored = get_storage().get_bytes(report["b2_key"])
    # The claim the key makes: the stored bytes hash to the sha256 the API reported.
    assert hashlib.sha256(stored).hexdigest() == report["sha256"]
    # And the stored document is the report (minus the fields only known after storing).
    body = json.loads(stored)
    assert body["audit_id"] == report["audit_id"]
    assert body["assets_sampled"] == report["assets_sampled"]


def test_audit_names_a_tampered_asset(audit_env, client, png_bytes):
    """Swap a stored object's bytes under its content address; the audit must say which."""
    from app.repo import get_repo
    from app.storage import get_storage

    _seed_pack(client, png_bytes)
    # Tamper: overwrite the authentic original's stored object with different bytes.
    victim = next(a for a in get_repo().list_all_assets() if a.get("is_authentic"))
    get_storage().put_bytes(victim["b2_key"], b"not the committed bytes", "image/png")

    report = client.post(
        "/api/ledger/audit", headers={"X-Audit-Token": "test-audit-token"}
    ).json()

    assert report["assets_passed"] < report["assets_sampled"]
    failed_shas = {f["sha256"] for f in report["failures"]}
    assert victim["sha256"] in failed_shas
    named = next(f for f in report["failures"] if f["sha256"] == victim["sha256"])
    assert named["checks"]["bytes_match_hash"] is False
