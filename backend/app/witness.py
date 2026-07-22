"""The external witness — anchoring transparency checkpoints into Bitcoin via OpenTimestamps.

The transparency log already has two integrity layers, and both share a weakness this module
exists to fix: **they rest on infrastructure the operator controls.** B2 Object Lock makes a
published checkpoint immutable — but in *our* bucket, under a retention *we* configured. The
Ed25519 signature proves *we* issued a head — with *our* key. A determined operator still
controls both. What neither provides is a timestamp from a party outside the operator's reach,
so "this head existed at time T and has not been rewritten since" ultimately still asks you to
trust us.

**OpenTimestamps closes that.** It commits a hash into the Bitcoin blockchain: the checkpoint
hash is submitted to public calendar servers, aggregated into a Merkle tree, and that tree's
root is anchored in a Bitcoin block. The resulting `.ots` proof lets *anyone* verify, against
Bitcoin and needing nothing from us, that the checkpoint hash existed no later than that block —
a timestamp the operator cannot backdate and cannot rewrite, because they do not control Bitcoin.
This is the first anchor in the project whose trust root is not our own infrastructure.

**What it does and does not close, stated precisely** (the same discipline as the rest):
  * It **closes backdating and silent rewriting of a published head** against an independent
    party. Combined with the Ed25519 signature — which makes any two conflicting checkpoints
    each self-incriminating (both signed by our one key) — a split view becomes *detectable the
    moment any two parties compare the checkpoints they were shown*.
  * It does **not**, by itself, force the operator to expose every head to a common auditor.
    That last step — gossip between independent witnesses so no one has to find the other victim —
    is the Certificate-Transparency ideal a single-operator log still cannot fully reach, and it
    stays documented as the next step rather than claimed as done.

**Best-effort by contract**, exactly like signing and Object Lock: if the calendars are
unreachable, the library is missing, or anything else fails, the checkpoint publishes with no
witness (the `witness` field is simply absent — never a claim of an anchor that isn't there),
and the periodic Auditor retries the pending upgrade later. A ledger anchor must never fail a
paid generation.
"""
from __future__ import annotations

import logging

from .config import get_settings

log = logging.getLogger("originshot.witness")

# The kind string recorded on a checkpoint's `witness` field, so a reader (and the schema) can
# tell what anchored it without inspecting the proof bytes.
WITNESS_TYPE = "opentimestamps"


def _make_calendar(url: str):
    """Construct a remote OpenTimestamps calendar client. Isolated so tests can substitute a
    fake calendar without touching the network."""
    from opentimestamps.calendar import RemoteCalendar

    return RemoteCalendar(url)


def is_enabled() -> bool:
    """True only when witnessing is switched on AND the library is importable.

    Kept together so every entry point degrades identically: a deployment without the optional
    dependency behaves exactly like one with `WITNESS_ENABLED=false`, never a crash on import.
    """
    if not get_settings().witness_enabled:
        return False
    try:
        import opentimestamps  # noqa: F401
    except Exception:  # noqa: BLE001 — a missing/broken dep simply disables witnessing
        return False
    return True


def stamp(digest_hex: str) -> tuple[bytes, list[str]] | None:
    """Submit a checkpoint hash to the OpenTimestamps calendars.

    Returns `(proof_bytes, calendar_urls)` — the serialized `.ots` detached proof plus the
    calendars that accepted it — or None if witnessing is off, the hash is unusable, or no
    calendar could be reached. Every failure is swallowed and logged: this is best-effort, and
    a checkpoint must publish whether or not an anchor was obtained.
    """
    if not is_enabled() or not digest_hex:
        return None
    try:
        from opentimestamps.core.op import OpSHA256
        from opentimestamps.core.serialize import BytesSerializationContext
        from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp
    except Exception:  # noqa: BLE001
        return None
    try:
        digest = bytes.fromhex(digest_hex)
    except ValueError:
        return None

    timeout = max(1, get_settings().witness_timeout_seconds)
    timestamp = Timestamp(digest)
    for url in get_settings().witness_calendar_list:
        try:
            merged = _make_calendar(url).submit(digest, timeout=timeout)
            timestamp.merge(merged)
        except Exception as exc:  # noqa: BLE001 — one calendar down must not sink the anchor
            log.info("witness: calendar %s unavailable (%s)", url, type(exc).__name__)

    pending = _pending_uris(timestamp)
    if not pending:
        return None  # no calendar accepted it — nothing to store, so claim nothing
    try:
        detached = DetachedTimestampFile(OpSHA256(), timestamp)
        ctx = BytesSerializationContext()
        detached.serialize(ctx)
        return ctx.getbytes(), pending
    except Exception as exc:  # noqa: BLE001
        log.warning("witness: proof serialization failed (%s)", type(exc).__name__)
        return None


