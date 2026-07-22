"""Verify Anywhere — the public, no-login *buyer* surface.

Every other verification path assumes you already hold the file. A buyer looking at a live
marketplace listing does not: they have a link, or at most the photo they can drag off the
page. This endpoint meets them there — paste a listing/image URL or drop the photo, and it
runs the **same** verification core as `/verify` (`verify_bytes`), so the perceptual "Verify in
the Wild" tier can recognise the re-encoded, manifest-stripped copy a marketplace actually
serves and trace it back to a known OriginShot asset.

Public and unauthenticated on purpose (a buyer has no account), and — crucially, UNLIKE
`/resolve` — it calls **no** provider: pHash is local numpy and the ledger lookup is a local
scan, so there is no denial-of-wallet exposure. The one new risk is SSRF from fetching a
caller-supplied URL, contained entirely in `app.fetch`. On top of that: a per-IP rate limit,
an on/off switch, and the same privacy posture as `/resolve` — the response carries lineage
*hashes* and metadata, never the seller's private original image.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from originshot_pipelines import perceptual

from ..config import get_settings
from ..fetch import FetchError, extract_image_urls, fetch_url
from ..models import CheckResult, VerifyResult
from ..security import limiter
from .verify import verify_bytes

log = logging.getLogger("originshot.check")

router = APIRouter(tags=["check"])


def _rate_limit() -> str:
    return get_settings().verify_wild_rate_limit


@router.post("/check", response_model=CheckResult)
@limiter.limit(_rate_limit)
async def check_anywhere(
    request: Request,                                   # required by slowapi's decorator
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
):
    """Check a listing photo the way a buyer would: from a link or a dropped file."""
    settings = get_settings()
    if not settings.verify_wild_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Verify Anywhere is disabled on this instance.")

    url = (url or "").strip()
    if (file is None) == (not url):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Provide exactly one of: a link to check, or an image file.")

    # ── Dropped / pasted file — identical to /verify, wrapped for the buyer UI. ──────────
    if file is not None:
        data = await file.read()
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")
        return CheckResult(source="upload", result=verify_bytes(data))

    # ── A caller-supplied URL — fetched only through the SSRF-hardened path. ─────────────
    try:
        fetched = fetch_url(
            url,
            timeout=settings.verify_wild_fetch_timeout_seconds,
            max_bytes=settings.max_upload_bytes,
        )
    except FetchError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None

    # A direct image link (or a mislabeled one that still decodes) is checked as-is.
    if not fetched.is_html:
        return CheckResult(
            source="url_image", source_url=url, result=verify_bytes(fetched.content)
        )

    # An HTML listing page: pull the candidate photos and check them, best match wins.
    candidates = extract_image_urls(fetched.content, fetched.final_url,
                                    settings.verify_wild_max_images)
    if not candidates:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Couldn't find a product image on that page — try dropping the photo instead, "
            "or paste the direct image link.",
        )

    best: VerifyResult | None = None
    scanned = 0
    for image_url in candidates:
        try:
            image = fetch_url(
                image_url,
                timeout=settings.verify_wild_fetch_timeout_seconds,
                max_bytes=settings.max_upload_bytes,
            )
        except FetchError as exc:  # one bad <img> must not sink the whole check
            log.info("check: candidate fetch skipped (%s)", exc)
            continue
        if not image.is_image:
            continue
        scanned += 1
        candidate = verify_bytes(image.content)
        if _is_definitive(candidate):
            return CheckResult(source="listing_page", source_url=url,
                               images_scanned=scanned, result=candidate)
        if best is None or _rank(candidate) > _rank(best):
            best = candidate

    if best is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Couldn't read a usable image from that page — try dropping the photo instead.",
        )
    return CheckResult(source="listing_page", source_url=url,
                       images_scanned=scanned, result=best)


def _is_definitive(r: VerifyResult) -> bool:
    """A cryptographic hit (exact-hash record or a surviving embedded manifest): stop looking."""
    return r.found or r.embedded


def _rank(r: VerifyResult) -> float:
    """Order two non-definitive results so the strongest perceptual match wins the page.

    A closer pHash (smaller distance) is the better lead; anything with no match at all ranks
    below every match. Kept tiny and total so the loop above is a plain max.
    """
    if _is_definitive(r):
        return 1e6
    if r.perceptual is not None:
        return float(perceptual.MATCH_WEAK - r.perceptual.distance)
    return -1.0
