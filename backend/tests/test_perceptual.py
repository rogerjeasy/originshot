"""Perceptual hashing (originshot_pipelines/perceptual.py).

The load-bearing claim is that a pHash survives a marketplace re-encode while still telling
two different products apart. That is asserted here against the ACTUAL transform a marketplace
applies — resize + JPEG recompress — not a mock.

**Both halves of that claim are measured against the REAL shipped catalog** (the demo assets in
`frontend/public/demo`, which are re-encodes of ledger-anchored production output). The earlier
version of this file measured only synthetic checker / gradient / circle patterns, and those
fixtures are why a real defect shipped: they are structures chosen to be maximally unlike each
other, whereas this app's catalog is one object, one pose, one white background, several
colourways — the near-worst case for a hash that discards colour. Against synthetic fixtures the
separation looked enormous; against real output, genuinely different assets sat 4 bits apart
while the thresholds admitted 6 and 10.

So the separation test now uses the adversarial pair from the app's own output. If someone
widens the thresholds again, `test_distinct_real_assets_stay_outside_the_match_window` fails.
"""
from __future__ import annotations

import io
import logging
import sys
from pathlib import Path

import pytest

from originshot_pipelines import perceptual

np = pytest.importorskip("numpy")
Image = pytest.importorskip("PIL.Image")

# Real generated output, re-encoded for the web by scripts/sync-demo-assets.py. Committed to the
# repo, so this is a fixture the test suite owns rather than a network dependency.
DEMO = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo"
_demo_assets = pytest.mark.skipif(
    not DEMO.is_dir() or not any(DEMO.glob("*.webp")),
    reason="demo assets not present (frontend/public/demo)",
)


def _demo(stem: str) -> bytes:
    return (DEMO / f"{stem}.webp").read_bytes()


def _img(pattern: str, size: int = 512) -> bytes:
    """A deterministic, structured test image. Structure matters — pHash keys on it."""
    from PIL import Image as I

    arr = np.zeros((size, size, 3), dtype=np.uint8)
    if pattern == "gradient":
        arr[:, :, 0] = np.linspace(0, 255, size, dtype=np.uint8)[None, :]
        arr[:, :, 1] = np.linspace(0, 255, size, dtype=np.uint8)[:, None]
    elif pattern == "checker":
        block = size // 8
        for i in range(8):
            for j in range(8):
                if (i + j) % 2 == 0:
                    arr[i * block:(i + 1) * block, j * block:(j + 1) * block] = 220
    elif pattern == "circle":
        yy, xx = np.ogrid[:size, :size]
        mask = (xx - size / 2) ** 2 + (yy - size / 2) ** 2 < (size / 3) ** 2
        arr[mask] = 200
    buf = io.BytesIO()
    I.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _reencode(data: bytes, size: int, quality: int) -> bytes:
    """The Etsy/Amazon transform: resize to exact dimensions and JPEG-recompress."""
    from PIL import Image as I

    with I.open(io.BytesIO(data)) as im:
        im = im.convert("RGB").resize((size, size))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def test_phash_is_stable_and_16_hex_chars():
    h = perceptual.phash(_img("gradient"))
    assert h is not None and len(h) == 16
    int(h, 16)  # valid hex
    assert perceptual.phash(_img("gradient")) == h  # deterministic


@_demo_assets
@pytest.mark.parametrize("stem", [
    "studio-01", "studio-02", "studio-03",
    "lifestyle-01", "lifestyle-02", "lifestyle-03", "lifestyle-04",
    "onmodel-01", "variant-01", "variant-02", "variant-03",
])
def test_real_asset_survives_a_marketplace_reencode(stem):
    """Every real asset must stay inside the STRONG window through a marketplace round-trip.

    Asserted against MATCH_STRONG, not the weaker boundary: measured across all eleven assets
    and all five transforms, 54 of 55 land at exactly 0 and the worst case is 2 (one lifestyle
    frame at 400px/q50 — a downscale far more aggressive than any marketplace applies). The
    true-positive side of this decision has almost no spread, which is what makes a threshold
    as tight as 2 safe.
    """
    original = _demo(stem)
    h0 = perceptual.phash(original)
    assert h0 is not None
    for size, q in [(2000, 75), (1600, 85), (1200, 80), (800, 60), (400, 50)]:
        d = perceptual.hamming(h0, perceptual.phash(_reencode(original, size, q)))
        assert d is not None and d <= perceptual.MATCH_STRONG, (
            f"{stem} at {size}/{q} moved {d} bits — a genuine re-encode must stay matchable"
        )


