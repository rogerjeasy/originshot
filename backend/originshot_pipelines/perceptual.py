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
  * **It discards colour.** Step 1 collapses to luminance, so two colourways of one product in
    one pose are nearly indistinguishable to it. That is not an edge case here — it is the
    house style of a product catalog — so a match must clear both a distance threshold and an
    ambiguity margin before it is reported at all. See :data:`MATCH_MARGIN` and
    :func:`ambiguous`.
"""
from __future__ import annotations

import io
import logging

log = logging.getLogger("originshot.perceptual")

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
    except ImportError:
        # NOT a decode failure — numpy or Pillow is missing from the deployment, so *every*
        # image hashes to None and the whole in-the-wild tier is dark. That is invisible in
        # the blanket handler below (a None reads exactly like an undecodable file), which is
        # how an undeclared numpy survived for as long as it did. Loud, and still non-fatal.
        log.exception("phash unavailable: numpy/Pillow missing — in-the-wild verify is DARK")
        return None
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
# Distances over 64 bits, calibrated by measuring BOTH sides of the decision on the real
# shipped catalog (`tests/test_perceptual.py` re-runs this measurement, so the numbers below
# cannot silently rot):
#
#   true positives  — every asset in frontend/public/demo through five marketplace-style
#                     re-encodes (2000/q75, 1600/q85, 1200/q80, 800/q60, 400/q50):
#                     **0 bits in 54 of 55 cases, worst case 2** (one lifestyle frame at the
#                     extreme 400px/q50 downscale, far past anything a marketplace applies).
#   false positives — the closest pair of genuinely DIFFERENT assets in that same catalog:
#                     **4 bits** (studio-01 vs variant-03; studio-02 vs studio-03).
#
# ⚠️ The earlier calibration here claimed "a DIFFERENT product (even the same mug in another
# colour) sits far higher" and set 6/10. That was measured against *synthetic* checker /
# gradient / circle fixtures — structures chosen to be maximally unlike each other, which is
# the opposite of this app's domain. Re-measured against real output the claim is false, and
# the old thresholds sat ABOVE the false-positive floor: distinct assets 4 and 6 bits apart
# were both being reported as confident matches, naming the wrong asset's provider, model and
# lineage. The gap is genuinely narrow (2 vs 4) because pHash reduces to 32×32 **luminance**
# before the DCT — colour is precisely the information it discards, and colourways of one
# object on a white background are precisely what this app generates.
#
# So the cut IS delicate, and it is drawn hard against the measured floor rather than
# comfortably above it. A false "this is that asset" is far worse than a missed match: the
# whole feature is a trust signal, and it is the only surface here that can name a provenance
# it did not cryptographically verify.
MATCH_STRONG = 2    # ≤ this: report as a confident perceptual match
MATCH_WEAK = 4      # ≤ this: report as a possible match, explicitly hedged
# > MATCH_WEAK: not reported as a match at all.

# Distance alone is not sufficient in a catalog of near-identical products: being 4 bits from
# the winner means little if the runner-up is 5 bits away. A match must also be *unambiguous*
# — the winner has to beat the next-best candidate by this many bits. Set to 3 because the
# worst true positive (2) still clears every measured non-self neighbour (≥4 away, and ≥12 for
# every asset whose own hash is indexed), while the ambiguous pre-backfill collisions this
# guards against sat 2 bits apart. See `ambiguous()`.
MATCH_MARGIN = 3


def ambiguous(distance: int, runner_up: int | None) -> bool:
    """True when the nearest asset is not clearly nearer than the second-nearest.

    A perceptual hit names a specific asset — its provider, model and authentic-original
    lineage. In a catalog of colourways of one object, several assets legitimately sit within
    a few bits of each other, so "closest" can be a coin flip between neighbours that are
    indistinguishable to this hash. Reporting one of them would attach a real, checkable
    provenance record to the wrong file, which is the exact failure this project exists to
    prevent — so an ambiguous result is reported as *no match* rather than as a guess.

    `runner_up` is None when there was no second candidate at all (a one-asset index, or the
    only near neighbour): nothing to be ambiguous against, so the match stands on distance.
    """
    if runner_up is None:
        return False
    return (runner_up - distance) < MATCH_MARGIN


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
