"""Recording assets into the transparency log, and publishing checkpoints to B2.

The chain mathematics live in `originshot_pipelines/transparency.py` as pure functions; this
module is the app-side plumbing: when an entry is written, when a checkpoint is cut, and
where it is published.

**Publishing to B2 is the point, not a storage detail.** A checkpoint kept only in our own
database is worth nothing — the party you are asking to trust the log is the same party who
could rewrite it. Writing checkpoints to object storage under a content-addressed key gives
them an existence independent of the application's own data, and B2's own object listing
becomes a second record of when each head was published.

But B2 is still *our* bucket, so publishing there alone is not an external witness. The real
one lives in `app/witness.py`: every checkpoint hash is anchored into **Bitcoin** via
OpenTimestamps — a party the operator does not control — so a published head cannot be
backdated or silently rewritten, and (with the Ed25519 signature) a split view becomes
detectable the moment two parties compare. What remains open is gossip between independent
witnesses; see the module docstring next door for exactly what that does and does not buy.

**Appends are best-effort by contract.** A ledger outage must never fail a generation the
provider has already billed for. The consequence is stated plainly wherever the log is
surfaced: an asset absent from the log may simply never have been recorded, so presence is
the load-bearing claim and absence is not evidence.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from originshot_pipelines import transparency as chain

from .config import get_settings
from .repo import get_repo

log = logging.getLogger("originshot.transparency")

CHECKPOINT_PREFIX = "ledger/checkpoints"


def _now() -> str:
    # Second precision, explicit Z: the value is hashed, so it must serialise identically
    # everywhere. `datetime.isoformat()` varies on microseconds and offset spelling.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_asset(asset: dict) -> dict | None:
    """Append one asset to the log. Returns the entry, or None if it couldn't be recorded.

    Subject is the asset's content hash — the same identifier `/verify` resolves — so a log
    entry and a file in someone's hands are talkable-about as the same thing.
    """
    settings = get_settings()
    if not settings.transparency_enabled:
        return None
    sha = asset.get("sha256")
    if not sha:
        return None

    if asset.get("is_authentic"):
        kind = "original"
    elif asset.get("replay_of"):
        # A replay is a generation whose spec came from an earlier manifest — logged as its
        # own kind so "regenerated twelve times until the scratch disappeared" is exactly
        # the pattern this log makes visible.
        kind = "replay"
    else:
        kind = "generated"
    try:
        entry = get_repo().append_transparency_entry({
            "subject_sha256": sha,
            "manifest_hash": asset.get("manifest_key") or asset.get("manifest_hash"),
            "kind": kind,
            "recorded_at": _now(),
        })
    except Exception as exc:  # noqa: BLE001 — never fail a paid generation over the log
        log.warning("transparency append failed for %s: %s", sha, exc)
        return None

    maybe_publish_checkpoint(entry["seq"] + 1)
    return entry


def maybe_publish_checkpoint(size: int) -> dict | None:
    """Cut a checkpoint every `transparency_checkpoint_every` entries."""
    every = max(1, get_settings().transparency_checkpoint_every)
    if size % every != 0:
        return None
    return publish_checkpoint()


def publish_checkpoint() -> dict | None:
    """Commit to the log's current head and publish it to B2.

    The checkpoint is stored under its own size *and* recorded in the repo, so the published
    object and our own record can be compared — a divergence between them is itself a signal
    worth being able to see.
    """
    repo = get_repo()
    try:
        size = repo.transparency_size()
        if size == 0:
            return None
        entries = repo.list_transparency_entries()
        head = entries[-1]["entry_hash"]
        checkpoint = chain.build_checkpoint(size=size, head=head, issued_at=_now())
        # Sign the checkpoint's own hash. The signature attests that THIS instance issued this
        # head — verifiable offline against the repo-committed public key. Absent when no key
        # is configured; never fatal (a paid generation must not fail because a key is unset).
        from . import signing

        sig = signing.sign_hex(checkpoint["checkpoint_hash"])
        if sig is not None:
            checkpoint = {**checkpoint, "signature": sig}
    except Exception as exc:  # noqa: BLE001
        log.warning("checkpoint build failed: %s", exc)
        return None

    try:
        from .storage import get_storage

        import json

        settings = get_settings()
        key = f"{CHECKPOINT_PREFIX}/{size:012d}-{checkpoint['checkpoint_hash'][:12]}.json"
        # Publish under Object Lock when configured. `retained_until` is an annotation added
        # AFTER the checkpoint hash is computed (like b2_key) — it describes where and how the
        # commitment was stored, not the commitment itself. It is set ONLY when a real lock was
        # applied, so a checkpoint that claims immutability always has it.
        retained_until = get_storage().put_immutable(
            key,
            json.dumps(checkpoint, sort_keys=True, indent=2).encode("utf-8"),
            "application/json",
            retain_days=settings.b2_object_lock_days,
            mode=settings.b2_object_lock_mode,
        )
        checkpoint = {**checkpoint, "b2_key": key}
        if retained_until is not None:
            checkpoint["retained_until"] = retained_until.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as exc:  # noqa: BLE001 — an unpublished checkpoint is still a record
        log.warning("checkpoint publish to B2 failed: %s", exc)

    # External witness: anchor the checkpoint hash into Bitcoin via OpenTimestamps — the one
    # anchor whose trust root is not our own infrastructure. Best-effort, exactly like signing
    # and Object Lock: a checkpoint publishes with no witness if the calendars are unreachable,
    # and the Auditor upgrades the pending proof to a Bitcoin attestation on a later pass.
    try:
        from . import witness

        stamped = witness.stamp(checkpoint["checkpoint_hash"])
        if stamped is not None:
            proof_bytes, calendars = stamped
            proof_key = f"{CHECKPOINT_PREFIX}/{size:012d}-{checkpoint['checkpoint_hash'][:12]}.ots"
            try:
                from .storage import get_storage

                settings = get_settings()
                get_storage().put_immutable(
                    proof_key, proof_bytes, "application/octet-stream",
                    retain_days=settings.b2_object_lock_days,
                    mode=settings.b2_object_lock_mode,
                )
            except Exception as exc:  # noqa: BLE001 — the anchor is real even if the copy fails
                log.warning("witness proof publish to B2 failed: %s", exc)
                proof_key = None
            checkpoint = {**checkpoint, "witness": {
                "type": witness.WITNESS_TYPE,
                "proof_key": proof_key,
                "pending_calendars": calendars,
                "bitcoin_block_height": None,
                "complete": False,
            }}
    except Exception as exc:  # noqa: BLE001 — never fail a checkpoint over the witness
        log.warning("witness stamping failed: %s", exc)

    try:
        repo.save_checkpoint(checkpoint)
    except Exception as exc:  # noqa: BLE001
        log.warning("checkpoint save failed: %s", exc)
    log.info("transparency checkpoint at size=%d head=%s", size, checkpoint["head"][:12])
    return checkpoint


def upgrade_latest_witness() -> dict | None:
    """Complete the latest checkpoint's pending Bitcoin anchor, if it's ready.

    Stamping only gets a *calendar commitment*; the Bitcoin attestation appears hours later,
    once a block confirms the aggregated tree. The Auditor runs on that same slow cadence, so
    it is the natural place to fetch the finished proof. Returns the updated witness dict when
    an upgrade landed, else None. Best-effort — a pending anchor is not a failure, just not done.

    The upgraded proof is stored under a *new* key (`…-btc.ots`) rather than overwriting the
    pending one: under Object Lock the original is immutable, and keeping both leaves the
    calendar commitment and its Bitcoin completion each independently retrievable.
    """
    try:
        from . import witness

        if not witness.is_enabled():
            return None
        repo = get_repo()
        checkpoint = repo.latest_checkpoint()
        wit = (checkpoint or {}).get("witness")
        if not checkpoint or not wit or wit.get("complete") or not wit.get("proof_key"):
            return None

        from .storage import get_storage

        storage = get_storage()
        proof = storage.get_bytes(wit["proof_key"])
        upgraded = witness.upgrade(proof)
        if upgraded is None:
            return None

        info = witness.describe(upgraded)
        new_wit = {**wit,
                   "bitcoin_block_height": info["bitcoin_block_height"],
                   "complete": info["complete"]}
        btc_key = wit["proof_key"].replace(".ots", "-btc.ots")
        try:
            settings = get_settings()
            storage.put_immutable(btc_key, upgraded, "application/octet-stream",
                                  retain_days=settings.b2_object_lock_days,
                                  mode=settings.b2_object_lock_mode)
            new_wit["proof_key"] = btc_key
        except Exception as exc:  # noqa: BLE001 — the upgrade is real even if re-storing fails
            log.warning("witness upgraded-proof publish failed: %s", exc)

        repo.save_checkpoint({**checkpoint, "witness": new_wit})
        log.info("witness upgraded: checkpoint %s anchored in Bitcoin block %s",
                 checkpoint["checkpoint_hash"][:12], info["bitcoin_block_height"])
        return new_wit
    except Exception as exc:  # noqa: BLE001 — an upgrade attempt must never break an audit
        log.warning("witness upgrade failed: %s", exc)
        return None


def position_for(sha256: str) -> dict | None:
    """Where an asset sits in the log, for `/verify` to show alongside its provenance."""
    if not get_settings().transparency_enabled:
        return None
    try:
        repo = get_repo()
        entry = repo.find_transparency_entry(sha256)
        if not entry:
            return None
        checkpoint = repo.latest_checkpoint()
        covered = bool(checkpoint and int(checkpoint.get("size", 0)) > int(entry["seq"]))
        return {
            "seq": entry["seq"],
            "entry_hash": entry["entry_hash"],
            "recorded_at": entry["recorded_at"],
            "log_size": repo.transparency_size(),
            "checkpoint_hash": checkpoint.get("checkpoint_hash") if checkpoint else None,
            "checkpoint_size": checkpoint.get("size") if checkpoint else None,
            # An entry written after the last checkpoint is in the log but not yet committed
            # to by any published head — a real and material distinction, so it is shown.
            "checkpoint_covers_entry": covered,
        }
    except Exception as exc:  # noqa: BLE001 — verification must not fail over the log
        log.warning("transparency lookup failed for %s: %s", sha256, exc)
        return None


def inclusion_proof(sha256: str) -> dict | None:
    """Everything a third party needs to verify this entry offline.

    Returns the entry, every entry after it, and the checkpoint to replay towards. The proof
    is O(n-k) because this is a chain rather than a Merkle tree; that cost is documented
    rather than hidden.
    """
    repo = get_repo()
    entry = repo.find_transparency_entry(sha256)
    if not entry:
        return None
    checkpoint = repo.latest_checkpoint()
    if not checkpoint:
        return None
    size = int(checkpoint["size"])
    following = repo.list_transparency_entries(start=int(entry["seq"]) + 1)
    # Trim to the checkpoint: entries added after it are not part of what it commits to.
    following = [e for e in following if int(e["seq"]) < size]
    return {"entry": entry, "following": following, "checkpoint": checkpoint}
