"""Public, embeddable provenance badge — an SVG that resolves live against this instance.

A seller drops one `<img>` into a marketplace listing and the badge answers, from the file's
content hash alone, *"is this a verifiable OriginShot asset?"* — right where the buyer is
looking, not only inside our app. It is an SVG (not an iframe) on purpose: an `<img>` renders
in far more places a listing allows than an embedded frame does, and being generated per
request it always reflects the current ledger rather than a snapshot baked in at export.

    <a href="https://originshot.vercel.app/verify/<sha>">
      <img src="https://originshot-api.onrender.com/api/badge/<sha>.svg"
           alt="OriginShot provenance" height="20">
    </a>

The badge states, and why each is honest:
  * **Authentic ✓** — a hash-anchored authentic original (the pre-AI photo).
  * **AI · Provenance ✓** — an AI-generated asset whose manifest verifies; "AI" is stated
    plainly (this is a disclosure feature, not a hide-the-AI one), and the tick is about the
    provenance being checkable, never about the image being "real".
  * **AI · unverified** — we hold the record but its manifest didn't verify.
  * **Unverified** — no record for this hash in this instance. Deliberately neutral, never a
    red "fake": absence is not proof (a marketplace re-encode strips the manifest and changes
    the hash), exactly as /verify itself refuses to present absence as a negative signal.

No auth (a buyer has no account) and no private data ever leaves — only the same
non-sensitive classification /verify already exposes. The global per-IP limiter applies; the
lookup is a single indexed read, and a short cache header keeps a popular listing cheap.
"""
from __future__ import annotations

import html

from fastapi import APIRouter
from fastapi.responses import Response

from .. import transparency
from ..repo import get_repo

router = APIRouter(tags=["badge"])

# Palette — muted, legible on both light and dark listing backgrounds. Provenance-positive
# states read confident (green / teal); the neutral state is grey, never alarm-red.
_BRAND_BG = "#1f2430"          # left segment (the "OriginShot" label)
_GREEN = "#2ea043"             # authentic
_TEAL = "#0b7285"             # AI, provenance verified
_AMBER = "#b7791f"            # AI, unverified
_GREY = "#8b929e"             # no record
_TEXT = "#ffffff"

_LABEL = "OriginShot"


def _badge_state(sha256: str) -> tuple[str, str]:
    """Return ``(value_text, color)`` for the badge, from the same lookup /verify uses."""
    asset = get_repo().find_asset_by_sha(sha256)
    if not asset:
        return "Unverified", _GREY
    if asset.get("is_authentic"):
        return "Authentic ✓", _GREEN
    mv = asset.get("manifest_verified")
    verified = True if mv is None else bool(mv)
    if not verified:
        return "AI · unverified", _AMBER
    in_ledger = transparency.position_for(sha256) is not None
    return ("AI · Provenance ✓" if in_ledger else "AI · Verified ✓"), _TEAL


def _text_width(text: str) -> int:
    """Rough advance width at 11px Verdana — wide enough that text never clips. Uppercase and
    a few wide glyphs cost more; the tick/·  are counted generously."""
    w = 0.0
    for ch in text:
        if ch in "mwMW✓":
            w += 9.0
        elif ch in "il·.'":
            w += 3.5
        elif ch.isupper():
            w += 7.5
        else:
            w += 6.3
    return int(w + 0.5)


def _svg(label: str, value: str, color: str) -> str:
    pad = 10
    lw = _text_width(label) + pad * 2
    vw = _text_width(value) + pad * 2
    total = lw + vw
    h = 20
    # Text is placed at each segment's centre; a 1px dark shadow (dy=1, low opacity) is the
    # shields.io trick that keeps light text readable on either fill.
    le = html.escape(label)
    ve = html.escape(value)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{h}" role="img" aria-label="{le}: {ve}">
  <title>{le}: {ve}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#fff" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total}" height="{h}" rx="4" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{lw}" height="{h}" fill="{_BRAND_BG}"/>
    <rect x="{lw}" width="{vw}" height="{h}" fill="{color}"/>
    <rect width="{total}" height="{h}" fill="url(#s)"/>
  </g>
  <g fill="{_TEXT}" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{lw / 2}" y="15" fill="#010101" fill-opacity=".3">{le}</text>
    <text x="{lw / 2}" y="14">{le}</text>
    <text x="{lw + vw / 2}" y="15" fill="#010101" fill-opacity=".3">{ve}</text>
    <text x="{lw + vw / 2}" y="14">{ve}</text>
  </g>
</svg>"""


def _render(sha256: str) -> Response:
    value, color = _badge_state(sha256)
    svg = _svg(_LABEL, value, color)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            # Short cache: live enough that a re-verify shows within minutes, cheap enough that
            # a popular listing doesn't hammer the lookup. no-transform stops a proxy mangling
            # the SVG. Public so a CDN/marketplace image cache can hold it.
            "Cache-Control": "public, max-age=300, no-transform",
        },
    )


@router.get("/badge/{sha256}.svg")
def badge_svg(sha256: str) -> Response:
    """Embeddable provenance badge (SVG) for a content hash. Public, no auth."""
    return _render(sha256)


@router.get("/badge/{sha256}")
def badge(sha256: str) -> Response:
    """Convenience alias without the extension — same SVG."""
    return _render(sha256)
