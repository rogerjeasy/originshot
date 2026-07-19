"""Resolve — turning stored provenance into dispute evidence.

Everything else in OriginShot serves the seller *before* the sale. This module serves the
moment the README opens with: a buyer, a seller and a marketplace six months later, arguing
about whether the item that arrived is the item that was listed. The provenance is already
in the ledger; until now nothing *used* it when it mattered.

Resolve answers two questions in one pass, because a dispute is always both:

  1. **Was the listing image itself honest?** Re-derived from the file's own bytes — is the
     manifest intact, and does the media still match the hash it committed to? A listing
     photo that was retouched *after* OriginShot signed it is the strongest possible finding
     and needs no model to establish it.
  2. **Is the delivered item the listed item?** The vision tier compares the *authentic
     anchored original* — not the AI-generated marketing shot — against a photo of what
     actually arrived, and is asked to enumerate visible differences in condition. That
     framing is deliberate: the failure the README opens with is an AI silently removing a
     scratch, and the only way to catch it is to compare the arrival against the anchor the
     generated image descends from.

**On the word "signed".** These reports are *hash-anchored*, not cryptographically signed.
The PDF's own SHA-256 is recorded at issue time and is its identifier, so anyone holding a
copy can confirm it is the document this instance issued, unaltered. That is a real and
checkable property, and it is strictly weaker than a signature: it proves integrity against
a record we serve, not authorship against a key we hold. We say so on the document itself
rather than borrowing the stronger word. Issuing keypair → roadmap.

The received photo is **never stored** — only its SHA-256 goes in the report. The buyer keeps
the file; anyone can re-hash it to confirm it is the image that was compared. That is the same
trick the rest of the app runs on, applied to somebody else's private photo.
"""
from __future__ import annotations

import io
import json
import logging
import re
from datetime import datetime, timezone
from enum import Enum

log = logging.getLogger("originshot.resolve")

# ── Thresholds ────────────────────────────────────────────────────────
# Deliberately wider apart than QA's single pass mark: a dispute report that says
# "inconclusive" is useful, and a confidently wrong one is worse than useless.
MATCH_PASS = 7          # >= this ⇒ the arrival is consistent with the anchor
MATCH_FAIL = 3          # <  this ⇒ the arrival contradicts the anchor
_VLM_MAX_EDGE = 640     # received photos are phone-camera sized; keep more detail than QA
_MAX_DIFFERENCES = 6


class Finding(str, Enum):
    """The report's verdict. Ordered by how urgently a human should look at it."""
    listing_tampered = "listing_tampered"       # the listing image's own bytes were altered
    item_mismatch = "item_mismatch"             # arrival contradicts the anchored original
    condition_differences = "condition_differences"   # right product, visible damage/wear
    inconclusive = "inconclusive"               # compared, but the evidence doesn't decide
    no_provenance = "no_provenance"             # listing image carries no verifiable record
    provenance_only = "provenance_only"         # provenance checked; no comparison was run
    consistent = "consistent"                   # everything checked agrees


SEVERITY = {
    Finding.listing_tampered: "critical",
    Finding.item_mismatch: "critical",
    Finding.condition_differences: "warning",
    Finding.inconclusive: "warning",
    Finding.no_provenance: "warning",
    Finding.provenance_only: "info",
    Finding.consistent: "ok",
}

_HEADLINES = {
    Finding.listing_tampered: "The listing image was altered after it was signed",
    Finding.item_mismatch: "The delivered item does not match the listed product",
    Finding.condition_differences:
        "The right product, but the delivered item differs in condition",
    Finding.inconclusive: "The comparison did not settle the question",
    Finding.no_provenance: "The listing image carries no verifiable provenance",
    Finding.provenance_only: "Provenance verified; no delivered-item comparison was run",
    Finding.consistent: "The evidence is consistent with the listing",
}


