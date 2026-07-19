"""Resolve — issue a Dispute Evidence Report.

**Public and unauthenticated, on purpose.** Every other route in this app serves the seller;
this one serves the buyer and the marketplace, who by definition have no account here. A
dispute-evidence tool that requires the seller's login is a tool that never gets used in the
argument it exists for.

That makes it the only unauthenticated path to a provider bill, so it is fenced accordingly:
a tight per-IP limit (`RESOLVE_RATE_LIMIT`, default 10/hour) on top of the global ceiling,
the same upload validation as the seller-facing path, and a hard requirement that the listing
image resolve to a *known anchor* before any model is called. That last one is the real
control — an attacker with no valid listing hash cannot reach the expensive step at all.

The submitted delivered-item photo is never stored. See `originshot_pipelines/resolve.py`.
"""
from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from originshot_pipelines import provenance, resolve as resolve_lib

from ..config import get_settings
from ..models import ResolveOut
from ..repo import get_repo
from ..security import limiter, validate_and_normalize_image
from ..storage import get_storage, key_from_url, storage_key

log = logging.getLogger("originshot.resolve")

router = APIRouter(tags=["resolve"])

_SHA256_LEN = 64


def _rate_limit() -> str:
    return get_settings().resolve_rate_limit


@router.post("/resolve", response_model=ResolveOut)
@limiter.limit(_rate_limit)
async def create_dispute_report(
    request: Request,                                   # required by slowapi's decorator
    listing_file: UploadFile | None = File(default=None),
    listing_sha256: str | None = Form(default=None),
    received_file: UploadFile | None = File(default=None),
):
    """Compare a listing image's provenance — and optionally the item that arrived — and
    issue a hash-anchored PDF report."""
    settings = get_settings()
    if not settings.resolve_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Dispute reports are disabled on this instance.")
    if listing_file is None and not listing_sha256:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Provide the listing image file or its SHA-256.")

    listing, asset = await _inspect_listing(listing_file, listing_sha256, settings)
    anchor_asset = _resolve_anchor(asset)
    anchor = {
        "sha256": anchor_asset.get("sha256") if anchor_asset else None,
        "created_at": anchor_asset.get("created_at") if anchor_asset else None,
    }

    received: dict = {"sha256": None}
    match: dict | None = None
    unavailable: str | None = None

    if received_file is not None:
        raw = await received_file.read()
        # Hash the bytes AS SUBMITTED. validate_and_normalize_image re-encodes to strip EXIF,
        # and hashing the normalized result would print a hash in the report that the holder
        # of the photo could never reproduce — quietly breaking the one property that ties
        # this report to that image.
        received["sha256"] = hashlib.sha256(raw).hexdigest()
        safe = validate_and_normalize_image(raw)     # type/size/bomb checks before decoding

        anchor_bytes = _anchor_bytes(anchor_asset)
        match_call = _make_match_call(settings)
        if anchor_bytes is None:
            unavailable = (
                "no authentic original is on record for this listing image, so there was "
                "nothing to compare the delivered item against"
            )
        elif match_call is None:
            unavailable = "the comparison model is not configured on this instance"
        else:
            try:
                match = match_call(anchor_bytes, safe["bytes"])
            except Exception as exc:  # noqa: BLE001 — never fabricate a comparison
                log.warning("resolve: comparison failed (%s)", exc)
                unavailable = f"the comparison model could not be reached ({type(exc).__name__})"

    verdict = resolve_lib.assess(listing=listing, match=match)

    record = {
        **verdict,
        "listing": listing,
        "anchor": anchor,
        "received": received,
        "match": match,
        "match_unavailable": unavailable,
        "issued_at": resolve_lib.issued_at_now(),
    }
    # Persist the findings BEFORE rendering: the report is the evidence, the PDF is a view
    # of it. A rendering failure must not lose a comparison the caller already paid for.
    stored = get_repo().add_dispute_report(record)
    pdf_sha, pdf_url = _render_and_store(stored, settings)
    return _to_out(stored, pdf_sha, pdf_url)