def describe(proof_bytes: bytes) -> dict:
    """Summarise an `.ots` proof for display and storage.

    Returns ``{pending_calendars, bitcoin_block_height, complete, digest}``. `complete` is True
    once a Bitcoin attestation is present; until then the proof is a calendar commitment that
    the Auditor upgrades later. Never raises — a malformed proof yields the empty summary.
    """
    empty = {"pending_calendars": [], "bitcoin_block_height": None,
             "complete": False, "digest": None}
    try:
        from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
        from opentimestamps.core.serialize import BytesDeserializationContext
        from opentimestamps.core.timestamp import DetachedTimestampFile
    except Exception:  # noqa: BLE001
        return empty
    try:
        detached = DetachedTimestampFile.deserialize(BytesDeserializationContext(proof_bytes))
    except Exception:  # noqa: BLE001
        return empty

    ts = detached.timestamp
    height: int | None = None
    for _msg, att in ts.all_attestations():
        if isinstance(att, BitcoinBlockHeaderAttestation):
            # Earliest confirmed block is the honest bound on "existed no later than".
            height = att.height if height is None else min(height, att.height)
    return {
        "pending_calendars": _pending_uris(ts),
        "bitcoin_block_height": height,
        "complete": height is not None,
        "digest": ts.msg.hex(),
    }


def upgrade(proof_bytes: bytes) -> bytes | None:
    """Try to complete a pending proof into a confirmed Bitcoin attestation.

    Queries each pending calendar for the finished path. Returns the upgraded proof bytes if
    anything changed (a caller then re-stores them), or None if nothing could be upgraded yet.
    Best-effort; used by the Auditor on its periodic pass.
    """
    if not is_enabled() or not proof_bytes:
        return None
    try:
        from opentimestamps.core.serialize import (BytesDeserializationContext,
                                                   BytesSerializationContext)
        from opentimestamps.core.timestamp import DetachedTimestampFile
    except Exception:  # noqa: BLE001
        return None
    try:
        detached = DetachedTimestampFile.deserialize(BytesDeserializationContext(proof_bytes))
    except Exception:  # noqa: BLE001
        return None

    if not _upgrade_timestamp(detached.timestamp):
        return None
    try:
        ctx = BytesSerializationContext()
        detached.serialize(ctx)
        return ctx.getbytes()
    except Exception as exc:  # noqa: BLE001
        log.warning("witness: upgraded proof serialization failed (%s)", type(exc).__name__)
        return None


# ── internals ─────────────────────────────────────────────────────────
def _pending_uris(timestamp) -> list[str]:
    from opentimestamps.core.notary import PendingAttestation

    uris = {att.uri for _msg, att in timestamp.all_attestations()
            if isinstance(att, PendingAttestation)}
    return sorted(uris)


def _upgrade_timestamp(timestamp) -> bool:
    """Recurse the timestamp tree, asking each pending calendar to finish its commitment.

    Mirrors the opentimestamps-client upgrade walk: at every node with a pending attestation,
    fetch the completed timestamp for that node's message and merge it; then descend into the
    child operations. Returns whether anything changed.
    """
    from opentimestamps.core.notary import PendingAttestation

    timeout = max(1, get_settings().witness_timeout_seconds)
    changed = False
    for att in list(timestamp.attestations):
        if isinstance(att, PendingAttestation):
            try:
                completed = _make_calendar(att.uri).get_timestamp(timestamp.msg, timeout=timeout)
                timestamp.merge(completed)
                changed = True
            except Exception as exc:  # noqa: BLE001 — still pending, or calendar down
                log.info("witness: upgrade via %s not ready (%s)", att.uri, type(exc).__name__)
    for _op, sub in list(timestamp.ops.items()):
        if _upgrade_timestamp(sub):
            changed = True
    return changed
