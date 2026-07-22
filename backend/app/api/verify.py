"""Public provenance verification.

Returns ONLY non-sensitive integrity + lineage — never private media, prompts, or owner
info. In production, integrity is confirmed against the embedded Genblaze manifest.
See ../docs/SECURITY.md §11.
"""
import hashlib
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from originshot_pipelines import perceptual, provenance

from .. import transparency
from ..config import get_settings
from ..models import PerceptualMatch, VerifyResult
from ..repo import get_repo
from ..util import disclosure

router = APIRouter(tags=["verify"])


@router.post("/verify", response_model=VerifyResult)
async def verify_upload(file: UploadFile = File(...)):
    """Public: re-prove a file's provenance from its **actual bytes**.

    Extracts the embedded manifest and re-runs `verify()` (never trusts stored state), then
    looks up our record by the uploaded bytes' SHA-256 for non-sensitive lineage. Works on
    a downloaded generated asset (`full`-mode files self-verify here with no DB record).
    """
    settings = get_settings()
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")
    return verify_bytes(data)


def verify_bytes(data: bytes) -> VerifyResult:
    """Re-prove a file's provenance from its exact bytes — the shared verification core.

    Both the seller-facing `POST /verify` and the buyer-facing `POST /check` call this, so the
    manifest/exact-hash/perceptual precedence lives in exactly ONE place and the two public
    surfaces can never disagree about the same file. Returns only non-sensitive integrity +
    lineage; it never reaches for private media, prompts or owner info.
    """
    sha = hashlib.sha256(data).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "upload"
        path.write_bytes(data)
        extracted = provenance.verify_file(path)  # sniffs MIME, extracts + verifies

    repo = get_repo()
    asset = repo.find_asset_by_sha(sha)
    found = bool(asset)

    # ── Verify in the Wild ─────────────────────────────────────────────
    # Only when BOTH cryptographic tiers came up empty: no embedded manifest AND no exact-hash
    # record. That is the fingerprint of a marketplace re-encode — the manifest stripped, the
    # bytes (and so the SHA) changed — which is exactly the file the cryptographic tiers can
    # say nothing about and the one a buyer is most likely to be holding. An honest,
    # unmodified OriginShot file never reaches here, so this costs a pHash scan only on files
    # that would otherwise get a flat "unknown".
    perceptual_match: PerceptualMatch | None = None
    if not extracted["present"] and not found:
        query = perceptual.phash(data)
        if query is not None:
            near = repo.find_similar_by_phash(query, perceptual.MATCH_WEAK)
            if near is not None:
                dist = near["phash_distance"]
                matched_sha = near["sha256"]
                perceptual_match = PerceptualMatch(
                    matched_sha256=matched_sha,
                    distance=dist,
                    confidence=perceptual.confidence(dist),
                    strong=dist <= perceptual.MATCH_STRONG,
                    style=near.get("style"),
                    provider=near.get("provider"),
                    model=near.get("model"),
                    parent_sha256=near.get("parent_sha256"),
                    matched_in_ledger=transparency.position_for(matched_sha) is not None,
                )

    if extracted["present"]:
        verified = extracted["verified"]                       # integrity proven from bytes
    elif found:
        mv = asset.get("manifest_verified")                    # fall back to stored result
        verified = True if mv is None else bool(mv)
    else:
        verified = False

    # Content-binding: do the bytes match the hash the manifest signed over? A byte-exact
    # match to a stored asset (found via SHA-256) is itself definitive content integrity.
    content_bound = extracted["content_bound"]
    if content_bound is None and found:
        content_bound = True

    if content_bound is False:
        # Manifest is intact but the media bytes don't match its signed content hash.
        disclosure_text = (
            "⚠ Tampered: this file carries a OriginShot manifest, but the media content has "
            "been altered and no longer matches the signed hash."
        )
    elif found:
        disclosure_text = disclosure(asset)
    elif extracted["present"]:
        disclosure_text = (
            "This file carries a "
            + ("verified" if verified else "invalid")
            + " OriginShot provenance manifest, but no matching record exists in this instance."
        )
    elif perceptual_match is not None:
        # No cryptographic provenance survived, but the pixels match a known asset. Stated as
        # a likeness, with the distance in the text, so it can never be mistaken for the
        # byte-exact guarantee the other branches make.
        strength = "closely matches" if perceptual_match.strong else "resembles"
        lineage = (
            f" It traces to authentic original {perceptual_match.parent_sha256[:12]}…"
            if perceptual_match.parent_sha256 else ""
        )
        disclosure_text = (
            f"No provenance manifest survives in this file (marketplaces re-encode images and "
            f"strip it), but it {strength} a known OriginShot asset "
            f"({perceptual_match.matched_sha256[:12]}…, perceptual distance "
            f"{perceptual_match.distance}/64).{lineage} This is a visual-similarity match — "
            f"evidence, not a cryptographic guarantee."
        )
    else:
        disclosure_text = "No embedded manifest and no record found for this file."

    return VerifyResult(
        sha256=sha,
        found=found,
        verified=verified,
        is_authentic=bool(asset.get("is_authentic")) if found else False,
        embedded=extracted["present"],
        content_bound=content_bound,
        modality=asset.get("modality") if found else None,
        style=asset.get("style") if found else None,
        provider=asset.get("provider") if found else None,
        model=asset.get("model") if found else None,
        parent_sha256=asset.get("parent_sha256") if found else None,
        created_at=asset.get("created_at") if found else None,
        disclosure=disclosure_text,
        ledger=transparency.position_for(sha),
        perceptual=perceptual_match,
    )


@router.get("/verify/{sha256}", response_model=VerifyResult)
def verify(sha256: str):
    asset = get_repo().find_asset_by_sha(sha256)
    if not asset:
        return VerifyResult(
            sha256=sha256, found=False, verified=False, is_authentic=False,
            disclosure="No record found for this hash.",
        )
    # Authentic originals have no manifest; generated assets carry manifest.verify() result.
    mv = asset.get("manifest_verified")
    verified = True if mv is None else bool(mv)
    return VerifyResult(
        sha256=sha256,
        found=True,
        verified=verified,
        is_authentic=bool(asset.get("is_authentic")),
        embedded=bool(asset.get("embedded")),
        modality=asset.get("modality"),
        style=asset.get("style"),
        provider=asset.get("provider"),
        model=asset.get("model"),
        parent_sha256=asset.get("parent_sha256"),
        created_at=asset.get("created_at"),
        disclosure=disclosure(asset),
        ledger=transparency.position_for(sha256),
    )


@router.get("/assets/{sha256}/manifest")
def manifest(sha256: str):
    asset = get_repo().find_asset_by_sha(sha256)
    if not asset:
        raise HTTPException(404, "Not found")
    # Minimal, non-sensitive manifest view (prompts/params redacted per EmbedPolicy).
    return {
        "sha256": asset["sha256"],
        "modality": asset.get("modality"),
        "style": asset.get("style"),
        "is_authentic": asset.get("is_authentic"),
        "provider": asset.get("provider"),
        "model": asset.get("model"),
        "parent_sha256": asset.get("parent_sha256"),
        "canonical_hash": asset.get("manifest_key"),
        "embedded": bool(asset.get("embedded")),
        "created_at": asset.get("created_at"),
    }
