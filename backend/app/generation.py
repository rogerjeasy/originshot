"""Generation engine — maps Genblaze pipeline runs (or a dev mock) to asset documents.

Real generation requires: Genblaze installed, a provider key (GMI), and B2 configured
(the Genblaze ObjectStorageSink writes to B2). Otherwise the dev mock runs so the full UX
works locally. Each style is isolated so one provider failure yields a *partial* result
rather than a total failure.
"""
from __future__ import annotations

import logging
import uuid

from .config import get_settings
from .models import Modality, Style

log = logging.getLogger("listsnap.generation")

GENERATED_STYLES = [Style.studio, Style.lifestyle, Style.onmodel, Style.variant, Style.video]

# Default variant sweep (kept small to bound cost).
VARIANT_COLORS = ["matte black", "sage green"]
VARIANT_ANGLES = ["three-quarter"]


def genblaze_available() -> bool:
    try:
        import genblaze_core  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def generation_mode() -> str:
    """"genblaze" only when the SDK, a provider key, and B2 are all configured."""
    s = get_settings()
    if s.gmi_api_key and s.b2_configured and genblaze_available():
        return "genblaze"
    return "mock"


def brand_prompt_fragment(brand: dict | None) -> str:
    """Full brand fragment for contextual styles (lifestyle/on-model/variant)."""
    if not brand:
        return ""
    parts = [str(brand[k]).strip() for k in ("vibe", "lighting", "palette", "props", "notes")
             if brand.get(k)]
    return "; ".join(parts)


def brand_tone_fragment(brand: dict | None) -> str:
    """Lighter fragment for studio/video — avoids palette/props that fight a pure-white bg."""
    if not brand:
        return ""
    parts = [str(brand[k]).strip() for k in ("vibe", "lighting") if brand.get(k)]
    return "; ".join(parts)


async def generate_assets(uid, sku, original, styles, *, storage, brand=None, marketplaces=None):
    """Return (asset_dicts, errors). `errors` non-empty + assets present ⇒ partial."""
    wanted = [Style(s) for s in styles if Style(s) in GENERATED_STYLES]
    if generation_mode() == "genblaze":
        return await _run_genblaze(sku, original, wanted, storage, brand, marketplaces or [])
    return _run_mock(sku, original, wanted), []


# ── Dev mock ───────────────────────────────────────────────────────────
def _run_mock(sku, original, wanted) -> list[dict]:
    run_id = f"mock-{uuid.uuid4().hex[:8]}"
    out: list[dict] = []
    for style in wanted:
        if style is Style.video:  # can't fabricate a video in the mock
            continue
        out.append({
            "sku_id": sku["id"],
            "sha256": original["sha256"],
            "b2_key": original["b2_key"],
            "b2_url": None,
            "modality": Modality.image.value,
            "style": style.value,
            "is_authentic": False,
            "parent_sha256": original["sha256"],
            "run_id": run_id,
            "provider": "mock-dev",
            "model": "passthrough",
            "manifest_key": None,
            "manifest_verified": None,
            "embedded": False,
            "mime_type": original.get("mime_type"),
            "width": original.get("width"),
            "height": original.get("height"),
            "duration": None,
        })
    return out


# ── Real Genblaze path ─────────────────────────────────────────────────
async def _run_genblaze(sku, original, wanted, storage, brand, marketplaces):
    from listsnap_pipelines import (
        lifestyle,
        onmodel,
        presets,
        storage as sink_module,
        studio,
        variants,
        video,
    )

    settings = get_settings()
    sink = sink_module.make_sink()
    source_uri = storage.presigned_get(original["b2_key"])
    desc = (sku.get("description") or sku.get("title") or "product").strip()
    parent = original["sha256"]
    img_t, vid_t = settings.image_timeout_seconds, settings.video_timeout_seconds

    brand_full = brand_prompt_fragment(brand)
    brand_tone = brand_tone_fragment(brand)
    studio_aspect = presets.studio_aspect_for(marketplaces)

    out: list[dict] = []
    errors: list[str] = []
    hero_url: str | None = None

    if Style.studio in wanted:
        try:
            res = await studio.build_studio_pipeline(
                source_uri, desc, brand_suffix=brand_tone, aspect=studio_aspect
            ).arun(sink=sink, timeout=img_t)
            asset = _map(sku, res, Style.studio, parent, storage)
            # The hero image feeds the image-to-video step. After embedding we store the
            # studio image under our own key, so presign that; else use the sink URL.
            hero_url = (
                storage.presigned_get(asset["b2_key"]) if asset.get("b2_key")
                else asset.get("b2_url")
            ) or hero_url
            out.append(asset)
        except Exception as e:  # noqa: BLE001
            errors.append(f"studio: {e}")

    if Style.lifestyle in wanted:
        try:
            for res in await lifestyle.run_lifestyle(source_uri, desc, sink, brand_suffix=brand_full):
                out.append(_map(sku, res, Style.lifestyle, parent, storage))
        except Exception as e:  # noqa: BLE001
            errors.append(f"lifestyle: {e}")

    if Style.onmodel in wanted:
        try:
            res = await onmodel.build_onmodel_pipeline(
                source_uri, desc, brand_suffix=brand_full
            ).arun(sink=sink, timeout=img_t)
            out.append(_map(sku, res, Style.onmodel, parent, storage))
        except Exception as e:  # noqa: BLE001
            errors.append(f"onmodel: {e}")

    if Style.variant in wanted:
        try:
            results = await variants.run_variants(
                source_uri, desc, sink, colors=VARIANT_COLORS, angles=VARIANT_ANGLES,
                brand_suffix=brand_full,
            )
            for res in results:
                out.append(_map(sku, res, Style.variant, parent, storage))
        except Exception as e:  # noqa: BLE001
            errors.append(f"variant: {e}")

    if Style.video in wanted:
        if hero_url:
            try:
                res = await video.build_hero_video(
                    hero_url, desc, brand_suffix=brand_tone
                ).arun(sink=sink, timeout=vid_t)
                out.append(_map(sku, res, Style.video, parent, storage))
            except Exception as e:  # noqa: BLE001
                errors.append(f"video: {e}")
        else:
            errors.append("video: requires a studio image (include 'studio' in styles)")

    return out, errors


