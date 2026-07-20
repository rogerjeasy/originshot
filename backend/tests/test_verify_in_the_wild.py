"""Verify in the Wild — the perceptual-match tier of POST /verify.

Scenario under test end to end: a seller generates an asset (we store its pHash), a
marketplace re-encodes it (new bytes, new SHA, manifest stripped), a buyer drops that
re-encoded file into the public verifier. The cryptographic tiers can say nothing; the
perceptual tier must recognise it, trace it to the authentic original, and label the whole
thing as evidence rather than proof.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from originshot_pipelines import perceptual


def _structured_png(seed: int, size: int = 512) -> bytes:
    """A decodable image with enough structure for a stable pHash (not a flat colour)."""
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, size=(8, 8, 3), dtype=np.uint8)  # coarse structure
    arr = np.kron(base, np.ones((size // 8, size // 8, 1), dtype=np.uint8))
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _reencode(data: bytes, size: int = 1600, quality: int = 80) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB").resize((size, size))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _seed_asset(png: bytes, *, sha: str, parent: str, style: str = "studio") -> dict:
    """Insert a generated asset carrying a pHash straight into the in-memory repo."""
    from app.repo import get_repo

    repo = get_repo()
    return repo.add_asset("seller-1", {
        "sku_id": "sku-1",
        "sha256": sha,
        "phash": perceptual.phash(png),
        "parent_sha256": parent,
        "style": style,
        "provider": "openai-dalle",
        "model": "gpt-image-1",
        "is_authentic": False,
        "modality": "image",
    })


def test_reencoded_marketplace_copy_is_recognised(client):
    original = _structured_png(seed=1)
    _seed_asset(original, sha="a" * 64, parent="parent123abc" + "0" * 52)

    # The buyer's file: same image, re-encoded by a marketplace. Different bytes entirely.
    wild = _reencode(original)
    assert wild != original

    r = client.post("/api/verify", files={"file": ("listing.jpg", wild, "image/jpeg")})
    assert r.status_code == 200
    body = r.json()

    # Cryptographic tiers correctly find nothing — the manifest is gone and the SHA changed.
    assert body["found"] is False
    assert body["embedded"] is False
    assert body["content_bound"] is None

    # Perceptual tier recognises it and carries the lineage back to the authentic original.
    pm = body["perceptual"]
    assert pm is not None
    assert pm["matched_sha256"] == "a" * 64
    assert pm["distance"] <= perceptual.MATCH_WEAK
    assert pm["parent_sha256"].startswith("parent123abc")
    assert pm["provider"] == "openai-dalle"
    # Language is evidentiary, never a cryptographic guarantee.
    assert "similarity" in body["disclosure"].lower()
    assert "not a cryptographic" in body["disclosure"].lower()


def test_a_different_product_is_not_matched(client):
    _seed_asset(_structured_png(seed=1), sha="a" * 64, parent="p" * 64)

    # An unrelated image — must not trigger a false "this is that asset".
    other = _reencode(_structured_png(seed=999))
    r = client.post("/api/verify", files={"file": ("other.jpg", other, "image/jpeg")})
    body = r.json()

    assert body["perceptual"] is None
    assert body["found"] is False
    assert "no embedded manifest and no record" in body["disclosure"].lower()


def test_perceptual_tier_is_skipped_when_the_exact_asset_is_on_record(client):
    """An unmodified file resolves cryptographically and must not fall to the pHash tier.

    The perceptual tier is a fallback for files the strong tiers can't place; running it on a
    file we can place exactly would be both wasteful and a weaker claim than the one we have.
    """
    import hashlib

    png = _structured_png(seed=7)
    sha = hashlib.sha256(png).hexdigest()
    _seed_asset(png, sha=sha, parent="p" * 64)

    r = client.post("/api/verify", files={"file": ("exact.png", png, "image/png")})
    body = r.json()

    assert body["found"] is True
    assert body["perceptual"] is None      # resolved by SHA, no pHash search needed


def test_non_image_upload_does_not_break_the_verifier(client):
    """A garbage upload with no match must degrade cleanly, not 500 on the pHash step."""
    r = client.post("/api/verify", files={"file": ("x.bin", b"not an image", "image/png")})
    assert r.status_code == 200
    assert r.json()["perceptual"] is None


def test_repo_phash_search_picks_the_nearest(client):
    """The search returns the closest asset and reports the distance it matched at."""
    from app.repo import get_repo

    near = _structured_png(seed=1)
    _seed_asset(near, sha="n" * 64, parent="p" * 64)
    _seed_asset(_structured_png(seed=500), sha="f" * 64, parent="p" * 64)

    hit = get_repo().find_similar_by_phash(perceptual.phash(_reencode(near)), perceptual.MATCH_WEAK)
    assert hit is not None
    assert hit["sha256"] == "n" * 64
    assert "phash_distance" in hit


def test_repo_phash_search_returns_none_when_nothing_is_close(client):
    from app.repo import get_repo

    _seed_asset(_structured_png(seed=1), sha="a" * 64, parent="p" * 64)
    far = perceptual.phash(_structured_png(seed=777))
    # A tiny max_distance guarantees the one seeded asset is out of range.
    assert get_repo().find_similar_by_phash(far, 0) is None