def assess(*, listing: dict, match: dict | None) -> dict:
    """Combine the provenance verdict and the item comparison into one finding.

    Pure function — no I/O, no config. `listing` is the shape produced by
    `app/api/resolve.py::_inspect_listing`; `match` is `vlm_item_match`'s result or None.
    """
    present = bool(listing.get("present"))
    found = bool(listing.get("found"))
    content_bound = listing.get("content_bound")
    score = (match or {}).get("score")

    if content_bound is False:
        finding = Finding.listing_tampered
        detail = (
            "The file carries an intact OriginShot manifest, but its media no longer matches "
            "the content hash that manifest committed to. Someone edited the image after it "
            "was generated and signed. Whatever the delivered item looks like, the listing "
            "image is not the file OriginShot produced."
        )
    elif not present and not found:
        finding = Finding.no_provenance
        detail = (
            "No embedded manifest and no matching record in this ledger. This image was not "
            "produced or anchored by OriginShot, so nothing here can confirm or contradict "
            "how it was made. That is not itself evidence of wrongdoing — most images on the "
            "internet are in this state — but it means the listing photo cannot be relied on "
            "as a reference point in this dispute."
        )
    elif score is None:
        finding = Finding.provenance_only
        detail = (
            "The listing image's provenance was re-derived from its own bytes and holds. No "
            "photo of the delivered item was compared"
            + (f" ({match['unavailable']})." if match and match.get("unavailable") else ".")
        )
    elif score >= MATCH_PASS and (match or {}).get("differences"):
        # The most common real dispute is not "wrong item" — it is "right item, arrived
        # damaged". A high same-product score with defects logged must NOT return a green
        # pass: that is the exact case the buyer is complaining about, and reporting it as
        # "consistent" would use this document against the person it was issued for.
        finding = Finding.condition_differences
        detail = (
            "The listing image's provenance holds and the delivered item is the same physical "
            "product as the authentic original — but visible differences in condition or "
            "completeness were identified, and they are listed below. This report does not "
            "establish when or how those differences arose: they may predate the sale, have "
            "occurred in transit, or be artefacts of the photograph. What it does establish "
            "is that they are not present in the anchored original the listing was built from."
        )
    elif score >= MATCH_PASS:
        finding = Finding.consistent
        detail = (
            "The listing image's provenance holds, and the delivered item is consistent with "
            "the authentic original the listing photos were generated from, with no visible "
            "differences in condition identified. Note what this does and does not establish: "
            "it is a visual judgement about the same physical product, not an assessment of "
            "completeness or working order."
        )
    elif score < MATCH_FAIL:
        finding = Finding.item_mismatch
        detail = (
            "The listing image's provenance holds, but the photo of the delivered item does "
            "not depict the same physical product as the authentic original the listing was "
            "built from. The listing photos are honest about their own making; the question "
            "this raises is what was shipped."
        )
    else:
        finding = Finding.inconclusive
        detail = (
            "The listing image's provenance holds. The delivered-item comparison landed "
            "between the thresholds — consistent with heavy wear, a different configuration, "
            "or simply a poor photo, and not sufficient to call either way. A human should "
            "look at both images."
        )

    return {
        "finding": finding.value,
        "severity": SEVERITY[finding],
        "headline": _HEADLINES[finding],
        "detail": detail,
    }


# ── Vision comparison ─────────────────────────────────────────────────
_PROMPT = (
    "You are examining evidence in an online-marketplace dispute. The FIRST image is the "
    "seller's authentic reference photo of the product, anchored before any AI processing. "
    "The SECOND image is a photo of the item the buyer actually received.\n\n"
    "Decide how confident you are that BOTH images show the same physical product. Score "
    "0-10. Photography differences — lighting, background, angle, focus, phone camera "
    "quality, the item being held or unboxed — are expected and must NOT lower the score. "
    "Only genuine differences in the product itself lower it: shape, proportions, colour, "
    "material, branding, markings, included parts.\n\n"
    "Separately, list any visible differences in CONDITION or COMPLETENESS: scratches, "
    "dents, cracks, wear, discolouration, missing or extra components. Report these even "
    "when the score is high — a correct item in damaged condition is the most common real "
    "dispute. Describe only what you can actually see; if you see none, return an empty "
    "list. Do not speculate about causes.\n\n"
    'Reply with ONLY this JSON: {"score": <0-10>, "verdict": "<one sentence>", '
    '"differences": ["<short phrase>", ...]}'
)


def _jpeg_b64(data: bytes) -> str:
    """Downscale + JPEG-encode for the VLM. Larger edge than QA: condition differences are
    small features, and a scratch that survives the resize is the whole point."""
    import base64

    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        edge = max(img.width, img.height)
        if edge > _VLM_MAX_EDGE:
            scale = _VLM_MAX_EDGE / edge
            img = img.resize((round(img.width * scale), round(img.height * scale)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def vlm_item_match(anchor: bytes, received: bytes, *, api_key: str, base_url: str,
                   model: str, timeout: int = 90) -> dict:
    """One VLM call: is the received item the anchored product, and how does it differ?

    Returns ``{score, verdict, differences[], model}``. Raises on any transport or contract
    problem — the caller reports the comparison as unavailable rather than inventing one.
    """
    import httpx

    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 700,   # room for the differences list; small budgets come back empty
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": _PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{_jpeg_b64(anchor)}"}},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{_jpeg_b64(received)}"}},
            ],
        }],
    }
    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=body,
        timeout=timeout,
    )
    resp.raise_for_status()
    content = (resp.json()["choices"][0]["message"].get("content") or "").strip()
    found = re.search(r"\{.*\}", content, re.DOTALL)
    if not found:
        raise ValueError(f"comparison model returned no JSON: {content[:160]!r}")
    parsed = json.loads(found.group(0))

    raw_diffs = parsed.get("differences") or []
    if isinstance(raw_diffs, str):          # models occasionally collapse the list to prose
        raw_diffs = [raw_diffs]
    differences = [str(d)[:200] for d in raw_diffs if str(d).strip()][:_MAX_DIFFERENCES]

    return {
        "score": max(0, min(10, int(parsed["score"]))),
        "verdict": str(parsed.get("verdict") or "")[:400],
        "differences": differences,
        "model": model,
    }


