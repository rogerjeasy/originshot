"""Text embeddings for catalog semantic search.

The visual and fraud halves of Catalog Intelligence need no model — they run on the pHash and
lineage already stored on every asset. Semantic search is the one part that needs a vector: a
buyer or seller asking "which of my products are ceramic?" is asking about *meaning*, which a
perceptual hash cannot answer.

We embed the SKU's own AI-generated text (title, description, facts, and the per-marketplace
listing copy) with OpenAI `text-embedding-3-small`, reduced to a small dimension — reachable
through the same `OPENAI_API_KEY` that already serves the voiceover and the cross-provider image
fallback, so it introduces no new provider relationship. Best-effort and degradable exactly like
those: with no key configured the capability reports itself off rather than failing a request.

Honest about scope: this is cosine similarity over stored vectors, scanned linearly. A real
vector index (HNSW/IVF) earns its complexity at millions of rows; at one shop's catalog a scan
behind a cache is simpler and truthful about its cost — the same stance the pHash search and the
transparency log's O(n-k) proofs take.
"""
from __future__ import annotations

import logging
import math

from .config import get_settings

log = logging.getLogger("originshot.embeddings")

# OpenAI's embeddings endpoint. The same base the SDK's OpenAI providers use; embeddings has no
# genblaze provider, so this is a direct, dependency-light call over the app's existing httpx.
_EMBED_URL = "https://api.openai.com/v1/embeddings"


def is_enabled() -> bool:
    """True only when semantic search is switched on AND an OpenAI key is configured."""
    settings = get_settings()
    return bool(settings.catalog_search_enabled and settings.openai_api_key)


def embed(text: str) -> list[float] | None:
    """Embed one text into a unit-comparable vector, or None if unavailable.

    Best-effort by contract: a missing key, an empty input, or any transport error yields None,
    and every caller treats that as "no vector" rather than an error — a catalog search must
    degrade to "not indexed", never fail the page.
    """
    if not is_enabled():
        return None
    text = (text or "").strip()
    if not text:
        return None
    settings = get_settings()
    try:
        import httpx

        resp = httpx.post(
            _EMBED_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.catalog_embed_model,
                "input": text[:8000],  # a SKU document is short; bound it defensively
                "dimensions": settings.catalog_embed_dim,
            },
            timeout=settings.catalog_embed_timeout_seconds,
        )
        resp.raise_for_status()
        vector = resp.json()["data"][0]["embedding"]
        return [float(x) for x in vector] if vector else None
    except Exception as exc:  # noqa: BLE001 — never fail a request over an embedding
        log.warning("embed failed (%s)", type(exc).__name__)
        return None


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]; 0.0 when either vector is empty or degenerate."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def sku_text(sku: dict) -> str:
    """Assemble the searchable document for a SKU from its own fields and listing copy.

    Deliberately draws only on text the app itself produced or the seller entered — title,
    category, description, facts, and the generated per-marketplace listing copy — so a search
    is over the catalog's real language, not an opaque derived signal.
    """
    parts: list[str] = []
    for key in ("title", "category", "description"):
        val = sku.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())

    facts = sku.get("facts")
    if isinstance(facts, dict):
        parts.extend(f"{k}: {v}" for k, v in facts.items() if v)
    elif isinstance(facts, str) and facts.strip():
        parts.append(facts.strip())

    listing = sku.get("listing")
    if isinstance(listing, dict):
        for channel in (listing.get("marketplaces") or {}).values():
            if not isinstance(channel, dict):
                continue
            for field in ("title", "description"):
                if channel.get(field):
                    parts.append(str(channel[field]))
            for field in ("bullets", "keywords"):
                seq = channel.get(field)
                if isinstance(seq, list):
                    parts.extend(str(x) for x in seq if x)

    # De-duplicate while preserving order: marketplace copy repeats the title across channels,
    # and a document that is 60% the same phrase skews the embedding toward it.
    seen: set[str] = set()
    unique = [p for p in parts if not (p in seen or seen.add(p))]
    return "\n".join(unique)
