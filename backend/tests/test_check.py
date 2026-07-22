"""Verify Anywhere (POST /api/check) — the public buyer surface, and its SSRF guard.

Two concerns are tested here. The endpoint behaviour: a buyer's link or dropped photo reaches
the same perceptual match as /verify, wrapped so the UI knows where the image came from. And
the security-critical part: `app.fetch` must refuse to fetch anything that points inward, no
matter how the target is dressed up (literal private IP, a name that resolves to one, a
redirect to one, a non-HTTP scheme, an odd port).
"""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from app import fetch
from app.fetch import FetchError, Fetched
from originshot_pipelines import perceptual


# ── fixtures / helpers (mirrors tests/test_verify_in_the_wild.py) ──────────────────────────
def _structured_png(seed: int, size: int = 512) -> bytes:
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, size=(8, 8, 3), dtype=np.uint8)
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


def _seed_asset(png: bytes, *, sha: str, parent: str, style: str = "studio") -> None:
    from app.repo import get_repo

    get_repo().add_asset("seller-1", {
        "sku_id": "sku-1", "sha256": sha, "phash": perceptual.phash(png),
        "parent_sha256": parent, "style": style, "provider": "openai-dalle",
        "model": "gpt-image-1", "is_authentic": False, "modality": "image",
    })


# ══ SSRF hardening (app.fetch) ═════════════════════════════════════════════════════════════
@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/",   # cloud metadata (link-local)
    "http://127.0.0.1/",                            # loopback
    "http://10.0.0.1/",                             # private
    "http://192.168.1.1/",                          # private
    "http://[::1]/",                                # IPv6 loopback
    "http://100.64.0.1/",                           # CGNAT
    "http://0.0.0.0/",                              # unspecified
])
def test_literal_internal_targets_are_rejected(url):
    with pytest.raises(FetchError):
        fetch.fetch_url(url, timeout=2, max_bytes=1024)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://host/x", "gopher://h:70/_"])
def test_non_web_schemes_are_rejected(url):
    with pytest.raises(FetchError):
        fetch.fetch_url(url, timeout=2, max_bytes=1024)


def test_odd_port_is_rejected():
    with pytest.raises(FetchError):
        fetch.fetch_url("http://8.8.8.8:22/", timeout=2, max_bytes=1024)


def test_hostname_resolving_to_private_ip_is_rejected(monkeypatch):
    """The classic bypass: a public-looking name whose DNS answer is a private address."""
    def fake_getaddrinfo(host, *a, **k):
        return [(None, None, None, "", ("10.1.2.3", 0))]

    monkeypatch.setattr(fetch.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(FetchError):
        fetch.fetch_url("https://totally-legit.example/x.jpg", timeout=2, max_bytes=1024)


def test_public_ip_passes_validation():
    fetch._validate_url("https://8.8.8.8/x.jpg")   # 8.8.8.8 is public → no raise


def test_ipv4_mapped_ipv6_private_is_blocked():
    import ipaddress

    assert fetch._ip_is_blocked(ipaddress.ip_address("::ffff:10.0.0.1")) is True
    assert fetch._ip_is_blocked(ipaddress.ip_address("8.8.8.8")) is False


def test_extract_image_urls_prefers_og_image_and_absolutises():
    html = (
        b'<html><head><meta property="og:image" content="/img/main.jpg">'
        b'</head><body><img src="https://cdn.example/thumb.png">'
        b'<img src="data:image/png;base64,AAAA"></body></html>'
    )
    urls = fetch.extract_image_urls(html, "https://shop.example/item/1", limit=4)
    assert urls[0] == "https://shop.example/img/main.jpg"   # og:image first, made absolute
    assert "https://cdn.example/thumb.png" in urls
    assert all(not u.startswith("data:") for u in urls)     # data: URIs dropped


# ══ Endpoint: dropped file ═════════════════════════════════════════════════════════════════
def test_dropped_reencoded_photo_matches_like_verify(client):
    original = _structured_png(seed=1)
    _seed_asset(original, sha="a" * 64, parent="parent123abc" + "0" * 52)

    wild = _reencode(original)
    r = client.post("/api/check", files={"file": ("listing.jpg", wild, "image/jpeg")})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "upload"
    pm = body["result"]["perceptual"]
    assert pm is not None and pm["matched_sha256"] == "a" * 64
    assert pm["parent_sha256"].startswith("parent123abc")
    # Privacy posture: lineage is a HASH, never a link to the seller's private original.
    assert "http" not in (pm["parent_sha256"] or "")


# ══ Endpoint: URL paths (fetch monkeypatched — no real network) ════════════════════════════
def test_direct_image_url_is_checked(client, monkeypatch):
    import app.api.check as check_mod

    original = _structured_png(seed=2)
    _seed_asset(original, sha="b" * 64, parent="p" * 64)
    wild = _reencode(original)

    monkeypatch.setattr(check_mod, "fetch_url",
                        lambda url, **k: Fetched(wild, "image/jpeg", url))
    r = client.post("/api/check", data={"url": "https://cdn.shop.com/p.jpg"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "url_image"
    assert body["source_url"] == "https://cdn.shop.com/p.jpg"
    assert body["result"]["perceptual"]["matched_sha256"] == "b" * 64


def test_listing_page_url_extracts_and_matches(client, monkeypatch):
    import app.api.check as check_mod

    original = _structured_png(seed=3)
    _seed_asset(original, sha="c" * 64, parent="p" * 64)
    wild = _reencode(original)

    page = "https://shop.example/item/9"
    img = "https://cdn.example/main.jpg"
    html = f'<html><head><meta property="og:image" content="{img}"></head></html>'.encode()

    def fake_fetch(url, **k):
        if url == page:
            return Fetched(html, "text/html; charset=utf-8", url)
        if url == img:
            return Fetched(wild, "image/jpeg", url)
        raise FetchError("unexpected url")

    monkeypatch.setattr(check_mod, "fetch_url", fake_fetch)
    r = client.post("/api/check", data={"url": page})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "listing_page"
    assert body["images_scanned"] == 1
    assert body["result"]["perceptual"]["matched_sha256"] == "c" * 64


def test_listing_page_with_no_images_returns_422(client, monkeypatch):
    import app.api.check as check_mod

    monkeypatch.setattr(check_mod, "fetch_url",
                        lambda url, **k: Fetched(b"<html><body>nothing</body></html>",
                                                 "text/html", url))
    r = client.post("/api/check", data={"url": "https://shop.example/empty"})
    assert r.status_code == 422


def test_internal_url_reaches_the_guard_through_the_endpoint(client):
    """End to end: a metadata-address link returns a clean 400, never a hang or a 500."""
    r = client.post("/api/check", data={"url": "http://169.254.169.254/latest/meta-data/"})
    assert r.status_code == 400
    assert "private or internal" in r.json()["detail"].lower()


# ══ Endpoint: guards ═══════════════════════════════════════════════════════════════════════
def test_neither_file_nor_url_is_400(client):
    assert client.post("/api/check").status_code == 400


def test_both_file_and_url_is_400(client, png_bytes):
    r = client.post("/api/check",
                    data={"url": "https://x.example/a.jpg"},
                    files={"file": ("a.png", png_bytes(), "image/png")})
    assert r.status_code == 400


def test_disabled_instance_returns_503(client, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("VERIFY_WILD_ENABLED", "false")
    r = client.post("/api/check", data={"url": "https://x.example/a.jpg"})
    assert r.status_code == 503
    get_settings.cache_clear()