# ── The report document ───────────────────────────────────────────────
def _listing_lines(listing: dict) -> list[tuple[str, str]]:
    """How the listing image's status reads on the page.

    Written as a table rather than inline because the honest wording depends on *what kind*
    of file it is. An authentic upload has no embedded manifest by design — it is anchored by
    hash at the moment of receipt — so printing "manifest: absent / integrity: verified"
    next to each other, as an earlier draft did, states a contradiction and implies the
    verification was stronger than it was.
    """
    authentic = bool(listing.get("is_authentic"))
    present = bool(listing.get("present"))
    found = bool(listing.get("found"))

    if authentic:
        kind = "authentic original - anchored by SHA-256 on upload, carries no manifest"
        integrity = ("confirmed - these bytes hash to the anchored value" if found
                     else "no anchor on record in this instance")
    elif present:
        kind = "AI-generated - embedded provenance manifest present"
        integrity = ("verified - the manifest is internally intact" if listing.get("verified")
                     else "NOT VERIFIED - the manifest failed its own integrity check")
    elif found:
        kind = "no embedded manifest, but these bytes match a ledger record"
        integrity = "confirmed by byte-exact match to the stored record"
    else:
        kind = "unknown - no embedded manifest and no ledger record"
        integrity = "no basis on which to verify"

    binding = {
        True: "bound - the media matches the hash committed for it",
        False: "BROKEN - the media no longer matches its committed hash",
        None: ("not applicable - nothing was committed for these bytes" if not present
               else "not determinable for this file format"),
    }[listing.get("content_bound")]

    return [
        ("File", kind),
        ("Integrity", integrity),
        ("Content binding", binding),
        ("Ledger record", "found" if found else "none in this instance"),
    ]


