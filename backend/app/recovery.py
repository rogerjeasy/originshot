"""Resolving provenance from B2 when this instance's own database no longer can.

`/verify` normally answers from the asset record in Firestore. But the transparency log is
append-only and the asset table is not: delete a SKU and the chain entry survives while the
row it described disappears. The verifier then reported `found: false` for a hash that was
sitting in its own signed, checkpointed, Bitcoin-anchored log — the app contradicting its own
ledger, which is the one failure this project cannot afford. On 2026-08-01, 6 of 30 production
entries were in exactly that state.

The fix is not a wider database lookup. Every entry already commits to **where its manifest
lives on B2**, so the record is still out there; the app simply wasn't asking. Recovering it
makes good on the claim the README makes for B2 — that object storage is the trust anchor
rather than a blob store — because the provenance survives the database that described it.

**The chain of custody, precisely.** `manifest_hash` is one of `COMMITTED_FIELDS`
(`originshot_pipelines/transparency.py`), so:

    Bitcoin (OpenTimestamps) ─┐
    Ed25519 signature ────────┴─▶ checkpoint ─▶ head ─▶ entry_hash ─▶ manifest_hash (B2 key)

An attacker who repointed an entry at a manifest of their choosing would change `entry_hash`,
which breaks every hash after it and no longer reproduces a published head that is signed and
timestamped in a chain they do not control.

**What this does NOT establish, stated as plainly as the rest of the project states its gaps:**

  * *Location, not content.* The chain commits to the manifest's B2 key, not to a hash of the
    manifest's bytes. Checkpoints are written under Object Lock; sidecar manifests are not. So
    bucket write access could still swap the object at that key. The manifest self-verifies
    (`Manifest.verify()` recomputes its own canonical hash), which catches corruption and
    careless edits — not a deliberate re-issue.
  * *No content-binding from a hash alone.* The ledger's subject is the **post-embed** hash
    (`generation._embed_and_store` rewrites `sha256` after injecting the manifest), while the
    manifest records the **pre-embed** asset hash. They are legitimately different bytes, so
    the recovered manifest cannot be re-hashed against the subject and `GET /verify/{sha}` must
    leave `content_bound` unset. Posting the file itself still binds: those bytes hash to the
    subject the signed chain committed to, which `verify_bytes` treats exactly as it treats a
    byte-exact hit on a stored row.

Both limits are carried into the disclosure string the caller shows, so a recovered answer can
never be mistaken for a byte-proven one.
"""
from __future__ import annotations

import json
import logging

from .repo import get_repo
from .storage import get_storage, key_from_url

log = logging.getLogger("originshot.recovery")

# How a recovered record identifies itself, on `VerifyResult.resolved_from` and in the admin
# surfaces. The normal path reports "record".
SOURCE = "b2-manifest"

# Pipeline name (`run.name`) → our Style vocabulary. Manifests record the pipeline that ran,
# not our enum, and the two only coincide by convention — spelling the mapping out means a
# renamed pipeline yields `None` (honest "unknown") instead of a silently wrong style.
_STYLE_BY_RUN_NAME = {
    "originshot-studio": "studio",
    "originshot-lifestyle": "lifestyle",
    "originshot-onmodel": "onmodel",
    "originshot-variant": "variant",
    "originshot-hero-video": "video",
    "originshot-text-to-video": "video",
    "originshot-voiceover": "voiceover",
    "originshot-narrated-video": "voiceover",
    # "originshot-replay" is deliberately absent: a replay's manifest names the replay
    # pipeline, not the style it reproduced, and guessing would put a wrong label on a record
    # whose whole purpose is being accurate.
}

# Successful manifest loads only, keyed by B2 key. A public unauthenticated endpoint should not
# issue an unbounded object fetch per request, and manifests are immutable in practice. Failures
# are never cached — a transient B2 error must not become a permanent "not found".
_cache: dict[str, dict] = {}
_CACHE_MAX = 512


def _load_manifest(key: str) -> dict | None:
    cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        doc = json.loads(get_storage().get_bytes(key))
    except Exception as exc:  # noqa: BLE001 — an unrecoverable record is not an error to raise
        log.info("manifest recovery failed for key %s: %s", key, exc)
        return None
    if not isinstance(doc, dict):
        return None
    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    _cache[key] = doc
    return doc


