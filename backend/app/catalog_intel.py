"""Catalog Intelligence — search and integrity over everything a seller has stored.

Three capabilities, and the split between them is the honest part of the story:

  * **Visual similarity** and **duplicate/reused-original detection** need no model at all. They
    run on the perceptual hash and the authentic-original lineage (`parent_sha256`) that every
    asset already carries — so "find products that look like this" and "this one real photo is
    behind three *different* listings" are cross-catalog reads over data we already store, not a
    new pipeline. This is the fraud-facing half, and it extends the project's thesis from "is
    this the real product?" to "is this seller honest across their whole shop?"
  * **Semantic search** is the one net-new capability, and it lives in `app/embeddings.py`: the
    SKU's text is embedded with OpenAI and matched by cosine. It degrades to "unavailable" with
    no key, so the visual and integrity halves work regardless.

The vectors are stored on B2 (`embeddings/<uid>.json`) as the durable, portable index — the
same repo-plus-B2 pattern the transparency checkpoints use — while the per-SKU copy on the
record is the fast query path.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from originshot_pipelines import perceptual

from . import embeddings
from .config import get_settings
from .repo import get_repo

log = logging.getLogger("originshot.catalog")

EMBEDDING_PREFIX = "embeddings"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Visual similarity (pHash) ─────────────────────────────────────────
def visual_similar(uid: str, sha256: str, limit: int) -> list[dict]:
    """The seller's other assets that *look like* one of theirs, nearest first.

    Scoped to the owner (unlike the public `find_similar_by_phash`, which spans all sellers for
    the buyer-facing verifier): this answers "what else in *my* catalog resembles this?", so a
    scan over the caller's own assets is both correct and cheap.
    """
    repo = get_repo()
    assets = repo.list_assets_for_user(uid)
    query = next((a for a in assets if a.get("sha256") == sha256), None)
    if not query or not query.get("phash"):
        return []
    max_distance = get_settings().catalog_similar_max_distance

    hits: list[dict] = []
    for a in assets:
        if a.get("sha256") == sha256 or not a.get("phash"):
            continue
        dist = perceptual.hamming(query["phash"], a["phash"])
        if dist is not None and dist <= max_distance:
            hits.append({**a, "phash_distance": dist})
    hits.sort(key=lambda a: a["phash_distance"])
    return hits[:limit]


# ── Integrity: reused originals + near-duplicate sources ──────────────
def integrity(uid: str) -> dict:
    """Cross-catalog integrity findings for one seller. Signals for review, never accusations.

    Two findings, both honest about being *signals*: a seller may legitimately list variations of
    one item, so these flag for a human rather than concluding fraud.
    """
    assets = get_repo().list_assets_for_user(uid)
    reused = _reused_originals(assets)
    near = _near_duplicate_sources(assets, get_settings().catalog_duplicate_max_distance)
    return {
        "reused_originals": reused,
        "near_duplicate_sources": near,
        "skus_analyzed": len({a.get("sku_id") for a in assets if a.get("sku_id")}),
        "generated_at": _now(),
    }


def _reused_originals(assets: list[dict]) -> list[dict]:
    """One authentic original behind *distinct* SKUs — the exact-reuse signal.

    Grouping by `parent_sha256` and counting **distinct** sku_ids is the whole trick: every style
    within a single SKU legitimately shares one parent, so the finding fires only when the same
    pre-AI photo anchors more than one product.
    """
    by_parent: dict[str, set[str]] = {}
    for a in assets:
        parent = a.get("parent_sha256")
        sku = a.get("sku_id")
        if parent and sku:
            by_parent.setdefault(parent, set()).add(sku)

    findings = [
        {"parent_sha256": parent, "sku_ids": sorted(skus), "sku_count": len(skus)}
        for parent, skus in by_parent.items() if len(skus) > 1
    ]
    findings.sort(key=lambda f: f["sku_count"], reverse=True)
    return findings


def _near_duplicate_sources(assets: list[dict], max_distance: int) -> list[dict]:
    """SKUs whose authentic source photos are perceptually near-identical across products.

    Catches what exact-reuse cannot: a seller who re-saved or lightly re-shot one item and listed
    it as several — different bytes (so `parent_sha256` differs) but the same picture. Clusters the
    per-SKU original pHashes with a strict threshold via union-find.
    """
    # One representative (the authentic original) per SKU; a SKU with no stored original can't be
    # compared and is simply absent, never a false pair.
    reps: list[tuple[str, str]] = []  # (sku_id, phash)
    seen_skus: set[str] = set()
    for a in assets:
        sku = a.get("sku_id")
        if a.get("is_authentic") and a.get("phash") and sku and sku not in seen_skus:
            reps.append((sku, a["phash"]))
            seen_skus.add(sku)

    parent = {sku: sku for sku, _ in reps}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(reps)):
        for j in range(i + 1, len(reps)):
            dist = perceptual.hamming(reps[i][1], reps[j][1])
            if dist is not None and dist <= max_distance:
                parent[find(reps[i][0])] = find(reps[j][0])

    clusters: dict[str, list[str]] = {}
    for sku, _ in reps:
        clusters.setdefault(find(sku), []).append(sku)
    findings = [
        {"sku_ids": sorted(members), "sku_count": len(members)}
        for members in clusters.values() if len(members) > 1
    ]
    findings.sort(key=lambda f: f["sku_count"], reverse=True)
    return findings


# ── Semantic search (embeddings on B2) ────────────────────────────────
def reindex_user(uid: str) -> dict:
    """(Re)embed every SKU's text and publish the vector index to B2.

    Skips SKUs whose text hasn't changed since last time (a source hash guards the re-embed) and
    SKUs with no text to embed. Returns counts. Best-effort on the B2 write — the per-SKU copy on
    the record is what queries read, the B2 object is the durable, portable index.
    """
    if not embeddings.is_enabled():
        return {"available": False, "embedded": 0, "skipped": 0, "total": 0}
    repo = get_repo()
    skus = repo.list_skus(uid)
    embedded = skipped = 0
    index: list[dict] = []
    for sku in skus:
        text = embeddings.sku_text(sku)
        if not text:
            skipped += 1
            continue
        source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        existing = sku.get("catalog_embedding") or {}
        vector = existing.get("vector")
        if existing.get("source_hash") == source_hash and vector:
            index.append({"sku_id": sku["id"], "title": sku.get("title"),
                          "source_hash": source_hash, "vector": vector})
            skipped += 1
            continue
        vector = embeddings.embed(text)
        if vector is None:
            skipped += 1
            continue
        record = {"model": get_settings().catalog_embed_model, "dim": len(vector),
                  "vector": vector, "source_hash": source_hash, "updated_at": _now()}
        repo.update_sku(uid, sku["id"], {"catalog_embedding": record})
        index.append({"sku_id": sku["id"], "title": sku.get("title"),
                      "source_hash": source_hash, "vector": vector})
        embedded += 1

    _publish_index(uid, index)
    return {"available": True, "embedded": embedded, "skipped": skipped, "total": len(skus)}


def reindex_sku(uid: str, sku_id: str) -> bool:
    """Embed one SKU now (called best-effort when its listing copy is (re)generated)."""
    if not embeddings.is_enabled():
        return False
    repo = get_repo()
    sku = repo.get_sku(uid, sku_id)
    if not sku:
        return False
    text = embeddings.sku_text(sku)
    if not text:
        return False
    vector = embeddings.embed(text)
    if vector is None:
        return False
    repo.update_sku(uid, sku_id, {"catalog_embedding": {
        "model": get_settings().catalog_embed_model, "dim": len(vector), "vector": vector,
        "source_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(), "updated_at": _now(),
    }})
    return True


def semantic_search(uid: str, query: str, limit: int) -> dict:
    """Rank the seller's SKUs by meaning against a free-text query.

    Returns ``{available, indexed, hits}``. `available` is False when semantic search is off (no
    key) — the caller surfaces that honestly rather than pretending the catalog has no matches.
    """
    if not embeddings.is_enabled():
        return {"available": False, "indexed": 0, "hits": []}
    qvec = embeddings.embed(query)
    if qvec is None:
        return {"available": False, "indexed": 0, "hits": []}

    skus = get_repo().list_skus(uid)
    scored: list[dict] = []
    indexed = 0
    for sku in skus:
        vector = (sku.get("catalog_embedding") or {}).get("vector")
        if not vector:
            continue
        indexed += 1
        score = embeddings.cosine(qvec, vector)
        # A small floor keeps a query with no real match from returning the whole catalog ranked
        # by noise; the cutoff is deliberately low because cosine on short docs runs low overall.
        if score > 0.15:
            scored.append({"sku_id": sku["id"], "title": sku.get("title"),
                           "category": sku.get("category"), "score": round(score, 4)})
    scored.sort(key=lambda h: h["score"], reverse=True)
    return {"available": True, "indexed": indexed, "hits": scored[:limit]}


def _publish_index(uid: str, index: list[dict]) -> None:
    """Write the per-user vector index to B2 — the durable, portable copy of the search index."""
    try:
        from .storage import get_storage

        body = json.dumps({
            "uid": uid, "model": get_settings().catalog_embed_model,
            "dim": get_settings().catalog_embed_dim, "count": len(index),
            "updated_at": _now(), "skus": index,
        }, sort_keys=True).encode("utf-8")
        get_storage().put_bytes(f"{EMBEDDING_PREFIX}/{uid}.json", body, "application/json")
    except Exception as exc:  # noqa: BLE001 — the query path reads the record, not this object
        log.warning("catalog index publish to B2 failed for %s: %s", uid, type(exc).__name__)
