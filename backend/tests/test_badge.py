"""Public embeddable provenance badge (app/api/badge.py).

The badge is a live SVG a seller drops into a listing. It must: be a valid, cacheable SVG;
never present "no record" as a red "fake" (absence isn't proof — a marketplace re-encode
strips the manifest and changes the hash); disclose AI plainly; and leak nothing private.
"""
from __future__ import annotations

from app.repo import get_repo

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_0 = "0" * 64


def _is_svg(text: str) -> bool:
    return text.lstrip().startswith("<svg") and "</svg>" in text


def test_unknown_hash_is_neutral_not_a_red_fake(client):
    r = client.get(f"/api/badge/{SHA_0}.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert _is_svg(r.text)
    assert "OriginShot" in r.text
    assert "Unverified" in r.text
    # Never the alarm-red of a "fake" claim — absence is not evidence.
    assert "#2ea043" not in r.text and "Fake" not in r.text


def test_badge_is_cacheable(client):
    r = client.get(f"/api/badge/{SHA_0}.svg")
    assert "public" in r.headers.get("cache-control", "")


def test_authentic_asset_reads_authentic(client):
    get_repo().add_asset("u1", {
        "sha256": SHA_A, "sku_id": "s1", "is_authentic": True,
        "modality": "image", "style": "original",
    })
    r = client.get(f"/api/badge/{SHA_A}")
    assert r.status_code == 200
    assert _is_svg(r.text)
    assert "Authentic" in r.text


def test_ai_asset_discloses_ai_and_verifies(client):
    get_repo().add_asset("u1", {
        "sha256": SHA_B, "sku_id": "s1", "is_authentic": False,
        "manifest_verified": True, "modality": "image", "style": "studio",
        "provider": "gmicloud-image", "model": "gemini-3-pro-image-preview",
    })
    r = client.get(f"/api/badge/{SHA_B}.svg")
    assert "AI" in r.text                       # AI is disclosed, never hidden
    assert "✓" in r.text                        # provenance is checkable


def test_ai_unverified_is_amber_not_green(client):
    get_repo().add_asset("u1", {
        "sha256": SHA_B, "sku_id": "s1", "is_authentic": False,
        "manifest_verified": False, "modality": "image", "style": "studio",
    })
    r = client.get(f"/api/badge/{SHA_B}.svg")
    assert "unverified" in r.text.lower()


def test_badge_leaks_no_private_fields(client):
    get_repo().add_asset("u1", {
        "sha256": SHA_B, "sku_id": "s1", "is_authentic": False, "manifest_verified": True,
        "modality": "image", "style": "studio", "b2_key": "assets/bb/bb/secret.png",
        "owner_uid": "u1",
    })
    r = client.get(f"/api/badge/{SHA_B}.svg")
    # The badge shows a classification only — never storage keys, prompts, or owner ids.
    assert "secret" not in r.text and "b2_key" not in r.text and "u1" not in r.text


def test_extension_and_bare_paths_agree(client):
    a = client.get(f"/api/badge/{SHA_0}.svg").text
    b = client.get(f"/api/badge/{SHA_0}").text
    assert a == b
