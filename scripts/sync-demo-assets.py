#!/usr/bin/env python
"""Sync real generated assets from Backblaze B2 into the marketing site.

The landing page shows OriginShot's actual output, not stock photography or
placeholder glyphs. This script pulls chosen assets straight from the B2 bucket,
resizes and re-encodes them to WebP for the web, and regenerates
`frontend/lib/demo-assets.ts`.

Filenames in the bucket are the assets' SHA-256 content hashes, and this script
carries those hashes through to the generated module. That means every hash
printed on the marketing site is the real one and resolves against /verify — the
provenance claim on the landing page is checkable, not decorative.

**Every pick is verified against the live public API before it is written.** The
site once shipped four hashes whose database rows had been deleted, so the
landing page's own "check this hash yourself" button answered *"No record found
for this hash"* — the worst possible failure for a product whose entire argument
is that you don't have to take its word for anything. A pick that does not
resolve is now a hard error, not a silent regression. `--offline` skips the check
for air-gapped runs; use it only when you already know the records are good.

The model and provider are read back from that same API response rather than
hardcoded here, so the site credits whichever provider actually served the run.
The pack below was served by OpenAI's `gpt-image-1` through the cross-provider
fallback, because GMI's image queue was out of credit at the time — a real
failover, and the page should say so rather than quietly claim GMI.

Usage (from the repo root, with the backend venv active and .env populated):

    python scripts/sync-demo-assets.py            # sync the current selection
    python scripts/sync-demo-assets.py --list     # print bucket candidates

To change which assets appear, edit PICKS below. Keys are SHA-256 prefixes;
run with --list to see what's available.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import boto3
from dotenv import load_dotenv
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
PUBLIC = REPO / "frontend" / "public" / "demo"
TS_MODULE = REPO / "frontend" / "lib" / "demo-assets.ts"
CACHE = REPO / ".cache" / "b2-demo"

# The public API the site itself calls. Picks are validated against production,
# not against a local database, because production is what a judge will hit.
VERIFY_API = os.environ.get(
    "ORIGINSHOT_VERIFY_API", "https://originshot-api.onrender.com/api/verify/"
)

# Long-edge cap. These are hero-scale web images, not print masters.
TARGET_LONG_EDGE = 1100
WEBP_QUALITY = 82

# sha256 prefix -> (slot name, style). Slot names drive the public filenames.
#
# Every still below is from ONE source photograph (original 05993b99f9af, the
# ceramic mug) and every one is manifest-embedded, content-bound and anchored in
# the transparency log. That combination is the whole point: the page claims a
# single photo produced all of these AND that you can check each frame, so a
# frame that is merely pretty — or merely resolvable — does not belong here.
#
# Do not reintroduce the old gemini-era picks (16612e91, 7d32f691, cec2a305,
# 2ff8fde1, edd6a2a0, bece137e, 028ac16c, 6bf689da, 404466 49, 7b30afcc,
# f2c0bdfa, fa99236f, 3a1656bd). They predate provenance embedding: most carry
# no manifest at all, four have no database record, and 3a1656bd is a *bottle*
# from the dispute-resolution fixture, not the demo mug.
PICKS: dict[str, tuple[str, str]] = {
    "11bfce586cc8": ("studio-01", "studio"),
    "38d43fd1c616": ("studio-02", "studio"),
    "42148eeb7c05": ("studio-03", "studio"),
    "090cf9990f10": ("lifestyle-01", "lifestyle"),
    "0a1a5eea5fcc": ("lifestyle-02", "lifestyle"),
    "2f522a727aec": ("lifestyle-03", "lifestyle"),
    "850605e0a471": ("lifestyle-04", "lifestyle"),
    "2f17210180067cd7": ("variant-01", "variant"),
    "4724a037780a": ("variant-02", "variant"),
    "8208a42f515c": ("variant-03", "variant"),
    "902b0b7df896": ("onmodel-01", "onmodel"),
}

# Video is copied byte-for-byte, never re-encoded. These files carry an embedded
# manifest and re-encoding would break the content binding — the whole point of
# showing them. Key is a sha256 prefix; the value is (slot, public filename stem).
# The stem keeps the hash so the file is self-identifying on disk; the slot is
# what lib/pack.ts and the landing sequence address it by.
#
# The hero clip derives from 4b2b705dbcdd — a second photograph of the same mug,
# not the still pack's original. Copy that says "one source photo" must therefore
# scope itself to the stills; see lib/pack.ts.
VIDEO_PICKS: dict[str, tuple[str, str]] = {
    "6ae12d1e": ("video-01", "video-6ae12d1e"),
}


def client():
    load_dotenv(REPO / ".env")
    endpoint = os.environ.get("B2_ENDPOINT_URL", "")
    if not endpoint:
        sys.exit("B2_ENDPOINT_URL is not set — populate .env first.")
    if not endpoint.startswith("http"):
        endpoint = "https://" + endpoint
    secret = os.environ.get("B2_APP_KEY") or os.environ.get("B2_APPLICATION_KEY")
    if not (os.environ.get("B2_KEY_ID") and secret):
        sys.exit("B2 credentials are not set — populate .env first.")
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["B2_KEY_ID"],
        aws_secret_access_key=secret,
    )
    return s3, os.environ["B2_BUCKET"]


def public_record(sha: str) -> dict:
    """What `/verify` tells the world about this hash — the site's own source of truth.

    Raises on anything that would leave a dead hash on the marketing page.
    """
    try:
        with urllib.request.urlopen(VERIFY_API + sha, timeout=90) as resp:
            record = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(
            f"{sha[:12]}: could not reach {VERIFY_API} ({exc}). "
            "Re-run when the API is up, or pass --offline if you accept the risk."
        ) from exc
    if not record.get("found"):
        raise SystemExit(
            f"{sha[:12]}: /verify returns found=false — this hash would render a dead "
            "'Check this hash yourself' link on the landing page. Pick another asset."
        )
    return record


def candidates(s3, bucket: str, exts: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="assets/"):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(exts) and obj["Size"] > 60_000:
                out.append((obj["Key"], obj["Size"]))
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print bucket candidates and exit")
    ap.add_argument("--offline", action="store_true",
                    help="skip the live /verify check (only when records are known good)")
    args = ap.parse_args()

    s3, bucket = client()
    found = candidates(s3, bucket)

    if args.list:
        print(f"{len(found)} media objects in {bucket}:")
        for key, size in found:
            print(f"  {size:>10,}  {key.split('/')[-1]}")
        return

    PUBLIC.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    rows = []
    for key, _size in found:
        sha = key.split("/")[-1].rsplit(".", 1)[0]
        hit = next((v for k, v in PICKS.items() if sha.startswith(k)), None)
        if not hit:
            continue
        slot, style = hit

        record = {} if args.offline else public_record(sha)
        model = record.get("model") or "unknown"
        provider = record.get("provider") or "unknown"
        in_ledger = bool(record.get("ledger"))

        cached = CACHE / f"{sha}.png"
        if not cached.exists():
            s3.download_file(bucket, key, str(cached))

        im = Image.open(cached).convert("RGB")
        # The master's dimensions, kept separately from the web copy's. The site
        # quotes these when it is displaying a provenance *record*, because that
        # record describes the object in B2 — not the thumbnail we re-encoded to
        # serve it. Reporting the resized size as the record's would be a small
        # lie in the middle of the page that argues nothing here is one.
        src_w, src_h = im.size
        if max(src_w, src_h) > TARGET_LONG_EDGE:
            scale = TARGET_LONG_EDGE / max(src_w, src_h)
            im = im.resize((round(src_w * scale), round(src_h * scale)), Image.LANCZOS)

        dest = PUBLIC / f"{slot}.webp"
        im.save(dest, "WEBP", quality=WEBP_QUALITY, method=6)
        rows.append((slot, style, sha, im.size[0], im.size[1], model, provider, slot,
                     src_w, src_h))
        print(f"{slot:<14} {style:<10} {im.size[0]}x{im.size[1]}  "
              f"{dest.stat().st_size // 1024:>4} KB  {sha[:16]}  {model}"
              f"{'' if in_ledger or args.offline else '   (NOT in ledger)'}")

    missing = set(PICKS.values()) - {(r[0], r[1]) for r in rows}
    if missing:
        print(f"\nWARNING: {len(missing)} picks not found in the bucket: {sorted(missing)}")

    # Videos: straight byte copy. Re-encoding would strip the embedded manifest
    # and break content-binding, which is exactly what these files demonstrate.
    for key, _size in candidates(s3, bucket, (".mp4",)):
        sha = key.split("/")[-1].rsplit(".", 1)[0]
        pick = next((v for k, v in VIDEO_PICKS.items() if sha.startswith(k)), None)
        if not pick:
            continue
        slot, stem = pick
        record = {} if args.offline else public_record(sha)
        dest = PUBLIC / f"{stem}.mp4"
        if not dest.exists():
            s3.download_file(bucket, key, str(dest))
        # Dimensions aren't probed here (no video dep); 960x960 is the pipeline's
        # 1:1 output. Update if ASPECT in the registry changes.
        rows.append((slot, "video", sha, 960, 960,
                     record.get("model") or "Kling-Image2Video-V2.1-Master",
                     record.get("provider") or "gmicloud", stem, 960, 960))
        print(f"{slot:<14} {'video':<10} 960x960  "
              f"{dest.stat().st_size // 1024:>4} KB  {sha[:16]}")

    rows.sort()

    def ext(style: str) -> str:
        return "mp4" if style == "video" else "webp"

    body = "\n".join(
        f'  {{ slot: "{slot}", style: "{style}", src: "/demo/{stem}.{ext(style)}", '
        f'sha: "{sha}", width: {w}, height: {h}, sourceWidth: {sw}, sourceHeight: {sh}, '
        f'model: "{model}", provider: "{provider}" }},'
        for slot, style, sha, w, h, model, provider, stem, sw, sh in rows
    )
    TS_MODULE.write_text(
        "// GENERATED — real OriginShot output pulled from Backblaze B2.\n"
        "// Each `sha` is the true SHA-256 of the source asset in the bucket, and every\n"
        "// one is checked against the live /verify API at sync time, so a hash shown on\n"
        "// the marketing site always resolves. `model` and `provider` are read back from\n"
        "// that same record — the site credits whoever actually served the run.\n"
        "// Regenerate with scripts/sync-demo-assets.py.\n"
        "\n"
        "export interface DemoAsset {\n"
        "  slot: string;\n"
        '  style: "studio" | "lifestyle" | "variant" | "onmodel" | "video";\n'
        "  src: string;\n"
        "  sha: string;\n"
        "  /** Dimensions of the re-encoded copy served from /public — for layout. */\n"
        "  width: number;\n"
        "  height: number;\n"
        "  /** Dimensions of the master in B2 — what the provenance record describes. */\n"
        "  sourceWidth: number;\n"
        "  sourceHeight: number;\n"
        "  /** The model the stored provenance record names — never assumed. */\n"
        "  model: string;\n"
        "  /** The provider that actually served this frame. */\n"
        "  provider: string;\n"
        "}\n"
        "\n"
        "export const DEMO_ASSETS: DemoAsset[] = [\n"
        f"{body}\n"
        "];\n",
        encoding="utf-8",
    )
    total_kb = sum((PUBLIC / f"{r[7]}.{ext(r[1])}").stat().st_size for r in rows) // 1024
    print(f"\n{len(rows)} images, {total_kb} KB total")
    print(f"wrote {TS_MODULE.relative_to(REPO)}")


if __name__ == "__main__":
    main()