def build_dispute_report(report: dict, *, verify_base_url: str,
                         report_base_url: str | None = None) -> bytes:
    """Render the Dispute Evidence Report PDF. Pure function of its inputs.

    `report` is the assembled record (see `app/api/resolve.py`): id, issued_at, finding
    block, listing block, anchor block, received block, match block.
    """
    from fpdf import FPDF

    from .certificate import (CAUTION, DANGER, MUTED, VERIFIED, draw_header, latin, qr_png)

    accent = {"ok": VERIFIED, "info": (MUTED, MUTED, MUTED),
              "warning": CAUTION, "critical": DANGER}[report["severity"]]

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(18, 16, 18)
    draw_header(pdf, "Dispute Evidence Report", accent=accent)

    def label(text: str) -> None:
        pdf.set_font("helvetica", "B", 7.5)
        pdf.set_text_color(MUTED, MUTED, MUTED)
        pdf.cell(0, 4, latin(text).upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    def mono(text: str, size: float = 8) -> None:
        pdf.set_font("courier", "", size)
        pdf.cell(0, 4, latin(text), new_x="LMARGIN", new_y="NEXT")

    def body(text: str, size: float = 8.5) -> None:
        # new_x=LMARGIN is load-bearing, not cosmetic: fpdf2 leaves the cursor at the RIGHT
        # edge of a multi_cell, so a following full-width call computes w=0 and raises
        # "Not enough horizontal space to render a single character".
        pdf.set_font("helvetica", "", size)
        pdf.multi_cell(0, 4.2, latin(text), new_x="LMARGIN", new_y="NEXT")

    # ── Verdict, stated first and in plain language ──
    pdf.set_fill_color(*accent)
    pdf.rect(18, pdf.get_y(), 174, 0.9, style="F")
    pdf.ln(3)
    pdf.set_font("helvetica", "B", 13)
    pdf.multi_cell(0, 5.6, latin(report["headline"]))
    pdf.ln(1)
    pdf.set_font("courier", "", 7.5)
    pdf.set_text_color(MUTED, MUTED, MUTED)
    pdf.cell(0, 4, latin(f"finding: {report['finding']}  ·  severity: {report['severity']}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2.5)
    body(report["detail"])
    pdf.ln(4)

    # ── The listing image ──
    listing = report["listing"]
    label("Listing image - re-derived from the file's own bytes")
    mono(listing.get("sha256") or "(supplied by hash lookup only)")
    pdf.set_font("helvetica", "", 8.5)
    for name, value in _listing_lines(listing):
        pdf.cell(0, 4.2, latin(f"    {name}: {value}"), new_x="LMARGIN", new_y="NEXT")
    if listing.get("model"):
        pdf.cell(0, 4.2, latin(f"    Generated by: {listing.get('model')} "
                               f"({listing.get('provider') or 'provider'})"),
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ── The anchor ──
    anchor = report.get("anchor") or {}
    if anchor.get("sha256"):
        label("Authentic original - anchored on upload, before any AI processing")
        mono(anchor["sha256"])
        pdf.set_font("helvetica", "", 8.5)
        if anchor.get("created_at"):
            pdf.cell(0, 4.2, latin(f"    Anchored: {anchor['created_at']}"),
                     new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 4.2, "    This is the reference the delivered item was compared against.",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # ── The received item ──
    received = report.get("received") or {}
    if received.get("sha256"):
        label("Photo of the delivered item - as submitted, not retained")
        mono(received["sha256"])
        pdf.set_font("helvetica", "", 8.5)
        pdf.multi_cell(0, 4.2, latin(
            "    OriginShot does not store this photo. Whoever submitted it still holds the "
            "file; re-hashing it reproduces the value above, which is what ties this report "
            "to that specific image."), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # ── The comparison ──
    match = report.get("match")
    label("Delivered-item comparison")
    if match:
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 5.5, latin(f"{match['score']} / 10  same physical product"),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("courier", "", 7.5)
        pdf.set_text_color(MUTED, MUTED, MUTED)
        pdf.cell(0, 4, latin(f"model: {match.get('model', 'unknown')}  ·  "
                             f"consistent >= {MATCH_PASS}  ·  contradicts < {MATCH_FAIL}"),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1.5)
        if match.get("verdict"):
            body(match["verdict"])
        if match.get("differences"):
            pdf.ln(1.5)
            label("Visible differences in condition or completeness")
            pdf.set_font("helvetica", "", 8.5)
            for diff in match["differences"]:
                pdf.multi_cell(0, 4.2, latin(f"    - {diff}"),
                               new_x="LMARGIN", new_y="NEXT")
    else:
        body(report.get("match_unavailable")
             or "No photo of the delivered item was submitted, so no comparison was run.")
    pdf.ln(4)

    # ── Verify block + QR ──
    y = pdf.get_y()
    qr_target = (f"{report_base_url}/{report['id']}" if report_base_url
                 else f"{verify_base_url}/{listing.get('sha256') or ''}")
    pdf.image(io.BytesIO(qr_png(qr_target)), x=18, y=y, w=28, h=28)
    pdf.set_xy(50, y + 1)
    pdf.set_font("helvetica", "B", 9)
    pdf.multi_cell(0, 4.5, "Check this report yourself", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(50)
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(MUTED, MUTED, MUTED)
    pdf.multi_cell(0, 4, latin(
        "Scan the code to open this report on the issuing instance. Every hash above resolves "
        "at the public verifier, and dropping the listing file itself into the verifier "
        "re-derives the provenance finding from its bytes alone - independently of this "
        "document and of anything OriginShot stores."))
    pdf.set_x(50)
    pdf.set_font("courier", "", 7.5)
    pdf.multi_cell(0, 4, latin(qr_target))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(max(pdf.get_y(), y + 31))

    # ── Standing of the document ──
    pdf.ln(3)
    pdf.set_draw_color(200, 200, 195)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(2.5)
    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(MUTED, MUTED, MUTED)
    pdf.multi_cell(0, 3.8, latin(
        f"Issued {report['issued_at']} · report {report['id']}. This report is hash-anchored, "
        "not cryptographically signed: this instance recorded the SHA-256 of the PDF it "
        "issued, so a copy can be confirmed unaltered against that record. It is not proof of "
        "authorship. The provenance findings are re-derived from file bytes and are "
        "reproducible by anyone. The delivered-item comparison is a vision-model judgement — "
        "it is evidence for a human decision, not a determination of fault, and it does not "
        "assess condition, authenticity of brand, or working order beyond what is visible in "
        "the two photographs supplied."))

    return bytes(pdf.output())


def issued_at_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