@router.get("/resolve/{report_id}", response_model=ResolveOut)
def get_dispute_report(report_id: str):
    """Public: resolve a report by the id printed on the PDF, with a fresh download link."""
    record = get_repo().get_dispute_report(report_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such report")
    url = None
    if record.get("report_key"):
        try:
            url = get_storage().presigned_get(record["report_key"])
        except Exception as exc:  # noqa: BLE001 — the findings still resolve without the PDF
            log.warning("resolve: presign failed for %s (%s)", report_id, exc)
    return _to_out(record, record.get("report_sha256"), url)


# ── Assembly helpers ──────────────────────────────────────────────────
async def _inspect_listing(file: UploadFile | None, sha: str | None,
                           settings) -> tuple[dict, dict | None]:
    """Re-derive what the listing image says about itself, from its bytes where possible.

    Mirrors /api/verify's precedence deliberately: a manifest extracted from the submitted
    bytes always outranks anything we have stored, because the stored record is exactly what
    a dispute might be about.
    """
    extracted = {"present": False, "verified": False, "content_bound": None}
    resolved_sha = (sha or "").strip().lower()

    if file is not None:
        data = await file.read()
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")
        resolved_sha = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "listing"
            path.write_bytes(data)
            extracted = provenance.verify_file(path)
    elif len(resolved_sha) != _SHA256_LEN or not all(
        c in "0123456789abcdef" for c in resolved_sha
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "A SHA-256 is 64 hexadecimal characters.")

    asset = get_repo().find_asset_by_sha(resolved_sha) if resolved_sha else None
    found = bool(asset)

    if extracted["present"]:
        verified = bool(extracted["verified"])
    elif found:
        stored = asset.get("manifest_verified")
        verified = True if stored is None else bool(stored)
    else:
        verified = False

    # A byte-exact match to a stored asset is itself definitive content integrity — same
    # reasoning as /api/verify, kept consistent so the two surfaces never disagree.
    content_bound = extracted["content_bound"]
    if content_bound is None and found and file is not None:
        content_bound = True

    return {
        "sha256": resolved_sha or None,
        "present": bool(extracted["present"]),
        "verified": verified,
        "content_bound": content_bound,
        "found": found,
        "is_authentic": bool(asset.get("is_authentic")) if found else False,
        "provider": asset.get("provider") if found else None,
        "model": asset.get("model") if found else None,
        "created_at": asset.get("created_at") if found else None,
    }, asset


def _resolve_anchor(asset: dict | None) -> dict | None:
    """The authentic original a listing image descends from.

    An authentic upload anchors itself; a generated asset points at its source through
    `parent_sha256`. Anything else has no anchor, and the comparison cannot run — which is
    the correct outcome, not a degradation.
    """
    if not asset:
        return None
    if asset.get("is_authentic"):
        return asset
    parent = asset.get("parent_sha256")
    return get_repo().find_asset_by_sha(parent) if parent else None


def _anchor_bytes(asset: dict | None) -> bytes | None:
    """Read the anchored original's media back out of storage."""
    if not asset:
        return None
    key = asset.get("b2_key") or key_from_url(asset.get("b2_url"))
    try:
        if key and not str(key).startswith("http"):
            return get_storage().get_bytes(key)
        url = asset.get("b2_url")
        if url:
            from ..generation import _fetch_bytes

            return _fetch_bytes(url)
    except Exception as exc:  # noqa: BLE001 — reported as "comparison unavailable"
        log.warning("resolve: anchor fetch failed for %s (%s)", asset.get("sha256"), exc)
    return None


def _make_match_call(settings):
    """The injected comparison transport, or None when the instance can't run it.

    Reuses the QA evaluator model, which was benchmarked on exactly this question (see
    registry.py) — a dispute report is not the place to introduce an unproven model.
    """
    if not (settings.qa_vlm_enabled and settings.gmi_api_key):
        return None
    from functools import partial

    from originshot_pipelines.registry import GMI_CHAT_BASE_URL, QA_VISION_MODEL

    return partial(
        resolve_lib.vlm_item_match,
        api_key=settings.gmi_api_key,
        base_url=GMI_CHAT_BASE_URL,
        model=QA_VISION_MODEL,
        timeout=max(settings.qa_vlm_timeout_seconds, 90),
    )


def _render_and_store(record: dict, settings) -> tuple[str | None, str | None]:
    """Render the PDF, store it content-addressably, and record its hash on the report.

    Best-effort by contract: the findings are the product and they are already persisted.
    A PDF that fails to render or upload costs the caller a download link, not the report.
    """
    try:
        origin = settings.origins[0].rstrip("/") if settings.origins else ""
        pdf = resolve_lib.build_dispute_report(
            record,
            verify_base_url=f"{origin}/verify",
            report_base_url=f"{origin}/resolve" if origin else None,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("resolve: report render failed (%s)", exc)
        return None, None

    sha = hashlib.sha256(pdf).hexdigest()
    key = storage_key(sha, ".pdf").replace("assets/", "reports/", 1)
    try:
        get_storage().put_bytes(key, pdf, "application/pdf")
        url = get_storage().presigned_get(key)
    except Exception as exc:  # noqa: BLE001
        log.warning("resolve: report upload failed (%s)", exc)
        return sha, None

    # Write the hash back onto the stored record — this is what makes the document
    # checkable later: a holder can re-hash their PDF and confirm it against what we issued.
    record["report_sha256"] = sha
    record["report_key"] = key
    get_repo().update_dispute_report(record["id"],
                                     {"report_sha256": sha, "report_key": key})
    return sha, url


def _to_out(record: dict, pdf_sha: str | None, pdf_url: str | None) -> ResolveOut:
    return ResolveOut(
        id=record["id"],
        issued_at=record["issued_at"],
        finding=record["finding"],
        severity=record["severity"],
        headline=record["headline"],
        detail=record["detail"],
        listing=record["listing"],
        anchor=record.get("anchor"),
        received=record.get("received"),
        match=record.get("match"),
        match_unavailable=record.get("match_unavailable"),
        report_sha256=pdf_sha or record.get("report_sha256"),
        report_url=pdf_url,
    )
