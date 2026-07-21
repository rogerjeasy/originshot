"""Ed25519 signing of transparency checkpoints, audit reports and dispute reports.

The property under test is authorship: a signed checkpoint verifies against the repo-committed
public key, a tampered one does not, and — the honesty invariant — nothing is *marked* signed
when no key is configured. A throwaway key is generated per test rather than using the real
one, so the suite never depends on production secrets.
"""
from __future__ import annotations

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from app import signing  # noqa: E402


@pytest.fixture
def test_key(monkeypatch):
    """Install a throwaway signing key and point the module's published key at it."""
    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    ).hex()
    pub = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()

    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "signing_private_key", seed)
    monkeypatch.setattr(signing, "PUBLISHED_PUBLIC_KEY_HEX", pub)
    monkeypatch.setattr(signing, "KEY_ID", pub[:16])
    return pub


def test_sign_and_verify_roundtrip(test_key):
    digest = "a" * 64
    sig = signing.sign_hex(digest)
    assert sig["algorithm"] == "ed25519"
    assert sig["key_id"] == test_key[:16]
    assert signing.verify_hex(digest, sig) is True


def test_a_tampered_digest_does_not_verify(test_key):
    sig = signing.sign_hex("a" * 64)
    assert signing.verify_hex("b" * 64, sig) is False


def test_a_signature_from_a_different_key_does_not_verify(test_key):
    # Sign with an unrelated key, verify against the published one.
    other = Ed25519PrivateKey.generate()
    forged = other.sign(("a" * 64).encode("ascii")).hex()
    assert signing.verify_hex("a" * 64, {"algorithm": "ed25519", "key_id": "x", "signature": forged}) is False


def test_signing_is_disabled_without_a_key(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "signing_private_key", None)
    assert signing.is_configured() is False
    assert signing.sign_hex("a" * 64) is None
    assert signing.verify_configuration() == {"ok": True, "state": "disabled"}


def test_configuration_flags_a_key_that_does_not_match_the_repo(monkeypatch):
    """A running key whose public half isn't the committed one can't produce verifiable sigs."""
    from app.config import get_settings

    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    ).hex()
    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "signing_private_key", seed)
    # PUBLISHED_PUBLIC_KEY_HEX left as the real repo key → mismatch.
    status = signing.verify_configuration()
    assert status["ok"] is False and status["state"] == "key_mismatch"


def test_the_real_repo_key_matches_its_constant():
    """Guards against committing a public key whose private half we no longer hold in dev.

    Only runs when a real signing key is present in the environment (skipped in CI/hermetic
    runs, where the key is blanked); when it does run, it catches a public-key/​private-key
    drift before it ships.
    """
    from app.config import get_settings

    get_settings.cache_clear()
    if not get_settings().signing_private_key:
        pytest.skip("no signing key configured in this environment")
    assert signing.public_key_hex() == signing.PUBLISHED_PUBLIC_KEY_HEX


# ── Checkpoint signing, end to end ─────────────────────────────────────
def test_published_checkpoint_is_signed_and_verifies(client, test_key):
    """A checkpoint cut with a key configured carries a signature over its own hash."""
    from app import transparency
    from app.repo import get_repo

    repo = get_repo()
    for i in range(2):
        repo.append_transparency_entry({
            "subject_sha256": f"{i:064x}", "manifest_hash": "", "kind": "generated",
            "recorded_at": "2026-07-21T00:00:00Z",
        })
    cp = transparency.publish_checkpoint()
    assert cp is not None
    assert cp["signature"]["algorithm"] == "ed25519"
    assert signing.verify_hex(cp["checkpoint_hash"], cp["signature"]) is True


def test_checkpoint_is_unsigned_when_no_key(client, monkeypatch):
    from app import transparency
    from app.config import get_settings
    from app.repo import get_repo

    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "signing_private_key", None)
    repo = get_repo()
    repo.append_transparency_entry({
        "subject_sha256": "0" * 64, "manifest_hash": "", "kind": "generated",
        "recorded_at": "2026-07-21T00:00:00Z",
    })
    cp = transparency.publish_checkpoint()
    assert cp is not None
    assert "signature" not in cp  # never marked signed when it isn't


def test_verify_ledger_script_verifies_a_real_signature(test_key):
    """The standalone verifier's vendored check must agree with the app's signer."""
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "verify_ledger.py"
    spec = importlib.util.spec_from_file_location("verify_ledger", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Point the script's committed key at the throwaway test key.
    mod.PUBLIC_KEY_HEX = test_key

    digest = "c" * 64
    sig = signing.sign_hex(digest)
    assert mod.verify_signature(digest, sig) is True
    assert mod.verify_signature("d" * 64, sig) is False
    assert mod.verify_signature(digest, None) is None
