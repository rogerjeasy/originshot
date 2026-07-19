"""Catalog Mode endpoints — run generation across many SKUs, then download the lot.

Uploads deliberately do NOT happen here. The client creates each SKU and uploads its photo
through the existing per-SKU routes, then hands this endpoint the ids. That keeps a single
hardened upload path (magic-byte validation, pixel caps, bomb guards, EXIF stripping) rather
than growing a second bulk one, keeps a ten-photo catalog off one multi-hundred-megabyte
request that a free-tier instance would drop, and lets the UI show real per-file progress
instead of one opaque bar.

See app/batches.py for the run semantics (concurrency, per-item credit, blocked vs failed).
"""
from __future__ import annotations

import io
import logging
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .. import batches as batch_lib
from .. import credits, pricing
from ..auth import CurrentUser, get_current_user
from ..config import get_settings
from ..models import (BatchCreate, BatchEstimateOut, BatchItemStatus, BatchOut, BatchStatus,
                      ExportRequest, Style, utcnow)
from ..repo import get_repo
from ..storage import get_storage
from .export import pack_root, write_pack
from .generate import assert_generation_available

router = APIRouter(prefix="/batches", tags=["batches"])
log = logging.getLogger("originshot.batches")


def _resolve_skus(uid: str, sku_ids: list[str]) -> list[dict]:
    """Every id must belong to the caller and carry an anchored original.

    Validated up front and as a whole: a catalog that silently dropped two of your twelve
    photos would be worse than one that refused and said which.
    """
    repo = get_repo()
    resolved: list[dict] = []
    missing: list[str] = []
    no_photo: list[str] = []
    for sku_id in dict.fromkeys(sku_ids):          # de-dupe, preserve order
        sku = repo.get_sku(uid, sku_id)
        if not sku:
            missing.append(sku_id)
        elif not sku.get("original_sha256"):
            no_photo.append(sku.get("title") or sku_id)
        else:
            resolved.append(sku)
    if missing:
        raise HTTPException(404, f"Unknown product(s): {', '.join(missing[:5])}")
    if no_photo:
        raise HTTPException(
            400, f"No product photo uploaded for: {', '.join(no_photo[:5])}")
    return resolved


