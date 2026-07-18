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

Usage (from the repo root, with the backend venv active and .env populated):

    python scripts/sync-demo-assets.py            # sync the current selection
    python scripts/sync-demo-assets.py --list     # print bucket candidates

To change which assets appear, edit PICKS below. Keys are SHA-256 prefixes;
run with --list to see what's available.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
PUBLIC = REPO / "frontend" / "public" / "demo"
TS_MODULE = REPO / "frontend" / "lib" / "demo-assets.ts"
CACHE = REPO / ".cache" / "b2-demo"

# Long-edge cap. These are hero-scale web images, not print masters.
TARGET_LONG_EDGE = 1100
WEBP_QUALITY = 82

# sha256 prefix -> (slot name, style). Slot names drive the public filenames.
PICKS: dict[str, tuple[str, str]] = {
    "16612e919d2d": ("studio-01", "studio"),
    "7d32f691df2a": ("studio-02", "studio"),
    "cec2a305ad34": ("studio-03", "studio"),
    "fa99236f85ba": ("studio-04", "studio"),
    "028ac16c44cd": ("lifestyle-01", "lifestyle"),
    "2ff8fde17412": ("lifestyle-02", "lifestyle"),
    "404466499eaf": ("lifestyle-03", "lifestyle"),
    "6bf689dac2b1": ("lifestyle-04", "lifestyle"),
    "edd6a2a0dc9f": ("lifestyle-05", "lifestyle"),
    "f2c0bdfa31da": ("lifestyle-06", "lifestyle"),
    "7b30afcc6f4a": ("scene-01", "lifestyle"),
    "bece137e8c83": ("scene-02", "lifestyle"),
    "3a1656bddbc7": ("variant-01", "variant"),
    "4b2b705dbcdd": ("onmodel-01", "onmodel"),
}

# Video is copied byte-for-byte, never re-encoded. These files carry an embedded
# manifest and re-encoding would break the content binding — the whole point of
# showing them. Key is a sha256 prefix; the value is the public filename stem.
VIDEO_PICKS: dict[str, str] = {
    "6ae12d1e": "video-6ae12d1e",
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

        cached = CACHE / f"{sha}.png"
        if not cached.exists():
            s3.download_file(bucket, key, str(cached))

        im = Image.open(cached).convert("RGB")
        w, h = im.size
        if max(w, h) > TARGET_LONG_EDGE:
            scale = TARGET_LONG_EDGE / max(w, h)
            im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)

        dest = PUBLIC / f"{slot}.webp"
        im.save(dest, "WEBP", quality=WEBP_QUALITY, method=6)
        rows.append((slot, style, sha, im.size[0], im.size[1]))
        print(f"{slot:<14} {style:<10} {im.size[0]}x{im.size[1]}  "
              f"{dest.stat().st_size // 1024:>4} KB  {sha[:16]}")

    missing = set(PICKS.values()) - {(r[0], r[1]) for r in rows}
    if missing:
        print(f"\nWARNING: {len(missing)} picks not found in the bucket: {sorted(missing)}")

    # Videos: straight byte copy. Re-encoding would strip the embedded manifest
    # and break content-binding, which is exactly what these files demonstrate.
    for key, _size in candidates(s3, bucket, (".mp4",)):
        sha = key.split("/")[-1].rsplit(".", 1)[0]
        stem = next((v for k, v in VIDEO_PICKS.items() if sha.startswith(k)), None)
        if not stem:
            continue
        dest = PUBLIC / f"{stem}.mp4"
        if not dest.exists():
            s3.download_file(bucket, key, str(dest))
        # Dimensions aren't probed here (no video dep); 960x960 is the pipeline's
        # 1:1 output. Update if ASPECT in the registry changes.
        rows.append((stem, "video", sha, 960, 960))
        print(f"{stem:<14} {'video':<10} 960x960  "
              f"{dest.stat().st_size // 1024:>4} KB  {sha[:16]}")

    rows.sort()

    def ext(style: str) -> str:
        return "mp4" if style == "video" else "webp"

    body = "\n".join(
        f'  {{ slot: "{slot}", style: "{style}", src: "/demo/{slot}.{ext(style)}", '
        f'sha: "{sha}", width: {w}, height: {h} }},'
        for slot, style, sha, w, h in rows
    )
    TS_MODULE.write_text(
        "// GENERATED — real OriginShot output pulled from Backblaze B2.\n"
        "// Each `sha` is the true SHA-256 of the source asset in the bucket, so any\n"
        "// hash shown on the marketing site resolves against /verify.\n"
        "// Regenerate with scripts/sync-demo-assets.py.\n"
        "\n"
        "export interface DemoAsset {\n"
        "  slot: string;\n"
        '  style: "studio" | "lifestyle" | "variant" | "onmodel" | "video";\n'
        "  src: string;\n"
        "  sha: string;\n"
        "  width: number;\n"
        "  height: number;\n"
        "}\n"
        "\n"
        "export const DEMO_ASSETS: DemoAsset[] = [\n"
        f"{body}\n"
        "];\n",
        encoding="utf-8",
    )
    total_kb = sum((PUBLIC / f"{r[0]}.{ext(r[1])}").stat().st_size for r in rows) // 1024
    print(f"\n{len(rows)} images, {total_kb} KB total")
    print(f"wrote {TS_MODULE.relative_to(REPO)}")


if __name__ == "__main__":
    main()
