"""Catalog Intelligence — visual search, integrity/fraud signals, and semantic search.

The visual and integrity halves run on the pHash + lineage already stored, so they're tested
with directly-seeded assets and crafted pHashes (deterministic Hamming distances). Semantic
search is tested with a fake embedder — the ranking logic is ours; OpenAI's vectors are not.
"""
from __future__ import annotations

import pytest

from app import embeddings

UID = "dev-user"  # the auth-dev-bypass user the client fixture authenticates as

# Crafted 16-hex (64-bit) pHashes with known Hamming distances from A:
_A = "0000000000000000"
_A2 = "0000000000000003"  # distance 2 from _A  → near-duplicate (<=6) and similar (<=12)
_FAR = "ffffffffffffffff"  # distance 64 from _A → neither


def _seed(sku_id: str, sha: str, *, parent=None, phash=None, authentic=False):
    from app.repo import get_repo

    return get_repo().add_asset(UID, {
        "sku_id": sku_id, "sha256": sha, "phash": phash, "parent_sha256": parent,
        "is_authentic": authentic, "modality": "image", "style": "studio",
        "b2_key": f"assets/{sha[:2]}/{sha[2:4]}/{sha}.png",
    })


# ── Integrity: reused originals ───────────────────────────────────────
def test_reused_original_across_two_skus_is_flagged(client):
    # One authentic photo (parent "p"*64) anchors generated assets in TWO different SKUs.
    _seed("sku-A", "a" * 64, parent="p" * 64)
    _seed("sku-B", "b" * 64, parent="p" * 64)
    _seed("sku-C", "c" * 64, parent="q" * 64)  # a different original, one SKU — fine

    r = client.get("/api/catalog/integrity")
    assert r.status_code == 200
    findings = r.json()["reused_originals"]
    assert len(findings) == 1
    assert findings[0]["parent_sha256"] == "p" * 64
    assert sorted(findings[0]["sku_ids"]) == ["sku-A", "sku-B"]
    assert findings[0]["sku_count"] == 2


def test_multiple_styles_in_one_sku_are_not_a_reuse(client):
    # studio + lifestyle of ONE product legitimately share a parent — must NOT flag.
    _seed("sku-A", "a" * 64, parent="p" * 64)
    _seed("sku-A", "b" * 64, parent="p" * 64)
    assert client.get("/api/catalog/integrity").json()["reused_originals"] == []


# ── Integrity: near-duplicate source photos ───────────────────────────
def test_near_duplicate_originals_across_skus_are_flagged(client):
    # Two SKUs whose authentic originals are perceptually near-identical (distance 2).
    _seed("sku-A", "a" * 64, phash=_A, authentic=True)
    _seed("sku-B", "b" * 64, phash=_A2, authentic=True)
    _seed("sku-C", "c" * 64, phash=_FAR, authentic=True)  # unrelated

    near = client.get("/api/catalog/integrity").json()["near_duplicate_sources"]
    assert len(near) == 1
    assert sorted(near[0]["sku_ids"]) == ["sku-A", "sku-B"]


def test_distinct_catalog_has_no_findings(client):
    _seed("sku-A", "a" * 64, parent="p" * 64, phash=_A, authentic=True)
    _seed("sku-B", "b" * 64, parent="q" * 64, phash=_FAR, authentic=True)
    body = client.get("/api/catalog/integrity").json()
    assert body["reused_originals"] == []
    assert body["near_duplicate_sources"] == []
    assert body["skus_analyzed"] == 2


# ── Visual similarity search ──────────────────────────────────────────
def test_visual_similar_returns_near_neighbours_only(client):
    _seed("sku-A", "a" * 64, phash=_A)
    _seed("sku-A", "b" * 64, phash=_A2)   # near — should match
    _seed("sku-B", "c" * 64, phash=_FAR)  # far — should not

    r = client.get(f"/api/library/similar?sha256={'a' * 64}")
    assert r.status_code == 200
    rows = r.json()
    assert [row["sha256"] for row in rows] == ["b" * 64]   # the near one, not itself, not far
    assert rows[0]["phash_distance"] == 2


def test_visual_similar_of_unknown_hash_is_empty(client):
    _seed("sku-A", "a" * 64, phash=_A)
    assert client.get(f"/api/library/similar?sha256={'z' * 64}").json() == []


# ── Semantic search (fake embedder — no network) ──────────────────────
def _fake_embed(text: str):
    """A 3-dim toy embedding: [ceramic, linen, bias]. Deterministic, offline."""
    t = (text or "").lower()
    return [1.0 if "ceramic" in t else 0.0, 1.0 if "linen" in t else 0.0, 0.1]


@pytest.fixture
def semantic(monkeypatch):
    monkeypatch.setattr(embeddings, "is_enabled", lambda: True)
    monkeypatch.setattr(embeddings, "embed", _fake_embed)


def _make_sku(client, title: str) -> str:
    return client.post("/api/skus", json={"title": title}).json()["id"]


def test_reindex_then_search_ranks_by_meaning(client, semantic):
    _make_sku(client, "Handmade ceramic mug")
    _make_sku(client, "Natural linen apron")

    reindexed = client.post("/api/catalog/reindex").json()
    assert reindexed["available"] is True
    assert reindexed["embedded"] == 2

    hits = client.get("/api/library/search?q=ceramic").json()
    assert hits["available"] is True
    assert hits["indexed"] == 2
    assert hits["hits"][0]["title"] == "Handmade ceramic mug"
    assert hits["hits"][0]["score"] > 0.9


def test_reindex_publishes_the_vector_index_to_b2(client, semantic):
    _make_sku(client, "Handmade ceramic mug")
    client.post("/api/catalog/reindex")

    from app.storage import get_storage

    body = get_storage().get_bytes(f"embeddings/{UID}.json")  # the durable B2 index
    import json

    index = json.loads(body)
    assert index["count"] == 1
    assert index["skus"][0]["vector"] == _fake_embed("Handmade ceramic mug")


def test_search_reports_unavailable_without_a_key(client):
    """Default suite has no OPENAI_API_KEY → semantic search is off, and says so distinctly."""
    _make_sku(client, "Handmade ceramic mug")
    body = client.get("/api/library/search?q=ceramic").json()
    assert body["available"] is False
    assert body["hits"] == []

    reindexed = client.post("/api/catalog/reindex").json()
    assert reindexed["available"] is False
