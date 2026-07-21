"""Ed25519 signatures for the transparency log and dispute reports.

Every other integrity claim in this project is a *hash*: a checkpoint, an audit report, a
dispute PDF each carries the SHA-256 of its own contents, so a copy can be proven unaltered
against a published record. What a bare hash cannot establish is **authorship** — anyone who
can write to the bucket could publish a checkpoint, and nothing in the bytes says *this
instance* issued it. That was the single largest caveat stamped across the transparency
docs: "no issuing keypair … proves integrity against a published record, not authorship."

This module closes it. The instance holds an Ed25519 private key (a 32-byte seed in
`SIGNING_PRIVATE_KEY`); it signs the content hash each artefact already computes, and the
matching **public key is committed to the repository** (`PUBLISHED_PUBLIC_KEY_HEX`). A third
party who cloned the repo from GitHub therefore holds the verification key independently of
our servers, and can check a checkpoint's signature offline —
`scripts/verify_ledger.py` does exactly that. Forging a checkpoint now requires the private
key, not merely write access to the bucket.

Design decisions that keep the claim honest:

  * **Sign the hash, not a re-serialisation.** Each artefact already commits to its contents
    with a canonical SHA-256 (`checkpoint_hash`, the audit report's `sha256`, the dispute
    PDF's `sha256`). Signing that exact hex string means the signature covers precisely what
    the hash covers — no second, subtly-different canonicalisation to disagree with it.
  * **The public key is repo-committed, not self-described.** The signature travels with the
    artefact, but the *key* a verifier trusts comes from the source tree (or a pinned copy),
    never from the same response as the signature. A checkpoint that carried its own key
    would let a forger swap both and "verify" against themselves.
  * **Graceful, and it says so.** With no key configured the artefacts publish unsigned and
    nothing claims otherwise — `signed` is simply absent, exactly as `retained_until` is
    absent when Object Lock isn't applied. A best-effort log must never fail a paid
    generation because a key wasn't set.

What it still does not do, stated as plainly as the rest: a single key proves *an* issuer,
not *the honest* issuer, and it does not solve the split-view problem (that needs independent
witnesses). It removes "anyone with bucket write access can forge history"; it does not turn
a single-operator log into a gossiped one.
"""
from __future__ import annotations

import logging

from .config import get_settings

log = logging.getLogger("originshot.signing")

# The public half of the signing keypair, committed to the repository on purpose: a verifier
# obtains it from the source tree (independently of the API), so a signature checked against
# it binds the artefact to the holder of the matching private seed. Rotating the key means
# changing this constant in a commit — which is itself a public, dated record of the rotation.
PUBLISHED_PUBLIC_KEY_HEX = "8d9ef557d70d7637580aceed82a1c396a1984ed18f1d4dd2551f854ff039e355"

# Short, human-quotable fingerprint of the published key (first 16 hex of the key itself).
KEY_ID = PUBLISHED_PUBLIC_KEY_HEX[:16]


def _load_private():
    """Return an Ed25519 private key from the configured seed, or None if unset/invalid."""
    seed_hex = get_settings().signing_private_key
    if not seed_hex:
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex.strip()))
    except Exception as exc:  # noqa: BLE001 — a bad key disables signing, never crashes a run
        log.warning("signing key present but unusable (%s); publishing unsigned", type(exc).__name__)
        return None


def is_configured() -> bool:
    return _load_private() is not None


def public_key_hex() -> str | None:
    """The public key derived from the configured private seed, hex-encoded.

    Returned so an operator can confirm the running key matches the repo-committed one — a
    mismatch means signatures this instance produces won't verify against the published key,
    which `verify_configuration()` surfaces loudly at startup rather than silently at audit
    time.
    """
    priv = _load_private()
    if priv is None:
        return None
    from cryptography.hazmat.primitives import serialization

    return priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()


def sign_hex(digest_hex: str) -> dict | None:
    """Sign a content hash (hex string). Returns a signature record, or None if unconfigured.

    The record is what gets attached to the artefact::

        {"algorithm": "ed25519", "key_id": <16-hex>, "signature": <128-hex>}

    `signature` is over the ASCII bytes of `digest_hex` — the same string the artefact's own
    hash field holds — so a verifier signs/checks the identical value with no ambiguity.
    """
    priv = _load_private()
    if priv is None or not digest_hex:
        return None
    try:
        sig = priv.sign(digest_hex.encode("ascii"))
        return {"algorithm": "ed25519", "key_id": KEY_ID, "signature": sig.hex()}
    except Exception as exc:  # noqa: BLE001 — never fail publication over a signing error
        log.warning("signing failed (%s); publishing unsigned", type(exc).__name__)
        return None


def verify_hex(digest_hex: str, signature: dict | None, *, public_key_hex: str | None = None) -> bool:
    """Verify a signature record against a digest and a public key (default: the repo key).

    Used by tests and available to any caller; the standalone verifier vendors an equivalent
    so it needs none of this package.
    """
    if not signature or not digest_hex:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(public_key_hex or PUBLISHED_PUBLIC_KEY_HEX)
        )
        pub.verify(bytes.fromhex(signature["signature"]), digest_hex.encode("ascii"))
        return True
    except Exception:  # noqa: BLE001 — any failure (bad sig, bad key, wrong digest) is "invalid"
        return False


def verify_configuration() -> dict:
    """Non-destructive status for /healthz: is signing active, and does the key match the repo?"""
    if not get_settings().signing_private_key:
        return {"ok": True, "state": "disabled"}
    running = public_key_hex()
    if running is None:
        return {"ok": False, "state": "misconfigured", "reason": "signing key is unusable"}
    if running != PUBLISHED_PUBLIC_KEY_HEX:
        return {"ok": False, "state": "key_mismatch",
                "reason": "running key does not match the repo-published public key"}
    return {"ok": True, "state": "active", "key_id": KEY_ID}
