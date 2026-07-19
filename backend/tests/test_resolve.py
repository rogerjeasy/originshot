"""Resolve — dispute evidence reports.

Two layers, kept apart on purpose: `assess()` is a pure function and is tested exhaustively
against every finding it can return, while the endpoint tests exercise the real wiring
(upload → anchor resolution → PDF → storage → public re-resolution) with no provider calls.

The vision comparison itself is injected. A test that hit the real model would cost money on
every run and would make this file's assertions depend on a remote model's mood — the
transport is covered by the live probe in registry.py, and its contract is pinned here.
"""
import hashlib
import io

import pytest
from PIL import Image

from originshot_pipelines import resolve as resolve_lib
from originshot_pipelines.resolve import Finding


def _png(color=(30, 90, 160), size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


CLEAN = {"present": True, "verified": True, "content_bound": True, "found": True}


# ── The finding logic ─────────────────────────────────────────────────
def test_tampered_listing_outranks_everything():
    """A broken content binding is the finding even when the item matches perfectly."""
    out = resolve_lib.assess(
        listing={**CLEAN, "content_bound": False},
        match={"score": 10, "verdict": "identical", "differences": []},
    )
    assert out["finding"] == Finding.listing_tampered.value
    assert out["severity"] == "critical"


def test_unknown_file_reports_no_provenance():
    out = resolve_lib.assess(
        listing={"present": False, "verified": False, "content_bound": None, "found": False},
        match=None,
    )
    assert out["finding"] == Finding.no_provenance.value
    # It must not read as an accusation — most images legitimately have no manifest.
    assert "not itself evidence of wrongdoing" in out["detail"]


def test_high_score_with_no_differences_is_consistent():
    out = resolve_lib.assess(listing=CLEAN, match={"score": 9, "verdict": "", "differences": []})
    assert out["finding"] == Finding.consistent.value
    assert out["severity"] == "ok"


def test_right_item_arrived_damaged_is_not_a_green_pass():
    """The most common real dispute: correct product, damaged on arrival.

    A high same-product score with defects logged must not report "consistent / ok" — that
    would hand the complainant a green document describing the very damage they reported.
    """
    out = resolve_lib.assess(listing=CLEAN, match={
        "score": 9, "verdict": "Same mug.",
        "differences": ["diagonal scratch on lower body", "chip near inner rim"]})
    assert out["finding"] == Finding.condition_differences.value
    assert out["severity"] == "warning"
    # It must not overclaim causation — when the damage happened is not knowable from photos.
    assert "does not establish when or how" in out["detail"]


def test_low_score_is_a_mismatch():
    out = resolve_lib.assess(listing=CLEAN, match={"score": 1, "verdict": "", "differences": []})
    assert out["finding"] == Finding.item_mismatch.value
    assert out["severity"] == "critical"


@pytest.mark.parametrize("score", [3, 4, 5, 6])
def test_middle_band_refuses_to_decide(score):
    """The gap between the thresholds must return inconclusive, not round to a verdict."""
    out = resolve_lib.assess(listing=CLEAN, match={"score": score, "verdict": "",
                                                   "differences": []})
    assert out["finding"] == Finding.inconclusive.value


def test_no_comparison_is_provenance_only_and_says_why():
    out = resolve_lib.assess(listing=CLEAN, match={"unavailable": "model unreachable"})
    assert out["finding"] == Finding.provenance_only.value
    assert "model unreachable" in out["detail"]


def test_every_finding_has_a_severity_and_headline():
    for finding in Finding:
        assert finding in resolve_lib.SEVERITY
        assert resolve_lib._HEADLINES[finding]


# ── The report document ───────────────────────────────────────────────
def _record(**over) -> dict:
    base = {
        "id": "rep-1", "issued_at": "2026-07-19 10:00 UTC",
        "finding": Finding.item_mismatch.value, "severity": "critical",
        "headline": "The delivered item does not match the listed product",
        "detail": "Detail paragraph.",
        "listing": {"sha256": "a" * 64, "present": True, "verified": True,
                    "content_bound": True, "found": True,
                    "provider": "gmicloud-image", "model": "gemini-3-pro-image-preview"},
        "anchor": {"sha256": "b" * 64, "created_at": "2026-01-02"},
        "received": {"sha256": "c" * 64},
        "match": {"score": 1, "verdict": "A different mug entirely.",
                  "differences": ["handle shape differs", "no speckled glaze"],
                  "model": "x-ai/grok-4.5"},
        "match_unavailable": None,
    }
    return {**base, **over}


def test_report_renders_a_pdf():
    pdf = resolve_lib.build_dispute_report(_record(), verify_base_url="https://x.test/verify",
                                           report_base_url="https://x.test/resolve")
    assert pdf.startswith(b"%PDF")
    assert b"/Page" in pdf
    assert len(pdf) > 2000


@pytest.mark.parametrize("severity", ["ok", "info", "warning", "critical"])
def test_report_renders_for_every_severity(severity):
    """The accent colour is looked up by severity — an unmapped one would KeyError."""
    pdf = resolve_lib.build_dispute_report(_record(severity=severity),
                                           verify_base_url="https://x.test/verify")
    assert pdf.startswith(b"%PDF")


def test_report_renders_without_a_comparison():
    pdf = resolve_lib.build_dispute_report(
        _record(match=None, match_unavailable="the model could not be reached",
                received={"sha256": None}, anchor={"sha256": None}),
        verify_base_url="https://x.test/verify")
    assert pdf.startswith(b"%PDF")


def test_report_survives_unicode_in_model_output():
    """fpdf core fonts are latin-1; a model verdict is untrusted text."""
    pdf = resolve_lib.build_dispute_report(
        _record(match={"score": 2, "verdict": "Différent — 日本製", "model": "m",
                       "differences": ["éclat manquant", "傷あり"]}),
        verify_base_url="https://x.test/verify")
    assert pdf.startswith(b"%PDF")


def test_typographic_punctuation_is_transliterated_not_mangled():
    """Model output is full of em-dashes and smart quotes. Rendering them as "?" in an
    evidence document reads as corruption, so they degrade to ASCII equivalents instead."""
    from originshot_pipelines.certificate import latin

    assert latin("a — b") == "a - b"
    assert latin("the buyer's “photo”") == "the buyer's \"photo\""
    assert latin("score ≥ 7…") == "score >= 7..."


def test_authentic_original_does_not_claim_a_manifest_it_has_no_reason_to_have():
    """An anchored upload carries no manifest by design; the page must not print
    "manifest absent" beside "integrity verified" and imply a contradiction."""
    lines = dict(resolve_lib._listing_lines(
        {"is_authentic": True, "present": False, "verified": True,
         "content_bound": None, "found": True}))
    assert "authentic original" in lines["File"]
    assert "anchored value" in lines["Integrity"]
    assert "not applicable" in lines["Content binding"]


def test_unknown_file_states_it_has_no_basis_to_verify():
    lines = dict(resolve_lib._listing_lines(
        {"is_authentic": False, "present": False, "verified": False,
         "content_bound": None, "found": False}))
    assert "no basis" in lines["Integrity"]


def test_broken_binding_is_stated_in_the_clear():
    lines = dict(resolve_lib._listing_lines(
        {"is_authentic": False, "present": True, "verified": True,
         "content_bound": False, "found": True}))
    assert "BROKEN" in lines["Content binding"]


# ── The endpoint ──────────────────────────────────────────────────────
def _seed_sku_with_original(client, png: bytes) -> dict:
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    asset = client.post(f"/api/skus/{sku['id']}/upload",
                        files={"file": ("p.png", png, "image/png")}).json()
    return asset


def test_requires_a_listing_reference(client):
    assert client.post("/api/resolve", data={}).status_code == 400


def test_rejects_a_malformed_hash(client):
    r = client.post("/api/resolve", data={"listing_sha256": "not-a-hash"})
    assert r.status_code == 400


def test_unknown_image_yields_no_provenance(client):
    r = client.post("/api/resolve",
                    files={"listing_file": ("x.png", _png(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["finding"] == Finding.no_provenance.value
    assert body["listing"]["found"] is False
    assert body["anchor"]["sha256"] is None


def test_anchored_original_resolves_its_own_anchor(client, png_bytes):
    """An authentic upload anchors itself, so it is its own comparison reference."""
    png = png_bytes()
    asset = _seed_sku_with_original(client, png)

    body = client.post("/api/resolve",
                       files={"listing_file": ("p.png", png, "image/png")}).json()
    assert body["listing"]["found"] is True
    assert body["listing"]["is_authentic"] is True
    assert body["anchor"]["sha256"] == asset["sha256"]
    assert body["finding"] == Finding.provenance_only.value


def test_lookup_by_hash_alone_works(client, png_bytes):
    png = png_bytes()
    asset = _seed_sku_with_original(client, png)
    body = client.post("/api/resolve",
                       data={"listing_sha256": asset["sha256"]}).json()
    assert body["listing"]["found"] is True
    assert body["anchor"]["sha256"] == asset["sha256"]


def test_report_is_stored_and_publicly_resolvable(client, png_bytes):
    """The whole point: a third party with only the id on the PDF can pull it back."""
    png = png_bytes()
    _seed_sku_with_original(client, png)
    issued = client.post("/api/resolve",
                         files={"listing_file": ("p.png", png, "image/png")}).json()

    assert issued["report_sha256"], "the issued PDF must be hash-anchored"
    fetched = client.get(f"/api/resolve/{issued['id']}").json()
    assert fetched["id"] == issued["id"]
    assert fetched["report_sha256"] == issued["report_sha256"]
    assert fetched["finding"] == issued["finding"]


def test_unknown_report_id_is_404(client):
    assert client.get("/api/resolve/nope").status_code == 404


def test_received_photo_hash_is_of_the_submitted_bytes(client, png_bytes):
    """The report's received-photo hash must be reproducible by whoever holds the file.

    Uploads are re-encoded to strip EXIF; hashing the normalized result would print a value
    the submitter could never reproduce, silently breaking the tie between the report and
    the image it describes.
    """
    png = png_bytes()
    _seed_sku_with_original(client, png)
    received = _png((10, 200, 10), size=(80, 80))

    body = client.post("/api/resolve", files={
        "listing_file": ("p.png", png, "image/png"),
        "received_file": ("arrived.png", received, "image/png"),
    }).json()
    assert body["received"]["sha256"] == hashlib.sha256(received).hexdigest()


def test_comparison_unavailable_is_reported_not_invented(client, png_bytes):
    """With no provider configured (as in this suite) no score may be fabricated."""
    png = png_bytes()
    _seed_sku_with_original(client, png)
    body = client.post("/api/resolve", files={
        "listing_file": ("p.png", png, "image/png"),
        "received_file": ("arrived.png", _png((10, 200, 10)), "image/png"),
    }).json()
    assert body["match"] is None
    assert body["match_unavailable"]
    assert body["finding"] == Finding.provenance_only.value


def test_injected_comparison_flows_into_the_finding(client, png_bytes, monkeypatch):
    """End-to-end with the transport stubbed: a real anchor is fetched and scored."""
    import app.api.resolve as resolve_api

    seen: dict = {}

    def fake_match_call(settings):
        def _call(anchor: bytes, received: bytes) -> dict:
            seen["anchor"] = anchor
            seen["received"] = received
            return {"score": 1, "verdict": "A different object.",
                    "differences": ["deep scratch on the barrel"], "model": "test-vlm"}
        return _call

    monkeypatch.setattr(resolve_api, "_make_match_call", fake_match_call)

    png = png_bytes()
    _seed_sku_with_original(client, png)
    body = client.post("/api/resolve", files={
        "listing_file": ("p.png", png, "image/png"),
        "received_file": ("arrived.png", _png((10, 200, 10)), "image/png"),
    }).json()

    # The anchor bytes really came back out of storage, not from the request.
    assert seen["anchor"], "the anchored original should have been fetched for comparison"
    assert body["match"]["score"] == 1
    assert body["match"]["differences"] == ["deep scratch on the barrel"]
    assert body["finding"] == Finding.item_mismatch.value
    assert body["severity"] == "critical"


def test_a_failing_comparison_degrades_instead_of_500ing(client, png_bytes, monkeypatch):
    import app.api.resolve as resolve_api

    def exploding(settings):
        def _call(anchor, received):
            raise RuntimeError("429 all endpoints overloaded")
        return _call

    monkeypatch.setattr(resolve_api, "_make_match_call", exploding)

    png = png_bytes()
    _seed_sku_with_original(client, png)
    r = client.post("/api/resolve", files={
        "listing_file": ("p.png", png, "image/png"),
        "received_file": ("arrived.png", _png((10, 200, 10)), "image/png"),
    })
    assert r.status_code == 200
    body = r.json()
    assert body["match"] is None
    assert "RuntimeError" in body["match_unavailable"]


def test_generated_asset_anchors_to_its_parent(client, png_bytes):
    """A listing image is normally a generated shot — its anchor is the authentic parent.

    The generated asset is seeded directly rather than produced by the dev mock: the mock
    copies the original's bytes verbatim, so under content-addressing it shares the
    original's SHA-256 and `find_asset_by_sha` can't tell the two apart. Real generations
    never collide this way; constructing the state explicitly tests anchor resolution
    instead of an artefact of the mock.
    """
    from app.repo import get_repo

    original = _seed_sku_with_original(client, png_bytes())
    generated_sha = "d" * 64
    get_repo().add_asset(original["owner_uid"], {
        "sku_id": original["sku_id"],
        "sha256": generated_sha,
        "b2_key": None,
        "modality": "image",
        "style": "studio",
        "is_authentic": False,
        "parent_sha256": original["sha256"],
        "provider": "gmicloud-image",
        "model": "gemini-3-pro-image-preview",
    })

    body = client.post("/api/resolve", data={"listing_sha256": generated_sha}).json()
    assert body["listing"]["found"] is True
    assert body["listing"]["is_authentic"] is False
    assert body["listing"]["model"] == "gemini-3-pro-image-preview"
    assert body["anchor"]["sha256"] == original["sha256"], \
        "a generated listing image must resolve back to the authentic original"