def _final_step(run: dict) -> dict | None:
    """The step that produced the run's output.

    Every pipeline in this app is single-step, so this is `steps[0]` in practice. Preferring
    the last step that actually emitted assets keeps it correct if a chained pipeline is ever
    added, rather than silently attributing the output to the first stage.
    """
    steps = [s for s in (run.get("steps") or []) if isinstance(s, dict)]
    if not steps:
        return None
    with_assets = [s for s in steps if s.get("assets")]
    return (with_assets or steps)[-1]


def recover_from_ledger(sha256: str) -> dict | None:
    """Rebuild an asset-shaped provenance record for `sha256` from B2, or None.

    Returns the same keys `/verify` reads off a database row, so the caller needs no second
    code path — plus `resolved_from` so the answer always declares where it came from.
    `verified` is a real check: the recovered manifest recomputes its own canonical hash.

    Returns None when the hash is not in the log, when its entry carries no manifest (authentic
    originals never do), or when the manifest cannot be read or parsed. In every one of those
    cases the caller's existing "no record" answer is the correct one.
    """
    try:
        entry = get_repo().find_transparency_entry(sha256)
    except Exception as exc:  # noqa: BLE001 — verification must not fail over the log
        log.warning("ledger lookup failed during recovery for %s: %s", sha256, exc)
        return None
    if not entry:
        return None

    pointer = entry.get("manifest_hash")
    if not pointer:
        return None
    # The sink records a full bucket URL; manifests we persist ourselves record a bare key.
    # `key_from_url` returns None for anything outside our bucket, which correctly refuses to
    # let a log entry send us fetching from somewhere else.
    key = key_from_url(pointer) or pointer
    if key.startswith(("http://", "https://")):
        log.info("manifest pointer for %s is outside our bucket; not fetched", sha256)
        return None

    doc = _load_manifest(key)
    if doc is None:
        return None

    try:
        from genblaze_core.models.manifest import parse_manifest

        manifest = parse_manifest(doc)
        verified = bool(manifest.verify())
    except Exception as exc:  # noqa: BLE001
        log.info("recovered manifest for %s did not parse: %s", sha256, exc)
        return None

    run = doc.get("run") or {}
    step = _final_step(run) or {}
    inputs = [i for i in (step.get("inputs") or []) if isinstance(i, dict)]
    parent = next((i.get("sha256") for i in inputs if i.get("sha256")), None)

    return {
        "sha256": sha256,
        "resolved_from": SOURCE,
        "manifest_verified": verified,
        "is_authentic": False,          # originals carry no manifest, so this is always generated
        "embedded": False,              # verified from the B2 sidecar, not from the file's bytes
        "modality": (step.get("modality") or None),
        "style": _STYLE_BY_RUN_NAME.get(run.get("name") or ""),
        "provider": step.get("provider"),
        "model": step.get("model"),
        "parent_sha256": parent,
        "created_at": run.get("completed_at") or run.get("created_at"),
        "manifest_key": key,
        "run_id": run.get("run_id"),
        "ledger_seq": entry.get("seq"),
    }


def disclosure(record: dict) -> str:
    """Disclosure text for a recovered record — never phrased as a byte-proven result.

    Says what was recovered, where from, and (because the honesty is the product) that the
    database row is gone and only the file's own bytes can prove content-binding.
    """
    model = record.get("model") or "an undisclosed model"
    provider = record.get("provider")
    medium = record.get("modality") or "file"
    who = f"{model} ({provider})" if provider else model
    lineage = (
        f" Derived from authentic source {record['parent_sha256'][:12]}."
        if record.get("parent_sha256") else ""
    )
    return (
        f"AI-generated {medium}. Model: {who}.{lineage} "
        "This instance no longer holds a database record for this hash, so its provenance was "
        "recovered from the manifest published on Backblaze B2 at the key its transparency-log "
        "entry commits to. The manifest passes its own integrity check. Content-binding cannot "
        "be established from a hash alone — POST the file itself to /api/verify for that."
    )
