"""Perceptual hashing — recognising a generated image *after* a marketplace mangles it.

Every other verification surface in OriginShot proves a file from its exact bytes: the
embedded manifest, the SHA-256 content address, the strip-and-rehash content binding. All of
them are cryptographic, and all of them die the instant the file is re-encoded — which is
the *first* thing Etsy, Amazon or Shopify do on upload. So the provenance a seller can prove
is provenance on files downloaded from us, precisely the place it is least needed. The buyer
looking at the live listing sees a re-compressed JPEG that carries nothing.

A **perceptual hash** survives that trip. It is computed from what the image *looks like*,
not from its bytes, so a resize + JPEG round-trip barely moves it while a different product
moves it a lot. That lets `/verify` answer a weaker but far more useful question about a file
with no manifest left: *"is this visually the same image as a known OriginShot asset?"*

This is the DCT-based construction (Zauner 2010), implemented on numpy so it adds no
dependency (the app already ships Pillow + numpy):

  1. reduce to 32×32 grayscale — throws away colour detail and most of the resolution, which
     is exactly the information a re-encode also throws away;
  2. 2-D DCT-II, keep the top-left 8×8 block — the low spatial frequencies, i.e. the coarse
     structure a human reads as "the same picture";
  3. threshold each coefficient against the block's median (excluding the DC term) → 64 bits.

Similarity is Hamming distance over those 64 bits. Two important honesty limits, stated here
because a perceptual match must never be dressed up as a cryptographic one:

  * **It is evidence, not proof.** A low distance means "very probably the same image"; it is
    a similarity score, not a signature. `/verify` labels it as such and never lets it set
    the cryptographic `content_bound` flag.
  * **It says nothing about tampering.** pHash is designed to ignore small edits, so it
    cannot detect the very thing content-binding exists to catch. The two tiers answer
    different questions and are reported separately.
"""
from __future__ import annotations

import io

# 64-bit hash → 16 hex chars. The block side is 8 (8×8 = 64 coefficients kept).
_HASH_BITS = 64
_BLOCK = 8
_IMG = 32  # pre-DCT working size


def _dct_matrix(n: int):
    """Orthonormal DCT-II basis as an (n×n) numpy array, so DCT(x) = D @ x @ D.T.

    Built once per call and tiny (32×32); not worth caching, and caching would drag numpy
    into module import for callers that only need the Hamming helper.
    """
    import numpy as np

    k = np.arange(n)
    # D[u, x] = a(u) * cos(pi/n * (x + 1/2) * u), a(0)=sqrt(1/n), else sqrt(2/n)
    basis = np.cos(np.pi / n * (k[None, :] + 0.5) * k[:, None])
    scale = np.full(n, np.sqrt(2.0 / n))
    scale[0] = np.sqrt(1.0 / n)
    return basis * scale[:, None]


def phash(image_bytes: bytes) -> str | None:
    """Perceptual hash of an image, as 16 lowercase hex chars. None if it can't be decoded.

    Returns None rather than raising: this is best-effort metadata attached to an asset, and
    a decode failure must never fail the generation that produced the asset.
    """
    try:
        import numpy as np
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as im:
            # "L" = luminance. LANCZOS downscaling keeps the low-frequency structure the DCT
            # then reads; a cheaper filter would alias detail into those coefficients.
            im = im.convert("L").resize((_IMG, _IMG), Image.LANCZOS)
            pixels = np.asarray(im, dtype=np.float64)

        d = _dct_matrix(_IMG)
        coeffs = d @ pixels @ d.T
        block = coeffs[:_BLOCK, :_BLOCK]

        # Median over the block EXCLUDING the DC term [0,0]: the DC coefficient carries the
        # overall brightness and dwarfs the rest, so including it would bias the threshold and
        # make every hash brightness-dependent.
        flat = block.flatten()
        med = np.median(flat[1:])
        bits = flat > med

        value = 0
        for bit in bits:
            value = (value << 1) | int(bit)
        return f"{value:0{_HASH_BITS // 4}x}"
    except Exception:  # noqa: BLE001 — best-effort; see docstring
        return None


def hamming(a: str, b: str) -> int | None:
    """Bit distance between two hex pHashes (0 = identical, 64 = opposite). None if unusable.

    None when either operand is missing or malformed, so callers treat "can't compare" as
    "no match" rather than a spurious distance of 0.
    """
    if not a or not b or len(a) != len(b):
        return None
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return None


# ── Match thresholds ──────────────────────────────────────────────────
# Distances over 64 bits. Calibrated on real re-encodes (tests/test_perceptual.py runs the
# actual Etsy-style transform — resize + JPEG q75 — against a live generated asset):
#   a genuine re-encode of the SAME image lands in the low single digits;
#   a DIFFERENT product (even the same mug in another colour) sits far higher.
# The gap is wide, so the exact cut is not delicate — but it is deliberately conservative:
# a false "this is that asset" is worse here than a missed match, because the whole feature
# is a trust signal.
MATCH_STRONG = 6    # ≤ this: report as a confident perceptual match
MATCH_WEAK = 10     # ≤ this: report as a possible match, explicitly hedged
# > MATCH_WEAK: not reported as a match at all.


def confidence(distance: int) -> float:
    """A 0–1 confidence from a Hamming distance, for display only.

    Linear from 1.0 at distance 0 to 0.0 at the weak threshold. This is a UI convenience, not
    a probability — the honest signal is the raw distance, which is always shown alongside it.
    """
    if distance <= 0:
        return 1.0
    if distance >= MATCH_WEAK:
        return 0.0
    return round(1.0 - distance / MATCH_WEAK, 3)
