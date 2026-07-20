"""The Auditor — a scheduled integrity agent for the media library and the ledger.

Everything else in this project proves integrity *on demand*: /verify when someone uploads
a file, the standalone script when someone replays the log. Nothing checked that the stored
library still is what the records say it is — bit rot, a bad write, or an operator quietly
swapping bytes under a content-addressed key would sit unnoticed until a customer happened
to hit the one damaged file. The Auditor closes that gap by doing, on a schedule, exactly
what a sceptical customer would do by hand:

  1. **Spot-check the library.** Download a random sample of stored assets and re-derive
     the truth from bytes alone: does the object still hash to the content address it is
     stored under, and (for embedded assets) does the manifest still verify and still bind
     to the media? The checks are the same code paths /verify uses — the audit holds the
     instance to the standard it advertises, not to a weaker internal one.
  2. **Replay the ledger.** Verify the whole chain is internally consistent AND that
     replaying the first `checkpoint.size` entries reproduces the last *published* head —
     the same check that catches a rewritten history in scripts/verify_ledger.py.
  3. **Cut a fresh checkpoint.** Entry-count checkpointing leaves a quiet period's tail
     uncommitted indefinitely (config.py notes this); the audit is the timer that commits
     it.
  4. **Publish the report to B2.** The report is stored under a key carrying its own
     SHA-256, so "the audit said X" is checkable against the stored bytes the same way
     every other claim in this system is.

**What this does and does not prove.** The audit is the instance marking its own homework,
and the report says so: a dishonest operator could simply not run it, or not publish a bad
result. Its value is against *silent* failure — corruption nobody chose, drift nobody
noticed — and as a heartbeat a judge or customer can see ("last audit: 2h ago, 25 assets
verified, chain consistent"). Independent verification remains the standalone script,
which needs none of our code to trust.

Failure isolation mirrors the rest of the codebase: one unreadable asset fails that row,
never the audit; a B2 publish failure degrades the report to repo-only rather than losing
it; and the trigger endpoint never lets an audit exception take the API down with it.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from originshot_pipelines import transparency as chain

from . import transparency
from .config import get_settings
from .repo import get_repo
from .storage import get_storage

log = logging.getLogger("originshot.auditor")

AUDIT_PREFIX = "ledger/audits"

# The public caveat, stated once. Same register as /verify-log's: self-audit is evidence
# against accident, not against a dishonest operator.
CAVEAT = (
    "This instance audited itself. That protects against silent corruption and drift, not "
    "against a dishonest operator — for independent verification run "
    "scripts/verify_ledger.py against the public /api/ledger endpoints."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _audit_asset(asset: dict, storage) -> dict:
    """Re-derive one asset's integrity from its stored bytes.

    Returns {sha256, style, kind, ok, checks{...}, error?}. `ok` is the conjunction of
    every boolean check that ran; an asset whose bytes can't be fetched is a failure with
    the reason recorded — unlike QA (which must never punish an asset for our own download
    hiccup mid-generation), an audit's entire job is noticing that a stored object can no
    longer be read.
    """
    sha = asset.get("sha256")
    out = {
        "sha256": sha,
        "style": asset.get("style"),
        "kind": "original" if asset.get("is_authentic") else "generated",
        "ok": False,
        "checks": {},
    }
    try:
        data = storage.get_bytes(asset["b2_key"])
    except Exception as e:  # noqa: BLE001
        out["error"] = f"unreadable ({e.__class__.__name__})"
        return out

    out["checks"]["bytes_match_hash"] = hashlib.sha256(data).hexdigest() == sha

    if asset.get("embedded"):
        # The same re-derivation /verify performs on an upload: extract the embedded
        # manifest from the actual bytes, verify it, and confirm content-binding.
        from originshot_pipelines import provenance

        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "asset"
                path.write_bytes(data)
                res = provenance.verify_file(path)
            out["checks"]["manifest_present"] = bool(res.get("present"))
            out["checks"]["manifest_verified"] = bool(res.get("verified"))
            if res.get("content_bound") is not None:
                out["checks"]["content_bound"] = bool(res["content_bound"])
        except Exception as e:  # noqa: BLE001
            out["error"] = f"manifest check failed ({e.__class__.__name__})"
            return out

    out["ok"] = all(v for v in out["checks"].values())
    return out


def run_audit(*, sample_size: int | None = None) -> dict:
    """One full audit pass. Returns the report; never raises for per-item failures."""
    settings = get_settings()
    repo = get_repo()
    storage = get_storage()

    started = _now_iso()
    t0 = time.monotonic()
    audit_id = f"audit-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    # 1. Spot-check a random sample of the library. Only assets we store ourselves are
    # sampleable — an asset with no b2_key lives outside the bucket and has nothing for
    # this check to say about it.
    candidates = [a for a in repo.list_all_assets() if a.get("b2_key") and a.get("sha256")]
    n = sample_size if sample_size is not None else settings.audit_sample_size
    sample = candidates if len(candidates) <= n else random.sample(candidates, n)
    results = [_audit_asset(a, storage) for a in sample]
    failures = [r for r in results if not r["ok"]]

    # 2. Replay the ledger — the whole chain, then the published head specifically.
    chain_consistent = None
    checkpoint_reproduced = None
    rows: list[dict] = []
    try:
        rows = repo.list_transparency_entries()
        chain_consistent = chain.verify_chain(rows)["consistent"]
        previous = repo.latest_checkpoint()
        if previous:
            checkpoint_reproduced = chain.verify_chain(
                rows[: int(previous["size"])], expect_head=previous["head"]
            )["consistent"]
    except Exception as exc:  # noqa: BLE001
        log.warning("audit ledger replay failed: %s", exc)

    # 3. The timer-based checkpoint cut: commit whatever the entry-count trigger hasn't.
    new_checkpoint = None
    if rows:
        new_checkpoint = transparency.publish_checkpoint()

    report = {
        "audit_id": audit_id,
        "started_at": started,
        "finished_at": _now_iso(),
        "duration_ms": int((time.monotonic() - t0) * 1000),
        "assets_sampled": len(sample),
        "assets_passed": len(results) - len(failures),
        # Capped so a systemic failure produces a readable report, not a megabyte of rows.
        "failures": failures[:20],
        "ledger_entries": len(rows),
        "chain_consistent": chain_consistent,
        "checkpoint_reproduced": checkpoint_reproduced,
        "checkpoint": new_checkpoint,
        "caveat": CAVEAT,
    }

    # 4. Publish the report to B2 under its own hash, then record it as the latest audit.
    # Verifiable claim: fetch the object at b2_key, hash it, compare to sha256.
    body = json.dumps(report, sort_keys=True, indent=2, default=str).encode("utf-8")
    sha = hashlib.sha256(body).hexdigest()
    key = f"{AUDIT_PREFIX}/{audit_id}-{sha[:12]}.json"
    try:
        settings = get_settings()
        # Same immutability as checkpoints: an audit report that could be quietly rewritten
        # after the fact is a report you have to trust rather than verify. Under Object Lock
        # it cannot be — retained_until is recorded only when a real lock was applied.
        retained_until = storage.put_immutable(
            key, body, "application/json",
            retain_days=settings.b2_object_lock_days,
            mode=settings.b2_object_lock_mode,
        )
        report["b2_key"] = key
        report["retained_until"] = (
            retained_until.strftime("%Y-%m-%dT%H:%M:%SZ") if retained_until else None
        )
    except Exception as exc:  # noqa: BLE001 — an unpublished report is still a record
        log.warning("audit report publish to B2 failed: %s", exc)
        report["b2_key"] = None
    report["sha256"] = sha

    try:
        repo.set_platform_config({"last_audit": report})
    except Exception as exc:  # noqa: BLE001
        log.warning("audit record save failed: %s", exc)

    log.info(
        "audit %s: %d/%d assets ok, chain=%s, checkpoint_reproduced=%s",
        audit_id, report["assets_passed"], report["assets_sampled"],
        chain_consistent, checkpoint_reproduced,
    )
    return report


def latest_audit() -> dict | None:
    """The most recent audit report, as recorded at the end of run_audit."""
    try:
        return get_repo().get_platform_config().get("last_audit") or None
    except Exception as exc:  # noqa: BLE001
        log.warning("latest audit read failed: %s", exc)
        return None
