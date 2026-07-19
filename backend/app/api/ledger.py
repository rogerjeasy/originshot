"""Public transparency-log endpoints.

Everything here is unauthenticated and read-only, because a log only anyone can read is a
log nobody has to trust. The endpoints exist to be consumed by `scripts/verify_ledger.py`
(and by anyone who writes their own verifier) rather than only by our own UI — which is why
`/proof` hands back raw entries and a checkpoint instead of a verdict computed on our side.

`/verify-log` is offered as a convenience for the UI and is deliberately the *weakest* thing
here: it is us marking our own homework. The endpoint says so in its own response.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Query

from originshot_pipelines import transparency as chain

from .. import transparency as log_service
from ..config import get_settings
from ..models import (LedgerAuditOut, LedgerCheckpointOut, LedgerEntryRow,
                      LedgerProofOut, LedgerStatusOut, LedgerVerifyOut)
from ..repo import get_repo

log = logging.getLogger("originshot.ledger")

router = APIRouter(prefix="/ledger", tags=["transparency"])

_MAX_PAGE = 500


@router.get("", response_model=LedgerStatusOut)
def status():
    """Log size, current head, and the latest published checkpoint."""
    repo = get_repo()
    size = repo.transparency_size()
    entries = repo.list_transparency_entries(start=max(0, size - 1)) if size else []
    checkpoint = repo.latest_checkpoint()
    return LedgerStatusOut(
        log_id="originshot-transparency-v1",
        size=size,
        head=entries[-1]["entry_hash"] if entries else chain.GENESIS_HASH,
        checkpoint=checkpoint,
        checkpoint_lag=max(0, size - int((checkpoint or {}).get("size") or 0)),
    )


@router.get("/entries", response_model=list[LedgerEntryRow])
def entries(start: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=_MAX_PAGE)):
    """A page of the raw log, in sequence order — the data a verifier replays."""
    return get_repo().list_transparency_entries(start=start, limit=limit)


@router.get("/checkpoint", response_model=LedgerCheckpointOut)
def checkpoint():
    checkpoint = get_repo().latest_checkpoint()
    if not checkpoint:
        raise HTTPException(404, "No checkpoint has been published yet")
    return checkpoint


@router.get("/proof/{sha256}", response_model=LedgerProofOut)
def proof(sha256: str):
    """An offline-verifiable inclusion proof for one asset.

    Returns the entry, every entry after it up to the checkpoint, and the checkpoint itself.
    Replaying those forward must reproduce the published head — which it can only do if this
    entry is genuinely part of that history.
    """
    found = log_service.inclusion_proof(sha256.strip().lower())
    if not found:
        raise HTTPException(404, "No log entry (or no checkpoint) for that hash")
    return LedgerProofOut(
        **found,
        note="Replay `entry` then `following` and compare the resulting head to "
             "`checkpoint.head`. scripts/verify_ledger.py does exactly this, offline.",
    )


@router.get("/audit", response_model=LedgerAuditOut)
def last_audit():
    """The most recent integrity audit (app/auditor.py) — public, like the rest of the log.

    404 until an audit has run: "no audit yet" and "audit passed" must never render the
    same way, so absence is a distinct state rather than a default-green placeholder.
    """
    from ..auditor import latest_audit

    report = latest_audit()
    if not report:
        raise HTTPException(404, "No audit has run yet")
    return report


@router.post("/audit", response_model=LedgerAuditOut)
def trigger_audit(x_audit_token: str | None = Header(default=None)):
    """Run one audit pass now. The caller is a scheduler, not a person.

    Authenticated by a shared token (GitHub Actions cron holds it as a secret) rather than
    a user account, because no user is present at 03:00. Unset token ⇒ 503, so a
    deployment that never configured auditing refuses rather than silently exposing an
    unauthenticated endpoint that downloads media at B2's expense.
    """
    expected = get_settings().audit_trigger_token
    if not expected:
        raise HTTPException(503, "Auditing is not configured (AUDIT_TRIGGER_TOKEN unset)")
    if not x_audit_token or not hmac.compare_digest(x_audit_token, expected):
        raise HTTPException(403, "Invalid audit token")

    from ..auditor import run_audit

    try:
        return run_audit()
    except Exception as exc:  # noqa: BLE001 — an audit crash must not read as an outage
        log.exception("audit run failed")
        raise HTTPException(500, f"Audit failed to complete: {exc.__class__.__name__}") from exc


@router.get("/verify-log", response_model=LedgerVerifyOut)
def verify_log():
    """Replay the whole chain server-side.

    A convenience for the UI, and the weakest claim on this router: an operator verifying
    their own log proves nothing to a sceptic. The real check is running the standalone
    verifier against `/entries` and `/checkpoint`, which is why the response says so.
    """
    repo = get_repo()
    rows = repo.list_transparency_entries()
    checkpoint = repo.latest_checkpoint()
    result = chain.verify_chain(rows)
    covered = None
    if checkpoint:
        covered = chain.verify_chain(
            rows[: int(checkpoint["size"])], expect_head=checkpoint["head"]
        )["consistent"]
    return LedgerVerifyOut(
        consistent=result["consistent"],
        size=result["size"],
        head=result["head"],
        broken_at=result["broken_at"],
        reason=result["reason"],
        checkpoint_reproduced=covered,
        caveat="This instance verified its own log. That is not independent evidence — "
               "re-run the check yourself with scripts/verify_ledger.py against the public "
               "/api/ledger endpoints.",
    )
