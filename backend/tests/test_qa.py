"""QA evaluator + retry loop. All hermetic: the VLM transport is stubbed, never called."""
import io

import pytest
from PIL import Image

from originshot_pipelines import qa


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def studio_good(size=600) -> bytes:
    """White canvas with a centred dark product filling ~half the frame."""
    img = Image.new("RGB", (size, size), (255, 255, 255))
    q = size // 4
    for x in range(q, size - q):
        for y in range(q, size - q):
            img.putpixel((x, y), (60, 70, 90))
    return _png(img)


def grey_photo(size=600) -> bytes:
    return _png(Image.new("RGB", (size, size), (128, 128, 128)))


# ── Deterministic tier ────────────────────────────────────────────────
def test_studio_good_passes():
    report = qa.evaluate_image(studio_good(), "studio")
    assert report["passed"] is True
    names = {c["name"] for c in report["checks"]}
    assert {"resolution", "white_background", "product_fill"} <= names
    assert report["scorer"] == "deterministic"


def test_studio_grey_background_fails():
    report = qa.evaluate_image(grey_photo(), "studio")
    assert report["passed"] is False
    failed = {c["name"] for c in report["checks"] if not c["passed"]}
    assert "white_background" in failed


def test_low_resolution_fails_every_style():
    tiny = _png(Image.new("RGB", (100, 100), (255, 255, 255)))
    for style in ("studio", "lifestyle", "variant"):
        report = qa.evaluate_image(tiny, style)
        assert report["passed"] is False


def test_lifestyle_has_no_whiteness_requirement():
    report = qa.evaluate_image(grey_photo(), "lifestyle")
    assert report["passed"] is True
    assert {c["name"] for c in report["checks"]} == {"resolution"}


def test_empty_canvas_fails_fill():
    blank = _png(Image.new("RGB", (600, 600), (255, 255, 255)))
    report = qa.evaluate_image(blank, "studio")
    fill = next(c for c in report["checks"] if c["name"] == "product_fill")
    assert fill["passed"] is False


def test_undecodable_bytes_fail():
    report = qa.evaluate_image(b"not an image", "studio")
    assert report["passed"] is False


# ── VLM tier (stubbed transport) ──────────────────────────────────────
def test_vlm_pass_and_fail_scores():
    ref = studio_good()
    good = qa.evaluate_image(studio_good(), "studio", reference=ref,
                             vlm_call=lambda r, c: (8, "same mug"))
    assert good["passed"] is True and good["scorer"] == "deterministic+vlm"
    assert good["vlm_score"] == 8

    bad = qa.evaluate_image(studio_good(), "studio", reference=ref,
                            vlm_call=lambda r, c: (3, "different product"))
    assert bad["passed"] is False
    match = next(c for c in bad["checks"] if c["name"] == "product_match")
    assert match["passed"] is False


def test_vlm_failure_degrades_to_deterministic():
    def broken(r, c):
        raise RuntimeError("429 overloaded")

    report = qa.evaluate_image(studio_good(), "studio",
                               reference=studio_good(), vlm_call=broken)
    assert report["passed"] is True            # deterministic checks still pass
    assert report["scorer"] == "deterministic"  # and the report says the VLM never ran
    assert report["vlm_score"] is None


def test_vlm_product_match_parses_json(monkeypatch):
    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {
                "content": 'Sure!\n{"score": 7, "verdict": "Same ceramic mug."}'}}]}

    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp())
    score, verdict = qa.vlm_product_match(
        studio_good(), studio_good(), api_key="k", base_url="http://x", model="m")
    assert score == 7 and "mug" in verdict


# ── Retry loop (style granularity, better attempt wins) ───────────────
@pytest.mark.anyio
async def test_retry_keeps_better_attempt(monkeypatch):
    import app.generation as gen
    from app.models import Style

    blobs = {"u1": grey_photo(), "u2": studio_good()}
    monkeypatch.setattr(gen, "_fetch_bytes", lambda url: blobs[url])

    class NullStorage:
        def presigned_get(self, key):
            return key

    seen_feedback = {}

    async def runner(feedback=None):
        # The retry must be INFORMED: attempt 1 (grey_photo) fails the white-background check,
        # so the runner should receive a correction naming that problem, not be re-rolled blind.
        seen_feedback["value"] = feedback
        return [{"b2_key": "u2", "sha256": "second"}]

    first = [{"b2_key": "u1", "sha256": "first"}]
    winner = await gen._qa_and_maybe_retry(
        Style.studio, runner, first, NullStorage(),
        reference=None, vlm_call=None, retry=True)
    assert winner[0]["sha256"] == "second"
    assert winner[0]["qa"]["passed"] is True
    assert winner[0]["qa"]["attempts"] == 2
    # Feedback-driven, not blind: the retry carried a correction for the failed check.
    assert seen_feedback["value"] and "background" in seen_feedback["value"].lower()
    assert winner[0]["qa"]["retry_feedback"]


@pytest.mark.anyio
async def test_no_retry_when_first_attempt_passes(monkeypatch):
    import app.generation as gen
    from app.models import Style

    monkeypatch.setattr(gen, "_fetch_bytes", lambda url: studio_good())

    class NullStorage:
        def presigned_get(self, key):
            return key

    async def runner(feedback=None):  # pragma: no cover — must never be called
        raise AssertionError("retry ran even though QA passed")

    first = [{"b2_key": "u1", "sha256": "first"}]
    winner = await gen._qa_and_maybe_retry(
        Style.studio, runner, first, NullStorage(),
        reference=None, vlm_call=None, retry=True)
    assert winner[0]["sha256"] == "first"
    assert winner[0]["qa"]["passed"] is True
    assert winner[0]["qa"]["attempt"] == 1


@pytest.mark.anyio
async def test_tie_keeps_first_attempt(monkeypatch):
    import app.generation as gen
    from app.models import Style

    monkeypatch.setattr(gen, "_fetch_bytes", lambda url: grey_photo())

    class NullStorage:
        def presigned_get(self, key):
            return key

    async def runner(feedback=None):
        return [{"b2_key": "u2", "sha256": "second"}]

    first = [{"b2_key": "u1", "sha256": "first"}]
    winner = await gen._qa_and_maybe_retry(
        Style.studio, runner, first, NullStorage(),
        reference=None, vlm_call=None, retry=True)
    assert winner[0]["sha256"] == "first"      # 0 == 0 passes ⇒ no churn
    assert winner[0]["qa"]["attempts"] == 2    # but the report says a retry happened