@_demo_assets
def test_distinct_real_assets_stay_outside_the_match_window():
    """The regression guard: two DIFFERENT real assets must not be reportable as a match.

    This is the test that was missing. `studio-01` and `variant-03` are different files — a
    cream mug and a green one — and sit 4 bits apart, because pHash reads luminance and the two
    differ almost only in colour. Under the old MATCH_STRONG of 6 the public verifier called
    that a confident match and handed the buyer the wrong asset's provider, model and lineage.

    Asserting `> MATCH_STRONG` rather than `> MATCH_WEAK` is deliberate and is the honest
    statement of what this hash can do: 4 bits is inside the hedged weak band, so these two can
    still surface as a *possible* match. What must never happen again is either of them being
    called confident — and `ambiguous()` is what stops the weak band naming a coin flip.
    """
    pairs = [("studio-01", "variant-03"), ("studio-02", "studio-03"),
             ("studio-01", "variant-01"), ("variant-01", "variant-03")]
    for a, b in pairs:
        d = perceptual.hamming(perceptual.phash(_demo(a)), perceptual.phash(_demo(b)))
        assert d is not None and d > perceptual.MATCH_STRONG, (
            f"{a} and {b} are different assets but sit {d} bits apart — "
            f"MATCH_STRONG={perceptual.MATCH_STRONG} would report that as confident"
        )


@_demo_assets
def test_thresholds_sit_below_the_measured_false_positive_floor():
    """The calibration itself: the confident cut must be under the closest distinct-asset pair.

    Recomputes both sides of the decision from the shipped catalog, so the constants in
    perceptual.py can never drift above the evidence they claim to rest on. This is the check
    that would have caught the original 6/10 thresholds.
    """
    stems = sorted(p.stem for p in DEMO.glob("*.webp"))
    hashes = {s: perceptual.phash(_demo(s)) for s in stems}

    closest = min(
        (perceptual.hamming(hashes[a], hashes[b]), a, b)
        for i, a in enumerate(stems) for b in stems[i + 1:]
    )
    floor = closest[0]
    assert perceptual.MATCH_STRONG < floor, (
        f"MATCH_STRONG={perceptual.MATCH_STRONG} is not below the closest distinct pair "
        f"({closest[1]}/{closest[2]} at {floor} bits) — confident matches would be wrong"
    )
    # The weak band may reach the floor, but the margin rule has to be wide enough that a
    # winner sitting on it cannot beat a neighbour one bit further out.
    assert perceptual.MATCH_MARGIN > 1


def test_phash_separates_structurally_different_images():
    """Synthetic sanity check: unrelated structure lands far outside any window.

    Retained as a floor, not as the calibration — the real separation evidence is the demo-asset
    test above. These patterns are wildly dissimilar and prove only that the hash is not
    degenerate.
    """
    a = perceptual.phash(_img("checker"))
    for other in ("gradient", "circle"):
        d = perceptual.hamming(a, perceptual.phash(_img(other)))
        assert d is not None and d > perceptual.MATCH_WEAK, f"{other} too close: {d}"


def test_ambiguous_rejects_a_winner_that_barely_beats_the_runner_up():
    """A near-tie between neighbours is not a match, however close the winner is."""
    # Clear winner: nothing else is anywhere near.
    assert perceptual.ambiguous(0, 12) is False
    assert perceptual.ambiguous(0, perceptual.MATCH_MARGIN) is False
    # Coin flip between two colourways — the exact production failure this guards.
    assert perceptual.ambiguous(4, 6) is True
    assert perceptual.ambiguous(0, 2) is True
    assert perceptual.ambiguous(2, 2) is True
    # No second candidate at all: nothing to be ambiguous against.
    assert perceptual.ambiguous(0, None) is False
    assert perceptual.ambiguous(4, None) is False


def test_phash_returns_none_on_undecodable_bytes():
    """Best-effort: a non-image must not raise — it degrades to 'no pHash'."""
    assert perceptual.phash(b"not an image at all") is None


def test_missing_numpy_is_logged_loudly_not_swallowed(monkeypatch, caplog):
    """A missing dependency must not look like an undecodable file.

    `phash` catches everything so a bad byte-stream can never fail a generation. That same
    handler also silently ate the ImportError from an undeclared numpy, so the in-the-wild
    verify tier ran dark — every asset hashing to None, no signal anywhere. It still returns
    None (best-effort is still the contract), but now it says so.
    """
    # `None` in sys.modules makes `import numpy` raise ImportError, exactly as an absent
    # install does, without touching the real module.
    monkeypatch.setitem(sys.modules, "numpy", None)

    with caplog.at_level(logging.ERROR, logger="originshot.perceptual"):
        assert perceptual.phash(_img("gradient")) is None

    assert any("in-the-wild verify is DARK" in r.message for r in caplog.records)


def test_hamming_edges():
    assert perceptual.hamming("0000000000000000", "0000000000000000") == 0
    assert perceptual.hamming("ffffffffffffffff", "0000000000000000") == 64
    # unusable operands -> None, so a caller never reads a spurious distance of 0
    assert perceptual.hamming(None, "0000000000000000") is None
    assert perceptual.hamming("abc", "abcd") is None
    assert perceptual.hamming("zzzz", "0000") is None


def test_confidence_is_monotone_and_bounded():
    assert perceptual.confidence(0) == 1.0
    assert perceptual.confidence(perceptual.MATCH_WEAK) == 0.0
    assert perceptual.confidence(999) == 0.0
    assert perceptual.confidence(1) > perceptual.confidence(perceptual.MATCH_STRONG)
