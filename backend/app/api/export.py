"""Export — assemble a real, downloadable per-SKU pack as a ZIP.

The pack is built to be *usable* (drag the right folder straight into a listing) and
*provable* (the provenance chain survives the export):

    OriginShot-<sku>/
      README.txt                     what's inside + how to verify
      disclosure.txt                 AI-disclosure statement per asset
      pack.json                      machine-readable index
      verified/                      byte-exact masters — embedded manifests INTACT
      manifests/                     sidecar provenance JSON per asset
      amazon/ etsy/ shopify/ ...     marketplace renditions at exact dimensions

Marketplace renditions are re-encoded to hit exact listing dimensions, which necessarily
drops the embedded manifest. That is why `verified/` ships the untouched bytes alongside:
the seller gets listing-ready files AND files that still pass /verify and `genblaze
verify`. See ../../docs/SECURITY.md §11.
"""
from __future__ import annotations

import io
import json
import logging
import re
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from originshot_pipelines.listing import listing_text
from originshot_pipelines.presets import get_preset, preset_targets, render_for_preset

from ..auth import CurrentUser, get_current_user
from ..config import get_settings
from ..models import ExportRequest, Modality
from ..repo import get_repo
from ..storage import get_storage, key_from_url
from ..util import disclosure

router = APIRouter(tags=["export"])
log = logging.getLogger("originshot.export")

_VIDEO_EXT = ".mp4"


def _slug(value: str | None, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:40] or fallback


def _asset_key(asset: dict) -> str | None:
    """Storage key for an asset, or None when only an off-bucket URL is known."""
    key = asset.get("b2_key") or key_from_url(asset.get("b2_url"))
    return key if key and not str(key).startswith("http") else None


def _ext_for(asset: dict) -> str:
    return {
        "image/png": ".png", "image/jpeg": ".jpg",
        "image/webp": ".webp", "video/mp4": _VIDEO_EXT,
    }.get((asset.get("mime_type") or "").lower(), ".png")


def _label(asset: dict) -> str:
    """Stable, human-readable filename stem, e.g. `studio-1a2b3c4d`."""
    return f"{asset.get('style') or 'asset'}-{(asset.get('sha256') or '')[:8]}"


