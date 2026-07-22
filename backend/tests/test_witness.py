"""The external witness — OpenTimestamps anchoring of transparency checkpoints (app/witness.py).

Everything here runs with a **fake calendar** (no network): the real behaviour under test is
our stamp/describe/upgrade plumbing and its best-effort degradation, not OpenTimestamps' own
Bitcoin machinery. The conftest pins `WITNESS_ENABLED=false` for the wider suite; these tests
opt back in explicitly.
"""
from __future__ import annotations

import hashlib

import pytest

from app import transparency, witness

# opentimestamps is a project dependency; skip cleanly if a dev env somehow lacks it rather
# than failing the whole suite on an optional-looking import.
pytest.importorskip("opentimestamps")

from opentimestamps.core.notary import (  # noqa: E402
    BitcoinBlockHeaderAttestation, PendingAttestation)
from opentimestamps.core.timestamp import Timestamp  # noqa: E402

_CALENDAR = "https://a.pool.opentimestamps.org"
_BLOCK = 800_000


class _FakeCalendar:
    """Stands in for opentimestamps.calendar.RemoteCalendar with zero network.

    `submit` returns a pending commitment (what a live calendar gives immediately); if
    `confirm` is set, `get_timestamp` returns a Bitcoin attestation (what it gives hours later,
    once a block confirms), so the upgrade path is exercised deterministically.
    """
    confirm = False

    def __init__(self, url: str):
        self.url = url

    def submit(self, digest: bytes, timeout=None) -> Timestamp:
        ts = Timestamp(digest)
        ts.attestations.add(PendingAttestation(self.url))
        return ts

    def get_timestamp(self, commitment: bytes, timeout=None) -> Timestamp:
        if not type(self).confirm:
            raise Exception("not ready")  # noqa: TRY002 — mimics a calendar 404 while pending
        ts = Timestamp(commitment)
        ts.attestations.add(BitcoinBlockHeaderAttestation(_BLOCK))
        return ts


@pytest.fixture
def witnessing(monkeypatch):
    """Turn witnessing on and route it through the fake calendar."""
    monkeypatch.setattr(witness, "is_enabled", lambda: True)
    monkeypatch.setattr(witness, "_make_calendar", _FakeCalendar)
    _FakeCalendar.confirm = False
    yield
    _FakeCalendar.confirm = False


def _hash(data: bytes = b"a checkpoint body") -> str:
    return hashlib.sha256(data).hexdigest()


# ── stamp / describe ──────────────────────────────────────────────────
def test_stamp_returns_proof_and_calendars(witnessing):
    digest = _hash()
    result = witness.stamp(digest)
    assert result is not None
    proof, calendars = result
    assert isinstance(proof, bytes) and len(proof) > 0
    assert calendars  # at least one calendar accepted it

    info = witness.describe(proof)
    assert info["digest"] == digest               # the proof commits to OUR checkpoint hash
    assert info["complete"] is False              # calendar commitment, not yet on Bitcoin
    assert info["bitcoin_block_height"] is None
    assert _CALENDAR in info["pending_calendars"]


def test_stamp_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(witness, "is_enabled", lambda: False)
    assert witness.stamp(_hash()) is None


def test_stamp_survives_a_dead_calendar(witnessing, monkeypatch):
    """Every calendar failing yields None (nothing to claim), never an exception."""
    class _Dead(_FakeCalendar):
        def submit(self, digest, timeout=None):
            raise Exception("calendar down")  # noqa: TRY002

    monkeypatch.setattr(witness, "_make_calendar", _Dead)
    assert witness.stamp(_hash()) is None


def test_describe_of_garbage_is_empty_not_a_crash():
    info = witness.describe(b"not an ots proof")
    assert info == {"pending_calendars": [], "bitcoin_block_height": None,
                    "complete": False, "digest": None}


# ── upgrade ───────────────────────────────────────────────────────────
def test_upgrade_completes_a_pending_proof(witnessing):
    proof, _ = witness.stamp(_hash())
    assert witness.describe(proof)["complete"] is False

    _FakeCalendar.confirm = True                  # the block has now confirmed
    upgraded = witness.upgrade(proof)
    assert upgraded is not None
    info = witness.describe(upgraded)
    assert info["complete"] is True
    assert info["bitcoin_block_height"] == _BLOCK


def test_upgrade_returns_none_while_still_pending(witnessing):
    proof, _ = witness.stamp(_hash())
    _FakeCalendar.confirm = False                 # calendar still has nothing
    assert witness.upgrade(proof) is None


# ── integration through the checkpoint publish path ───────────────────
def _seed_entries(n: int) -> None:
    from app.repo import get_repo

    repo = get_repo()
    for i in range(n):
        repo.append_transparency_entry({
            "subject_sha256": f"{i:064x}", "manifest_hash": "", "kind": "generated",
            "recorded_at": "2026-07-22T00:00:00Z",
        })


def test_publish_checkpoint_anchors_and_serves_the_proof(client, witnessing):
    _seed_entries(3)
    checkpoint = transparency.publish_checkpoint()
    assert checkpoint is not None

    wit = checkpoint.get("witness")
    assert wit is not None
    assert wit["type"] == "opentimestamps"
    assert wit["complete"] is False
    assert wit["pending_calendars"]
    assert wit["proof_key"] and wit["proof_key"].endswith(".ots")

    # The public API exposes the witness on the checkpoint...
    r = client.get("/api/ledger/checkpoint")
    assert r.status_code == 200
    assert r.json()["witness"]["type"] == "opentimestamps"

    # ...and serves the raw proof so anyone can verify it against Bitcoin without trusting us.
    r = client.get("/api/ledger/checkpoint.ots")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    assert witness.describe(r.content)["digest"] == checkpoint["checkpoint_hash"]


def test_publish_checkpoint_without_witness_still_works(client):
    """Witnessing off (the suite default): checkpoints publish with no witness field, never a crash."""
    _seed_entries(3)
    checkpoint = transparency.publish_checkpoint()
    assert checkpoint is not None
    assert checkpoint.get("witness") is None

    r = client.get("/api/ledger/checkpoint.ots")
    assert r.status_code == 404          # nothing to serve, and it says so


def test_auditor_upgrades_the_pending_anchor(client, witnessing):
    _seed_entries(3)
    transparency.publish_checkpoint()            # pending anchor stored
    _FakeCalendar.confirm = True                 # block confirms before the audit runs

    updated = transparency.upgrade_latest_witness()
    assert updated is not None
    assert updated["complete"] is True
    assert updated["bitcoin_block_height"] == _BLOCK

    from app.repo import get_repo
    latest = get_repo().latest_checkpoint()["witness"]
    assert latest["complete"] is True
    assert latest["proof_key"].endswith("-btc.ots")
