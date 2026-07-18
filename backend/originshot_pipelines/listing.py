"""Listing copy generation — the second-most-hated seller chore after the photos.

One chat-model call turns the SKU's facts (title, category, description, brand kit) into
per-marketplace listing copy that respects each channel's actual rules — title length
caps, bullet counts, tag limits — which are enforced *in code* after the model responds,
because a character limit is a fact, not a suggestion.

Same transport rules as the QA tier (see registry.py): the GMI chat endpoint can 429 under
load, so callers must treat failure as "try again", never as a broken SKU. The output
always carries its own AI-disclosure line; copy that ships in the export pack discloses
itself the same way the images do.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

log = logging.getLogger("originshot.listing")

# The per-channel rules the prompt teaches and the normalizer enforces. Real listing
# rejection reasons, not invented structure: Amazon suppresses listings with >200-char
# titles; eBay hard-caps at 80; Etsy indexes 13 tags; social captions truncate at ~125
# chars in feed view.
RULES: dict[str, dict] = {
    "amazon": {
        "title_max": 200, "bullet_count": 5, "keyword_count": 0,
        "guidance": "Title in Title Case, no promotional phrases (no 'free shipping', "
                    "no 'sale'), lead with brand/product type. Exactly 5 benefit-led "
                    "bullet points, each starting with a capitalised feature phrase.",
    },
    "etsy": {
        "title_max": 140, "bullet_count": 0, "keyword_count": 13,
        "guidance": "Buyer-search phrasing, front-load the first 40 characters with what "
                    "a buyer would type. Provide exactly 13 tags, each under 20 characters, "
                    "no repeats of single words already in the title.",
    },
    "shopify": {
        "title_max": 70, "bullet_count": 3, "keyword_count": 5,
        "guidance": "SEO page title under 70 characters and a description whose first "
                    "sentence works as a meta description (~155 characters).",
    },
    "ebay": {
        "title_max": 80, "bullet_count": 3, "keyword_count": 0,
        "guidance": "Max 80 characters, no ALL CAPS words, include brand, item type, and "
                    "key attribute. No promotional language.",
    },
    "social": {
        "title_max": 125, "bullet_count": 0, "keyword_count": 8,
        "guidance": "A feed caption whose first 125 characters stand alone, warm and "
                    "human, one emoji maximum. Provide up to 8 relevant hashtags as "
                    "keywords, without the # symbol.",
    },
}


def disclosure_line(model: str) -> str:
    return (
        f"AI-generated listing copy. Model: {model} (GMI Cloud). "
        "Review for accuracy before publishing — you are responsible for listing claims."
    )


def build_prompt(sku: dict, brand: dict | None, marketplaces: list[str]) -> str:
    facts = [f"Product title: {sku.get('title') or 'Untitled product'}"]
    if sku.get("category"):
        facts.append(f"Category: {sku['category']}")
    if sku.get("description"):
        facts.append(f"Seller's description: {sku['description']}")
    if brand:
        kit = "; ".join(f"{k}: {v}" for k, v in brand.items() if v and k != "notes")
        if kit:
            facts.append(f"Brand voice: {kit}")

    channels = []
    for m in marketplaces:
        r = RULES[m]
        parts = [f'"{m}"', f"title <= {r['title_max']} chars"]
        if r["bullet_count"]:
            parts.append(f"exactly {r['bullet_count']} bullets")
        if r["keyword_count"]:
            parts.append(f"exactly {r['keyword_count']} keywords")
        channels.append(f"- {', '.join(parts)}. {r['guidance']}")

    return (
        "You write product listing copy for e-commerce sellers. Using ONLY the facts "
        "below — never invent materials, dimensions, or claims not stated — write listing "
        "copy for each requested marketplace.\n\n"
        + "\n".join(facts)
        + "\n\nMarketplaces and their rules:\n"
        + "\n".join(channels)
        + "\n\nKeep every description under 120 words — tight copy sells and slow "
        "generations time out.\n\nReply with ONLY this JSON, no other text:\n"
        '{"<marketplace>": {"title": "...", "description": "...", '
        '"bullets": ["..."], "keywords": ["..."]}, ...}\n'
        "Every requested marketplace must be a key. Use empty arrays where a channel "
        "needs no bullets or keywords."
    )


def _normalize(raw: dict, marketplaces: list[str]) -> dict:
    """Enforce the hard limits in code — the model proposes, the rules dispose."""
    out: dict[str, dict] = {}
    for m in marketplaces:
        r = RULES[m]
        entry = raw.get(m) or {}
        title = str(entry.get("title") or "").strip()[: r["title_max"]]
        bullets = [str(b).strip() for b in (entry.get("bullets") or []) if str(b).strip()]
        if r["bullet_count"]:
            bullets = bullets[: r["bullet_count"]]
        keywords = [str(k).strip().lstrip("#") for k in (entry.get("keywords") or [])
                    if str(k).strip()]
        if r["keyword_count"]:
            keywords = keywords[: r["keyword_count"]]
        out[m] = {
            "title": title,
            "description": str(entry.get("description") or "").strip(),
            "bullets": bullets,
            "keywords": keywords,
            "title_max": r["title_max"],
        }
    return out


def generate_listing(sku: dict, brand: dict | None, marketplaces: list[str], *,
                     api_key: str, base_url: str, model: str, timeout: int = 240) -> dict:
    """One chat call → normalized per-marketplace copy. Raises on transport/parse failure."""
    import httpx

    wanted = [m for m in marketplaces if m in RULES] or list(RULES)
    body = {
        "model": model,
        "temperature": 0.4,
        "max_tokens": 3000,  # reasoning-model headroom; small budgets come back empty
        "messages": [{"role": "user", "content": build_prompt(sku, brand, wanted)}],
    }
    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=body,
        timeout=timeout,
    )
    resp.raise_for_status()
    content = (resp.json()["choices"][0]["message"].get("content") or "").strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError(f"listing model returned no JSON: {content[:120]!r}")
    raw = json.loads(match.group(0))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "gmicloud-chat",
        "model": model,
        "disclosure": disclosure_line(model),
        "marketplaces": _normalize(raw, wanted),
    }


def listing_text(marketplace: str, entry: dict, disclosure: str) -> str:
    """Render one marketplace's copy as the paste-ready .txt that ships in the export."""
    lines = [
        f"{marketplace.upper()} LISTING COPY",
        "=" * 60,
        "",
        f"TITLE ({len(entry.get('title') or '')}/{entry.get('title_max', '?')} chars)",
        entry.get("title") or "",
        "",
    ]
    if entry.get("bullets"):
        lines.append("BULLETS")
        lines += [f"  - {b}" for b in entry["bullets"]]
        lines.append("")
    lines += ["DESCRIPTION", entry.get("description") or "", ""]
    if entry.get("keywords"):
        lines += ["KEYWORDS / TAGS", ", ".join(entry["keywords"]), ""]
    lines += ["-" * 60, disclosure]
    return "\n".join(lines)