@router.post("/skus/{sku_id}/export")
def export_pack(
    sku_id: str,
    body: ExportRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    repo = get_repo()
    sku = repo.get_sku(user.uid, sku_id)
    if not sku:
        raise HTTPException(404, "Not found")

    assets = repo.list_assets(user.uid, sku_id)
    if not assets:
        raise HTTPException(400, "Nothing to export — generate assets first")

    marketplaces = [m.value for m in body.marketplaces] if body else []
    storage = get_storage()
    root = f"OriginShot-{_slug(sku.get('title'), sku_id)}"

    buf = io.BytesIO()
    disclosures: list[str] = []
    rendered = skipped = 0
    # The main image's master bytes, for the compliance scorecard: prefer studio (that's
    # the marketplace main image), fall back to the first still we manage to read.
    scorecard_master: bytes | None = None
    scorecard_is_studio = False

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for asset in assets:
            key = _asset_key(asset)
            if not key:
                skipped += 1
                continue
            try:
                data = storage.get_bytes(key)
            except Exception as exc:  # noqa: BLE001 — one bad object must not kill the pack
                log.warning("export: could not read %s (%s)", key, exc)
                skipped += 1
                continue

            name, ext = _label(asset), _ext_for(asset)
            is_video = asset.get("modality") == Modality.video.value or ext == _VIDEO_EXT

            # 1. Byte-exact master — embedded manifest intact, still verifiable.
            zf.writestr(f"{root}/verified/{name}{ext}", data)
            disclosures.append(f"{name}{ext}\n    {disclosure(asset)}")

            # 2. Sidecar provenance manifest, when one was persisted to B2.
            manifest_key = asset.get("manifest_key")
            if manifest_key and not str(manifest_key).startswith("http"):
                try:
                    zf.writestr(f"{root}/manifests/{name}.json", storage.get_bytes(manifest_key))
                except Exception as exc:  # noqa: BLE001
                    log.warning("export: manifest %s unavailable (%s)", manifest_key, exc)

            # 3. Marketplace-formatted renditions (still images only).
            if is_video:
                continue
            if scorecard_master is None or (
                not scorecard_is_studio and asset.get("style") == "studio"
            ):
                scorecard_master = data
                scorecard_is_studio = asset.get("style") == "studio"
            for marketplace in marketplaces:
                preset = get_preset(marketplace)
                if not preset:
                    continue
                try:
                    out, out_ext = render_for_preset(data, preset)
                    zf.writestr(f"{root}/{marketplace}/{name}{out_ext}", out)
                    rendered += 1
                except Exception as exc:  # noqa: BLE001 — a bad render must not kill the pack
                    log.warning("export: render %s for %s failed (%s)", name, marketplace, exc)

        # Listing copy, when it has been generated: one paste-ready .txt per channel plus
        # the machine-readable original. Copy discloses itself the same way the images do.
        stored_listing = sku.get("listing")
        if stored_listing:
            zf.writestr(f"{root}/listing/listing.json",
                        json.dumps(stored_listing, indent=2))
            for market, entry in (stored_listing.get("marketplaces") or {}).items():
                if marketplaces and market not in marketplaces:
                    continue
                zf.writestr(
                    f"{root}/listing/{market}.txt",
                    listing_text(market, entry, stored_listing.get("disclosure", "")),
                )

        # Compliance scorecard, measured on the same render path the folders above used.
        compliance_items: list[dict] = []
        if scorecard_master is not None:
            try:
                from originshot_pipelines.compliance import studio_scorecard

                compliance_items = studio_scorecard(
                    scorecard_master, marketplaces or None
                )
            except Exception as exc:  # noqa: BLE001 — the scorecard must not kill the pack
                log.warning("export: compliance scorecard failed (%s)", exc)

        # Certificate of Provenance + QR badge: the tangible proof sheet. The frontend
        # origin hosts /verify, so the QR resolves for anyone who scans it from a listing.
        try:
            from originshot_pipelines.certificate import build_certificate, qr_png

            verify_base = get_settings().origins[0].rstrip("/") + "/verify"
            zf.writestr(f"{root}/certificate.pdf",
                        build_certificate(sku, assets, verify_base_url=verify_base))
            original_asset = next((a for a in assets if a.get("is_authentic")), None)
            if original_asset and original_asset.get("sha256"):
                zf.writestr(f"{root}/verify-qr.png",
                            qr_png(f"{verify_base}/{original_asset['sha256']}"))
        except Exception as exc:  # noqa: BLE001 — the certificate must not kill the pack
            log.warning("export: certificate generation failed (%s)", exc)

        targets = preset_targets(marketplaces)
        zf.writestr(f"{root}/disclosure.txt", _disclosure_doc(sku, disclosures))
        zf.writestr(f"{root}/README.txt", _readme_doc(sku, targets, len(assets), rendered))
        zf.writestr(f"{root}/pack.json", json.dumps({
            "sku_id": sku_id,
            "title": sku.get("title"),
            "asset_count": len(assets),
            "marketplaces": marketplaces,
            "presets": targets,
            "renditions": rendered,
            "skipped": skipped,
            "compliance": compliance_items,
            "assets": [
                {
                    "file": f"{_label(a)}{_ext_for(a)}",
                    "style": a.get("style"),
                    "sha256": a.get("sha256"),
                    "is_authentic": bool(a.get("is_authentic")),
                    "provider": a.get("provider"),
                    "model": a.get("model"),
                    "parent_sha256": a.get("parent_sha256"),
                    "manifest_verified": a.get("manifest_verified"),
                }
                for a in assets
            ],
        }, indent=2))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{root}.zip"',
            # Let the browser read the filename back on a cross-origin fetch download.
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


def _disclosure_doc(sku: dict, entries: list[str]) -> str:
    return "\n".join([
        f"AI-DISCLOSURE — {sku.get('title') or 'Product'}",
        "=" * 60,
        "",
        "Generated with OriginShot. Every file in verified/ carries an embedded, SHA-256",
        "anchored Genblaze provenance manifest and can be re-verified from its own bytes —",
        "no trust in this document required.",
        "",
        *entries,
        "",
        "Verify any file at https://originshot.vercel.app/verify",
    ])


def _readme_doc(sku: dict, targets: list[dict], asset_count: int, rendered: int) -> str:
    lines = [
        f"OriginShot export — {sku.get('title') or 'Product'}",
        "=" * 60,
        "",
        f"{asset_count} source asset(s) · {rendered} marketplace rendition(s)",
        "",
        "FOLDERS",
        "  verified/    Byte-exact masters. Embedded provenance manifests are INTACT —",
        "               upload one to /verify (or run `genblaze verify <file>`) to prove",
        "               which pixels are authentic and which are AI-generated.",
        "  manifests/   Sidecar provenance JSON (provider, model, parameters, lineage).",
        "  <market>/    Listing-ready renditions at that channel's exact dimensions.",
        "               Re-encoded to hit those dimensions, so the embedded manifest is",
        "               NOT preserved here — use verified/ for proof, these for listing.",
        "",
        "  listing/         Paste-ready listing copy per marketplace (when generated),",
        "                   written to each channel's title/bullet/tag rules.",
        "",
        "  certificate.pdf  One-page Certificate of Provenance: every hash, model, and",
        "                   QA verdict, plus a QR code into the public verifier.",
        "  verify-qr.png    The QR badge alone - drop it into a listing so buyers can",
        "                   scan straight to the proof.",
        "  disclosure.txt   Per-asset AI-disclosure statements (EU AI Act / marketplace",
        "                   transparency rules).",
        "  pack.json        Machine-readable index of the whole pack, including the",
        "                   marketplace compliance scorecard.",
        "",
    ]
    if targets:
        lines.append("MARKETPLACE TARGETS")
        lines += [
            f"  {t['marketplace']:<10} {t['width']}x{t['height']}  "
            f"background={t['background']}  — {t['notes']}"
            for t in targets
        ]
    else:
        lines.append("No marketplace selected — verified masters and manifests only.")
    return "\n".join(lines)
