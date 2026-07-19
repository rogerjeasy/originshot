"""Certificate of Provenance — the pack's tangible, human-readable proof sheet.

One PDF per export: the authentic original's anchor, every generated asset's content
hash, models, timestamps, QA verdicts, and a QR code that resolves to the public
verifier. The certificate is deliberately honest about its own standing: it is a
*convenience view* of the provenance, and says so — the real proof is re-derivable from
each file's own bytes with no trust in this document.

Sellers drop the QR badge into a listing ("verify this photo"); buyers and marketplaces
scan straight into /verify. Monochrome, Helvetica + Courier: the same sans-for-claims,
mono-for-machine-truth split as the product UI.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

MUTED = 107           # grey for secondary text
VERIFIED = (59, 124, 61)    # the ColorChecker green the UI uses for "verified"
DANGER = (168, 52, 45)      # ColorChecker red — a failed/contradicted claim
CAUTION = (196, 146, 42)    # ColorChecker amber — inconclusive, needs a human
INK = (31, 31, 29)          # the near-black the design system calls foreground

_MUTED = MUTED              # retained: the module's own body reads better unprefixed
_VERIFIED = VERIFIED


def qr_png(url: str, *, box_size: int = 8) -> bytes:
    """A scannable PNG for `url` — ships in the pack as the listing badge."""
    import qrcode

    qr = qrcode.QRCode(border=2, box_size=box_size)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# Typographic characters that are NOT in latin-1 and would otherwise be replaced with "?"
# mid-sentence. Model-written text (verdicts, listing copy) is full of these, and a stray
# "?" in an evidence document reads as corruption. Transliterate before the lossy encode.
_TRANSLITERATE = str.maketrans({
    "—": "-", "–": "-", "−": "-",          # em/en dash, minus
    "‘": "'", "’": "'", "‚": ",",          # single quotes
    "“": '"', "”": '"', "„": '"',          # double quotes
    "…": "...", "•": "-", "→": "->",       # ellipsis, bullet, arrow
    "≥": ">=", "≤": "<=", "≠": "!=",
    " ": " ", " ": " ", " ": " ",          # non-breaking / thin spaces
    "⚠": "(!)", "✓": "OK", "✗": "X",
})


def latin(text: str) -> str:
    """fpdf core fonts are latin-1; degrade gracefully rather than crash on a title."""
    return (text or "").translate(_TRANSLITERATE).encode(
        "latin-1", errors="replace").decode("latin-1")


_latin = latin              # back-compat alias for this module's existing call sites


def draw_header(pdf, subtitle: str, *, accent: tuple[int, int, int] = VERIFIED) -> None:
    """The shared masthead: four-patch calibration glyph, wordmark, document kind.

    `accent` strikes the fourth patch, so a document's own verdict is legible from the
    glyph alone — green for a clean result, amber for inconclusive, red for a contradiction.
    """
    x0, y0, s, gap = 18, 16, 4.4, 1.4
    for i, (dx, dy) in enumerate([(0, 0), (1, 0), (0, 1), (1, 1)]):
        pdf.set_fill_color(*(accent if i == 3 else INK))
        pdf.rect(x0 + dx * (s + gap), y0 + dy * (s + gap), s, s, style="F")

    text_x = x0 + 2 * s + 3 * gap + 3
    pdf.set_xy(text_x, y0)
    pdf.set_font("helvetica", "B", 15)
    pdf.cell(0, 6, "OriginShot", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(text_x)
    pdf.set_font("helvetica", "", 8.5)
    pdf.set_text_color(MUTED, MUTED, MUTED)
    pdf.cell(0, 4, latin(subtitle), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)


def build_certificate(sku: dict, assets: list[dict], *, verify_base_url: str) -> bytes:
    """Render the one-page certificate PDF. Pure function of its inputs."""
    from fpdf import FPDF

    original = next((a for a in assets if a.get("is_authentic")), None)
    generated = [a for a in assets if not a.get("is_authentic") and a.get("sha256")]

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(18, 16, 18)

    draw_header(pdf, "Certificate of Provenance")

    # Product + issue facts.
    pdf.set_font("helvetica", "B", 12.5)
    pdf.cell(0, 6, _latin(sku.get("title") or "Product"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("courier", "", 8)
    pdf.set_text_color(_MUTED, _MUTED, _MUTED)
    issued = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 4.5, f"issued {issued}  ·  {len(generated)} generated asset(s)"
                     f"  ·  sku {sku.get('id', '')[:12]}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    def label(text: str) -> None:
        pdf.set_font("helvetica", "B", 7.5)
        pdf.set_text_color(_MUTED, _MUTED, _MUTED)
        pdf.cell(0, 4, text.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    def hash_line(sha: str) -> None:
        pdf.set_font("courier", "", 8)
        pdf.cell(0, 4, sha, new_x="LMARGIN", new_y="NEXT")

    # The anchor everything chains back to.
    if original:
        label("Authentic original - SHA-256 anchored on upload")
        hash_line(original.get("sha256") or "")
        pdf.ln(3)

    # Every generated asset, with its full hash — this page is evidence, not a summary.
    label("Generated assets")
    for a in generated:
        pdf.set_font("helvetica", "B", 8.5)
        style = (a.get("style") or "asset").capitalize()
        meta = " · ".join(x for x in [a.get("provider"), a.get("model")] if x)
        qa = a.get("qa")
        if qa:
            meta += f"  [QA {'passed' if qa.get('passed') else 'flagged'}]"
        pdf.cell(0, 4.5, _latin(f"{style}   {meta}"), new_x="LMARGIN", new_y="NEXT")
        hash_line(a.get("sha256") or "")
        pdf.ln(1)

    # Verify block + QR.
    pdf.ln(3)
    y = pdf.get_y()
    qr_target = f"{verify_base_url}/{original['sha256']}" if original else verify_base_url
    pdf.image(io.BytesIO(qr_png(qr_target)), x=18, y=y, w=30, h=30)

    pdf.set_xy(52, y + 1)
    pdf.set_font("helvetica", "B", 9)
    pdf.multi_cell(0, 4.5, "Verify any file yourself", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(52)
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(_MUTED, _MUTED, _MUTED)
    pdf.multi_cell(
        0, 4,
        "Scan the code (or open the URL below) to check the authentic original. Any hash "
        "on this page resolves the same way, and dropping the file itself into the "
        "verifier re-derives the proof from its bytes alone.",
    )
    pdf.set_x(52)
    pdf.set_font("courier", "", 7.5)
    pdf.multi_cell(0, 4, f"{verify_base_url}/<sha256>")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(max(pdf.get_y(), y + 33))

    # Honest footer: what this document is and is not.
    pdf.ln(4)
    pdf.set_draw_color(200, 200, 195)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(2.5)
    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(_MUTED, _MUTED, _MUTED)
    pdf.multi_cell(
        0, 3.8,
        "This certificate is a convenience view. The authoritative proof is embedded in "
        "the media files themselves (verified/ folder): each carries a manifest bound to "
        "its exact bytes, verifiable offline with no trust in this document or in "
        "OriginShot's servers. Generated assets are AI-generated and disclosed as such "
        "in disclosure.txt.",
    )

    return bytes(pdf.output())
