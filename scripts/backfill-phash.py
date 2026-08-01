#!/usr/bin/env python
"""Backfill the perceptual-hash index from the bytes already stored on B2.

**Why this exists.** `phash` is computed inline during generation (`app/generation.py`), so
only assets created *after* Verify in the Wild shipped carry one. Everything generated before
that is invisible to the buyer-facing `/check` surface — and worse than invisible: a sparse
index makes the nearest-neighbour search return a *distant* asset as its best candidate, so
the public verifier confidently names the wrong file's provider, model and lineage.

Measured against production before this script existed: of the eleven assets on the marketing
site, five matched nothing at all and five matched the wrong asset — four of those flagged as
confident matches. One was correct. The threshold retune in `perceptual.py` removes most of
the wrong answers; only a complete index makes the right ones win, because an asset can only
match itself at distance 0 if its own hash is in the index.

Reads each asset's bytes back from B2 by its stored `b2_key`, recomputes the pHash from the
pixels, and writes both the asset field and the flat `phash_index` collection that
`find_similar_by_phash` scans. Nothing is generated and no provider is called — this is pure
re-derivation from bytes we already hold, so it is free and safe to re-run.

Idempotent by construction: an asset that already has a matching pHash is skipped, and the
index document is keyed by sha256, so a re-run overwrites rather than duplicating. Assets whose
bytes can't be fetched or decoded are reported and left alone — a pHash is best-effort metadata
and a missing one is strictly better than a wrong one.

Images only. A pHash of one video frame would be a single-frame claim the feature can't stand
behind, which is the same reason `generation.py` skips video inline.

Usage (from the repo root, backend venv active, .env populated):

    python scripts/backfill-phash.py              # report what would change (default)
    python scripts/backfill-phash.py --apply      # write the pHashes and the index
    python scripts/backfill-phash.py --apply --recompute   # also refresh existing pHashes
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the pHashes and index entries (default: report only)")
    ap.add_argument("--recompute", action="store_true",
                    help="also recompute assets that already carry a pHash")
    args = ap.parse_args()

    load_dotenv(REPO / ".env")
    # The backend package owns storage config and the pHash implementation; import it the same
    # way the app does rather than reimplementing either here.
    sys.path.insert(0, str(REPO / "backend"))

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if cred_path and not os.path.isabs(cred_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(REPO / cred_path)
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return _fail("GOOGLE_APPLICATION_CREDENTIALS is not set — populate .env first.")

    from app.config import get_settings
    from app.generation import _ext_for
    from app.storage import get_storage, key_from_url, storage_key
    from originshot_pipelines.perceptual import phash

    def resolve_key(a: dict) -> str | None:
        """Where this asset's bytes live on B2, trying every shape a record has ever used.

        Older rows predate `b2_key` and carry only the sink's unsigned `b2_url`; older ones
        still carry neither, but every stored object is content-addressed, so the key is
        recomputable from the sha and the MIME type. A wrong guess costs one failed GET and is
        reported — far better than silently leaving an asset out of the index, which is the
        state that made the public verifier answer with the wrong file in the first place.
        """
        if a.get("b2_key"):
            return a["b2_key"]
        if a.get("b2_url") and (key := key_from_url(a["b2_url"])):
            return key
        if a.get("sha256"):
            return storage_key(a["sha256"], _ext_for(a.get("mime_type")))
        return None

    if not get_settings().b2_configured:
        return _fail("B2 is not configured — this script reads asset bytes from the bucket.")

    import firebase_admin
    from firebase_admin import credentials, firestore

    firebase_admin.initialize_app(
        credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]))
    db = firestore.client()
    storage = get_storage()

    # Unfiltered collection-group stream — the same index-free shape repo.find_sku_by_id uses,
    # so this works on a fresh Firestore project with no composite indexes defined.
    assets = [(snap.reference, snap.to_dict() or {})
              for snap in db.collection_group("assets").stream()]

    images = [(ref, a) for ref, a in assets
              if str(a.get("mime_type") or "").lower().startswith("image/")]

    print(f"{len(assets)} asset(s), {len(images)} image(s)")

    written = skipped = failed = 0
    for ref, a in images:
        sha = a.get("sha256")
        label = f"{(sha or '?')[:12]}… {a.get('style') or '-':<10}"

        if a.get("phash") and not args.recompute:
            skipped += 1
            continue
        key = resolve_key(a)
        if not sha or not key:
            print(f"  {label} SKIP   no sha256 or resolvable B2 key on the record")
            failed += 1
            continue

        try:
            data = storage.get_bytes(key)
        except Exception as exc:  # noqa: BLE001 — one unreadable object must not stop the pass
            print(f"  {label} FAIL   could not read {key} ({type(exc).__name__})")
            failed += 1
            continue

        # NOTE: this hashes the *stored* bytes, which for a generated asset are the
        # manifest-embedded ones. That is correct and matches what a buyer holds: embedding
        # writes a metadata chunk (PNG iTXt / JPEG APP1 / WebP XMP) and never touches pixels,
        # so the pHash is identical either side of the embed.
        value = phash(data)
        if value is None:
            print(f"  {label} FAIL   bytes did not decode as an image")
            failed += 1
            continue
        if value == a.get("phash"):
            skipped += 1
            continue

        verb = "would write" if not args.apply else "wrote"
        print(f"  {label} {verb} {value}")
        if not args.apply:
            written += 1
            continue

        ref.set({"phash": value}, merge=True)
        # The flat index is what the public verifier scans; the asset field alone would leave
        # the asset still invisible to /check. Same payload shape add_asset writes.
        db.collection("phash_index").document(sha).set({
            "phash": value,
            "sha256": sha,
            "uid": a.get("owner_uid"),
            "sku_id": a.get("sku_id"),
            "asset_id": a.get("id"),
        })
        written += 1

    index_size = sum(1 for _ in db.collection("phash_index").stream())
    verb = "written" if args.apply else "pending (dry run — pass --apply)"
    print(f"\n{written} {verb}, {skipped} already current, {failed} could not be hashed")
    print(f"phash_index now holds {index_size} entr{'y' if index_size == 1 else 'ies'}")
    if not args.apply and written:
        print("\nRe-run with --apply to write them.")
    return 0


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