@router.post("/estimate", response_model=BatchEstimateOut)
def estimate_batch(body: BatchCreate, user: CurrentUser = Depends(get_current_user)):
    """What this catalog will cost and how long it will take, before committing to it."""
    skus = _resolve_skus(user.uid, body.sku_ids)
    settings = get_settings()
    repo = get_repo()

    # Idempotent, and needed here for the same reason it's needed at submit: a user's first
    # authenticated call isn't necessarily /me, and quoting a brand-new seller's catalog as
    # unaffordable against a welcome credit that hasn't been issued yet is a false refusal
    # on the very first screen they see.
    credits.ensure_signup_grant(user.uid)

    per_sku = pricing.estimate_styles(body.styles)
    total = round(per_sku * len(skus), 4)
    balance = credits.get_balance(user.uid)
    used = repo.count_generations_today(user.uid)

    # Wall clock, not summed work: `catalog_concurrency` SKUs run at once, so a 10-SKU
    # catalog at concurrency 2 takes about five sequential packs, not ten.
    lanes = batch_lib.concurrency_for(len(skus))
    waves = -(-len(skus) // lanes)                 # ceil division
    eta = pricing.eta_seconds(body.styles) * waves

    return BatchEstimateOut(
        skus=len(skus),
        styles=body.styles,
        per_sku_usd=per_sku,
        total_estimate_usd=total,
        balance_usd=balance,
        affordable=total <= balance,
        eta_seconds=eta,
        quota_remaining=max(0, settings.daily_generation_quota - used),
        basis=pricing.ESTIMATE_ONLY,
    )


@router.post("", response_model=BatchOut, status_code=202)
async def create_batch(
    body: BatchCreate,
    background: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    settings = get_settings()
    if len(body.sku_ids) > settings.catalog_max_skus:
        raise HTTPException(
            400, f"A catalog run is limited to {settings.catalog_max_skus} products.")

    skus = _resolve_skus(user.uid, body.sku_ids)
    assert_generation_available()
    credits.ensure_signup_grant(user.uid)

    styles = [s.value for s in body.styles]
    marketplaces = [m.value for m in body.marketplaces]
    per_sku = pricing.estimate_styles(body.styles)

    # A pre-flight check, NOT a hold — each job holds its own cost as it starts (see
    # app/batches.py). Refusing a catalog nobody can afford up front is a better error than
    # letting it run three SKUs deep and stall; a catalog that becomes unaffordable partway
    # through is still handled, per item, as `blocked`.
    balance = credits.get_balance(user.uid)
    total = round(per_sku * len(skus), 4)
    if total > balance:
        raise credits.InsufficientCredit(balance, total)

    lanes = batch_lib.concurrency_for(len(skus))
    batch = get_repo().create_batch(user.uid, {
        "title": body.title,
        "status": BatchStatus.queued.value,
        "styles": styles,
        "marketplaces": marketplaces,
        "concurrency": lanes,
        "cost_estimate": total,
        "eta_seconds": pricing.eta_seconds(body.styles) * (-(-len(skus) // lanes)),
        "items": [
            {"sku_id": s["id"], "title": s.get("title"),
             "status": BatchItemStatus.pending.value, "asset_count": 0}
            for s in skus
        ],
        "started_at": None,
        "finished_at": None,
    })

    background.add_task(batch_lib.process_batch, user.uid, batch["id"])
    return batch


@router.get("", response_model=list[BatchOut])
def list_batches(user: CurrentUser = Depends(get_current_user)):
    return get_repo().list_batches(user.uid)


@router.get("/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: str, user: CurrentUser = Depends(get_current_user)):
    batch = get_repo().get_batch(user.uid, batch_id)
    if not batch:
        raise HTTPException(404, "Not found")
    return batch


@router.post("/{batch_id}/export")
def export_catalog(
    batch_id: str,
    body: ExportRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """One ZIP containing a full, normal pack per SKU.

    Each product's folder is byte-for-byte what the single-SKU export produces — same
    `verified/` masters, same certificate, same disclosure — because both go through
    `export.write_pack`. A catalog download is the seller's whole shop, so it must not be a
    reduced form of the thing they already trust.
    """
    repo = get_repo()
    batch = repo.get_batch(user.uid, batch_id)
    if not batch:
        raise HTTPException(404, "Not found")

    marketplaces = [m.value for m in body.marketplaces] if body else []
    storage = get_storage()
    root = f"OriginShot-catalog-{batch_id[:8]}"

    packed: list[dict] = []
    empty: list[str] = []
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in batch.get("items") or []:
            sku_id = item.get("sku_id")
            sku = repo.get_sku(user.uid, sku_id) if sku_id else None
            if not sku:
                continue
            assets = repo.list_assets(user.uid, sku_id)
            if not assets:
                empty.append(sku.get("title") or sku_id)
                continue
            try:
                stats = write_pack(
                    zf, sku=sku, sku_id=sku_id, assets=assets,
                    marketplaces=marketplaces,
                    root=f"{root}/{pack_root(sku, sku_id)}", storage=storage,
                )
            except Exception as exc:  # noqa: BLE001 — one bad SKU must not kill the catalog
                log.warning("catalog export: pack failed for %s (%s)", sku_id, exc)
                empty.append(sku.get("title") or sku_id)
                continue
            packed.append({"sku_id": sku_id, "title": sku.get("title"), **stats})

        if not packed:
            raise HTTPException(400, "Nothing to export — no product in this catalog has "
                                     "generated assets yet")

        zf.writestr(f"{root}/catalog.json", _catalog_index(batch, packed, empty,
                                                           marketplaces))
        zf.writestr(f"{root}/README.txt", _catalog_readme(batch, packed, empty))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{root}.zip"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


def _catalog_index(batch: dict, packed: list[dict], empty: list[str],
                   marketplaces: list[str]) -> str:
    import json

    return json.dumps({
        "batch_id": batch.get("id"),
        "title": batch.get("title"),
        "status": batch.get("status"),
        "styles": batch.get("styles"),
        "marketplaces": marketplaces,
        "generated_at": utcnow().isoformat(),
        "products_included": len(packed),
        "products_without_assets": empty,
        "cost_actual_usd": batch.get("cost_actual"),
        "products": packed,
    }, indent=2, default=str)


def _catalog_readme(batch: dict, packed: list[dict], empty: list[str]) -> str:
    lines = [
        f"OriginShot catalog export — {batch.get('title') or 'Untitled catalog'}",
        "=" * 64,
        "",
        f"{len(packed)} product pack(s) in this archive.",
        "",
        "Each folder is a complete, self-contained OriginShot pack — identical in structure",
        "to a single-product export. Open any one of them and read its own README.txt for",
        "what the subfolders mean and how to verify the files inside.",
        "",
        "  <product>/verified/     byte-exact masters, embedded manifests INTACT",
        "  <product>/manifests/    sidecar provenance JSON",
        "  <product>/certificate.pdf   Certificate of Provenance + QR",
        "  <product>/<market>/     listing-ready renditions at exact dimensions",
        "",
        "  catalog.json            machine-readable index across every product here",
        "",
    ]
    if empty:
        lines += [
            "NOT INCLUDED",
            "  These products had no generated assets when this archive was built —",
            "  they were skipped rather than shipped as empty folders:",
            *[f"    - {name}" for name in empty[:50]],
            "",
        ]
    lines.append("Verify any file at https://originshot.vercel.app/verify")
    return "\n".join(lines)