def _map(sku, result, style: Style, parent: str, storage) -> dict:
    # Genblaze data shapes (verified against genblaze-core 0.3.2):
    #   * provider / model / cost live on the *Step*, not the Asset.
    #   * Asset exposes `media_type` (not `mime_type`), `url`, `sha256`, `size_bytes`,
    #     `width`, `height`, `duration` — and has no storage `key`.
    #   * Manifest exposes `canonical_hash`, `manifest_uri`, `verify()`.
    step = result.run.steps[0]
    asset = step.assets[0]
    run_id = getattr(getattr(result, "run", None), "run_id", None)
    manifest = getattr(result, "manifest", None)

    manifest_verified = None
    manifest_key = None
    if manifest is not None:
        try:
            manifest_verified = bool(manifest.verify())
        except Exception:  # noqa: BLE001
            manifest_verified = None
        # Prefer the sink-recorded sidecar URI; otherwise persist one ourselves.
        manifest_key = getattr(manifest, "manifest_uri", None) or _persist_manifest(
            storage, run_id or "run", style, manifest
        )

    modality = Modality.video if style is Style.video else Modality.image
    mime_type = getattr(asset, "media_type", None)
    out = {
        "sku_id": sku["id"],
        "sha256": getattr(asset, "sha256", None),
        # The Genblaze sink owns the stored object key; we keep its durable URL and let the
        # response layer presign by key when we manage the object ourselves.
        "b2_key": None,
        "b2_url": getattr(asset, "url", None),
        "modality": modality.value,
        "style": style.value,
        "is_authentic": False,
        "parent_sha256": parent,
        "run_id": run_id,
        "provider": getattr(step, "provider", None),
        "model": getattr(step, "model", None),
        "cost_usd": getattr(step, "cost_usd", None),
        "manifest_key": manifest_key,
        "manifest_verified": manifest_verified,
        "embedded": False,
        "mime_type": mime_type,
        "width": getattr(asset, "width", None),
        "height": getattr(asset, "height", None),
        "duration": getattr(asset, "duration", None),
    }

    # Embed the provenance manifest into the actual media bytes and store the embedded,
    # verifiable deliverable ourselves (content-addressable + presignable). Best-effort:
    # any failure leaves the sink-stored copy + manifest.verify() result untouched.
    if manifest is not None and get_settings().manifest_embed_mode.lower() != "none":
        try:
            _embed_and_store(result, out, storage, mime_type, manifest_key)
        except Exception as e:  # noqa: BLE001
            log.warning("manifest embed failed for %s (%s); using sink copy", style.value, e)

    return out


def _ext_for(mime_type: str | None) -> str:
    return {
        "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
        "video/mp4": ".mp4",
    }.get((mime_type or "").lower(), ".bin")


def _fetch_bytes(url: str) -> bytes:
    """Download generated media bytes (monkeypatched in tests)."""
    import httpx

    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def _embed_and_store(result, out: dict, storage, mime_type: str | None, manifest_key) -> None:
    """Embed `result.manifest` into the media, store it via our storage, and re-verify.

    Mutates `out` in place: sets b2_key (our content-addressable key), clears b2_url,
    refreshes sha256 to the embedded bytes, and sets manifest_verified/embedded.
    """
    import hashlib
    import tempfile
    from pathlib import Path

    from listsnap_pipelines import provenance

    from .storage import storage_key

    url = out.get("b2_url")
    if not url:
        return
    data = _fetch_bytes(url)

    mode = get_settings().manifest_embed_mode.lower()
    ext = _ext_for(mime_type)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"asset{ext}"
        path.write_bytes(data)
        sidecar_uri = storage.presigned_get(manifest_key) if manifest_key else None
        provenance.embed_manifest(result, path, mode=mode, sidecar_uri=sidecar_uri)
        embedded_bytes = path.read_bytes()
        verified = provenance.extract_and_verify(path, mime_type or "")

    sha = hashlib.sha256(embedded_bytes).hexdigest()
    key = storage_key(sha, ext)
    storage.put_bytes(key, embedded_bytes, mime_type or "application/octet-stream")
    out.update({
        "b2_key": key,
        "b2_url": None,
        "sha256": sha,
        "manifest_verified": verified,
        "embedded": True,
    })


def _persist_manifest(storage, run_id: str, style: Style, manifest) -> str | None:
    """Best-effort: write a sidecar manifest JSON to B2 (prompts redacted by EmbedPolicy)."""
    try:
        data = None
        # Manifest API (genblaze-core 0.3.2): canonical JSON is the provenance source of
        # truth; fall back to plain pydantic serialization if unavailable.
        to_canonical = getattr(manifest, "to_canonical_json", None)
        if callable(to_canonical):
            data = to_canonical()
        elif hasattr(manifest, "model_dump_json"):
            data = manifest.model_dump_json()
        if data is None:
            return None
        if isinstance(data, str):
            data = data.encode("utf-8")
        key = f"manifests/{run_id}/{style.value}.json"
        storage.put_bytes(key, data, "application/json")
        return key
    except Exception as e:  # noqa: BLE001
        log.warning("manifest persist failed: %s", e)
        return None
