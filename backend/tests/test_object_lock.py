"""B2 Object Lock for the transparency ledger (app/storage.py, transparency, auditor).

The feature is a trust claim, so these tests pin the two properties that make the claim
honest rather than hollow:

  1. when a retention is configured, the retention headers actually reach `put_object`; and
  2. when the lock CAN'T be applied (key/bucket not ready), the object still publishes but the
     caller learns it was NOT retained — so nothing is ever *described* as immutable when it
     is not.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import config
from app.storage import B2Storage, LocalStorage


class _FakeS3:
    """Records put_object calls; can be told to reject Object Lock like an unprepared bucket."""

    def __init__(self, *, reject_lock: bool = False):
        self.calls: list[dict] = []
        self.reject_lock = reject_lock

    def put_object(self, **kwargs):
        if self.reject_lock and "ObjectLockMode" in kwargs:
            raise RuntimeError("Access Denied: key lacks writeFileRetentions")
        self.calls.append(kwargs)
        return {}


def _b2(fake: _FakeS3) -> B2Storage:
    s = B2Storage()
    s._client = fake  # bypass real boto3
    return s


def test_put_immutable_sends_retention_headers_when_configured():
    fake = _FakeS3()
    retained = _b2(fake).put_immutable(
        "ledger/checkpoints/x.json", b"{}", "application/json",
        retain_days=365, mode="COMPLIANCE",
    )
    assert isinstance(retained, datetime)
    assert retained > datetime.now(timezone.utc)
    call = fake.calls[-1]
    assert call["ObjectLockMode"] == "COMPLIANCE"
    assert call["ObjectLockRetainUntilDate"] == retained  # ~365 days out


def test_put_immutable_without_retention_is_a_plain_put():
    fake = _FakeS3()
    retained = _b2(fake).put_immutable("k", b"data", retain_days=0)
    assert retained is None
    assert "ObjectLockMode" not in fake.calls[-1]


def test_put_immutable_falls_back_unlocked_when_lock_is_rejected():
    """The decisive honesty property: a rejected lock still publishes, but returns None.

    None is what makes the caller omit `retained_until`, so an object is never labelled
    immutable when the bucket/key couldn't actually lock it.
    """
    fake = _FakeS3(reject_lock=True)
    retained = _b2(fake).put_immutable("k", b"data", "application/json", retain_days=365)
    assert retained is None
    # It still got written — just without the lock params.
    assert len(fake.calls) == 1
    assert "ObjectLockMode" not in fake.calls[0]


def test_local_storage_has_no_lock_and_says_so():
    s = LocalStorage()
    assert s.put_immutable("k", b"x", retain_days=365) is None
    assert s.object_lock_status()["capable"] is False


# ── Publish sites record retained_until only on a real lock ────────────
class _FakeStorage:
    def __init__(self, retained):
        self._retained = retained
        self.puts: list[str] = []

    def put_immutable(self, key, data, content_type=None, *, retain_days=0, mode="COMPLIANCE"):
        self.puts.append(key)
        return self._retained

    def put_bytes(self, key, data, content_type=None):
        self.puts.append(key)
        return key


@pytest.fixture
def _ledger_repo(monkeypatch):
    """A fresh in-memory repo with a couple of entries, for checkpoint publication."""
    import app.repo as repo_mod

    config.get_settings.cache_clear()
    repo_mod._repo = None
    repo = repo_mod.get_repo()
    for i in range(2):
        repo.append_transparency_entry({
            "subject_sha256": f"{i:064x}", "manifest_hash": "", "kind": "generated",
            "recorded_at": "2026-07-20T00:00:00Z",
        })
    return repo


def test_checkpoint_records_retained_until_when_locked(monkeypatch, _ledger_repo):
    from app import transparency

    retain = datetime(2027, 7, 20, tzinfo=timezone.utc)
    import app.storage as storage_mod
    monkeypatch.setattr(storage_mod, "get_storage", lambda: _FakeStorage(retain))
    monkeypatch.setattr(config.get_settings(), "b2_object_lock_days", 365)

    cp = transparency.publish_checkpoint()
    assert cp is not None
    assert cp["retained_until"] == "2027-07-20T00:00:00Z"


def test_checkpoint_omits_retained_until_when_not_locked(monkeypatch, _ledger_repo):
    """No lock applied (fallback) → no immutability claim on the checkpoint."""
    from app import transparency

    import app.storage as storage_mod
    monkeypatch.setattr(storage_mod, "get_storage", lambda: _FakeStorage(None))
    cp = transparency.publish_checkpoint()
    assert cp is not None
    assert "retained_until" not in cp


# ── Health self-check states ──────────────────────────────────────────
def test_health_reports_disabled_when_retention_is_off(monkeypatch):
    from app import health

    s = config.get_settings()
    monkeypatch.setattr(s, "b2_key_id", "k")
    monkeypatch.setattr(s, "b2_app_key", "a")
    monkeypatch.setattr(s, "b2_bucket", "b")
    monkeypatch.setattr(s, "b2_object_lock_days", 0)
    out = health.check_object_lock()
    assert out["state"] == "disabled" and out["ok"] is True


def test_health_reports_misconfigured_when_key_cannot_lock(monkeypatch):
    """Retention is asked for but the key can't apply it — a real, surfaced misconfiguration."""
    from app import health
    import app.storage as storage_mod

    s = config.get_settings()
    monkeypatch.setattr(s, "b2_key_id", "k")
    monkeypatch.setattr(s, "b2_app_key", "a")
    monkeypatch.setattr(s, "b2_bucket", "b")
    monkeypatch.setattr(s, "b2_object_lock_days", 365)

    class _Incapable:
        def object_lock_status(self):
            return {"capable": False, "reason": "key lacks writeFileRetentions capability"}

    monkeypatch.setattr(storage_mod, "get_storage", lambda: _Incapable())
    out = health.check_object_lock()
    assert out["state"] == "misconfigured" and out["ok"] is False
    assert "writeFileRetentions" in out["reason"]
