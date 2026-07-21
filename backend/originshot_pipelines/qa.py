"""Post-generation QA — the "evaluate" in generate → evaluate → retry → store.

Every generated image is scored before it becomes an asset, in two tiers:

  1. **Deterministic (Pillow)** — always runs, costs nothing, cannot be wrong about what it
     measures: minimum resolution for every style, plus border whiteness and product fill
     ratio for studio shots (the two things marketplaces actually reject main images for).
  2. **Vision-model fidelity** — `QA_VISION_MODEL` compares the generated image against the
     authentic original and scores "is this the same product?" 0–10. This is the check that
     catches the failure mode provenance alone can't: a beautiful image of a subtly
     *different* product.

The VLM tier is best-effort by contract: the endpoint 429s under load (observed live), so
any failure downgrades the report to deterministic-only rather than failing a run the
provider has already billed for. A report is attached to the asset either way — the UI
shows what was checked, not a bare green tick.

Thresholds are module constants, deliberately visible and few. They gate the *retry*
decision; they never delete output. A pack that fails QA twice still ships, flagged.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re

log = logging.getLogger("originshot.qa")

# ── Thresholds ────────────────────────────────────────────────────────
MIN_SHORT_SIDE = 512          # px; below this no marketplace accepts the file
WHITE_BORDER_MIN = 0.90       # fraction of border pixels that must read as white (studio)
FILL_MIN = 0.25               # product bbox area / frame area lower bound (studio)
FILL_MAX = 0.995              # upper bound — a full-bleed "studio" shot has no white bg
_WHITE_LUMA = 235             # 0–255 luminance above which a pixel counts as white
_BORDER_FRAC = 0.04           # border strip width as a fraction of each dimension
VLM_PASS_SCORE = 6            # 0–10; below this the product-match check fails
_VLM_MAX_EDGE = 512           # downscale images before sending to the VLM (token cost)


def evaluate_image(data: bytes, style: str, *, reference: bytes | None = None,
                   vlm_call=None) -> dict:
    """Score one generated image. Returns the QA report stored on the asset document.

    `vlm_call` is the injected VLM transport (`vlm_product_match` partially applied with
    config, or None to skip the tier) — injection keeps this module free of app config and
    makes the tests hermetic.
    """
    checks: list[dict] = []
    scorer = "deterministic"
    vlm_score = None
    vlm_verdict = None

    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGB")
            checks.append(_resolution_check(img))
            if style == "studio":
                checks.append(_white_border_check(img))
                checks.append(_fill_check(img))
    except Exception as exc:  # noqa: BLE001 — an undecodable image is itself a failure
        checks.append({
            "name": "decodable", "passed": False,
            "detail": f"image could not be decoded: {exc}",
        })

    if vlm_call is not None and reference is not None:
        try:
            vlm_score, vlm_verdict = vlm_call(reference, data)
            scorer = "deterministic+vlm"
            checks.append({
                "name": "product_match",
                "passed": vlm_score >= VLM_PASS_SCORE,
                "value": vlm_score,
                "threshold": VLM_PASS_SCORE,
                "detail": vlm_verdict,
            })
        except Exception as exc:  # noqa: BLE001 — VLM tier is best-effort by contract
            log.warning("VLM QA unavailable, deterministic-only: %s", exc)

    return {
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "scorer": scorer,
        "vlm_score": vlm_score,
        "vlm_verdict": vlm_verdict,
    }


# ── Feedback: turn a failed check into a prompt the next attempt can act on ──────────
# The point of the retry loop is not to roll the dice again — it is to tell the model
# *what was wrong*. Each failed check maps to a concrete, imperative instruction phrased in
# the model's own terms (background, framing, identity), so the retry is a correction rather
# than a coin flip. `{value}` and `{threshold}` are the measured numbers, quoted back so the
# instruction is specific ("was 0.62, needs ≥0.90") instead of vague.
_CHECK_GUIDANCE = {
    "white_background": (
        "the background was not pure white (measured {value}, needs ≥{threshold}): place the "
        "product on a pure #FFFFFF seamless studio background, with no gradient, prop or "
        "shadow reaching the edges of the frame"
    ),
    "product_fill": (
        "the product was poorly sized in the frame ({value}, target {threshold}): centre it "
        "and let it occupy a natural portion of the image — neither tiny nor cropped at the edges"
    ),
    "resolution": (
        "the output resolution was too low ({value}): render at a higher resolution"
    ),
    "product_match": (
        "the result did not clearly depict the SAME physical product (identity {value}/10): "
        "preserve the exact shape, proportions, colour, material and surface markings of the "
        "reference product — do not restyle, recolour, or substitute it"
    ),
    "decodable": "the output was not a valid image: produce a clean, decodable image",
}


def feedback_from_report(report: dict) -> str:
    """One actionable instruction per failed check in a single QA report."""
    parts: list[str] = []
    for c in report.get("checks", []):
        if c.get("passed"):
            continue
        tmpl = _CHECK_GUIDANCE.get(c.get("name"))
        if tmpl:
            parts.append(tmpl.format(value=c.get("value"), threshold=c.get("threshold")))
    return "; ".join(parts)


def feedback_from_reports(reports: list[dict]) -> str:
    """Aggregate feedback across a batch (e.g. the four lifestyle scenes), de-duplicated.

    A style is retried as a whole, so the guidance is the union of what went wrong across its
    assets — de-duplicated **by check** (the instruction for "background" is the same whether
    two scenes or four failed it), each named once in a stable order using the first failing
    occurrence's measured value. That keeps the retry prompt one coherent correction rather
    than the same instruction repeated with slightly different numbers.
    """
    by_check: dict[str, str] = {}
    for report in reports:
        if not report or report.get("passed"):
            continue
        for c in report.get("checks", []):
            name = c.get("name")
            if c.get("passed") or name in by_check:
                continue
            tmpl = _CHECK_GUIDANCE.get(name)
            if tmpl:
                by_check[name] = tmpl.format(value=c.get("value"), threshold=c.get("threshold"))
    return "; ".join(by_check.values())


def to_evaluation(report: dict):
    """Express a QA report as a Genblaze ``EvaluationResult`` — the SDK's agent vocabulary.

    This is what lets the generate → evaluate → refine loop read `.feedback` the same way
    `genblaze_core.agents.AgentLoop` does: our QA becomes a first-class SDK evaluator whose
    verdict carries the correction the next iteration should apply. Imported lazily so this
    module stays importable without the SDK (the deterministic tier and the hermetic tests
    need no Genblaze install).
    """
    from genblaze_core.agents import EvaluationResult

    vlm = report.get("vlm_score")
    return EvaluationResult(
        passed=bool(report.get("passed")),
        score=(vlm / 10.0) if vlm is not None else None,
        feedback=feedback_from_report(report) or None,
        metadata={"scorer": report.get("scorer"), "checks": report.get("checks", [])},
    )


def _resolution_check(img) -> dict:
    short = min(img.width, img.height)
    return {
        "name": "resolution",
        "passed": short >= MIN_SHORT_SIDE,
        "value": f"{img.width}x{img.height}",
        "threshold": f"short side >= {MIN_SHORT_SIDE}px",
    }


def _luma(px) -> float:
    r, g, b = px[0], px[1], px[2]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _white_border_check(img) -> dict:
    """Fraction of border-strip pixels that read as white (marketplace main-image rule)."""
    w, h = img.width, img.height
    bw = max(1, round(w * _BORDER_FRAC))
    bh = max(1, round(h * _BORDER_FRAC))
    px = img.load()
    total = white = 0
    for y in range(h):
        xs = range(w) if (y < bh or y >= h - bh) else list(range(bw)) + list(range(w - bw, w))
        for x in xs:
            total += 1
            if _luma(px[x, y]) >= _WHITE_LUMA:
                white += 1
    frac = white / total if total else 0.0
    return {
        "name": "white_background",
        "passed": frac >= WHITE_BORDER_MIN,
        "value": round(frac, 3),
        "threshold": WHITE_BORDER_MIN,
    }


def _fill_check(img) -> dict:
    """Product bounding-box area over frame area — is the product usably sized?

    Works on the non-white mask, so it is only meaningful for white-background styles.
    Downscales first: bbox at 1/8 resolution is within a pixel of the full-size answer.
    """
    from PIL import Image

    small = img.resize((max(1, img.width // 8), max(1, img.height // 8)), Image.BILINEAR)
    px = small.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(small.height):
        for x in range(small.width):
            if _luma(px[x, y]) < _WHITE_LUMA:
                xs.append(x)
                ys.append(y)
    if not xs:
        return {"name": "product_fill", "passed": False, "value": 0.0,
                "threshold": f"{FILL_MIN}-{FILL_MAX}", "detail": "no product found on canvas"}
    bbox_area = (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)
    frac = bbox_area / (small.width * small.height)
    return {
        "name": "product_fill",
        "passed": FILL_MIN <= frac <= FILL_MAX,
        "value": round(frac, 3),
        "threshold": f"{FILL_MIN}-{FILL_MAX}",
    }


# ── VLM transport ─────────────────────────────────────────────────────
_PROMPT = (
    "You are a product-photography QA checker. The FIRST image is an authentic reference "
    "photo of a product. The SECOND image is an AI-generated marketing shot that is "
    "supposed to show the SAME product. Score 0-10 how confident you are that it depicts "
    "the same physical product (shape, colour, material, markings). Staging, background, "
    "lighting and angle differences are fine and must not lower the score. "
    'Reply with ONLY this JSON: {"score": <0-10>, "verdict": "<one sentence>"}'
)


def _jpeg_b64(data: bytes) -> str:
    """Downscale + JPEG-encode for the VLM: fidelity scoring doesn't need full-res PNGs."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        edge = max(img.width, img.height)
        if edge > _VLM_MAX_EDGE:
            scale = _VLM_MAX_EDGE / edge
            img = img.resize((round(img.width * scale), round(img.height * scale)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def vlm_product_match(reference: bytes, candidate: bytes, *, api_key: str,
                      base_url: str, model: str, timeout: int = 60) -> tuple[int, str]:
    """One VLM call: does the generated image show the same product as the reference?

    Raises on any transport/parse problem — the caller downgrades to deterministic-only.
    """
    import httpx

    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 500,  # reasoning-model headroom: small budgets come back empty
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": _PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{_jpeg_b64(reference)}"}},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{_jpeg_b64(candidate)}"}},
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
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError(f"VLM returned no JSON: {content[:120]!r}")
    parsed = json.loads(match.group(0))
    score = max(0, min(10, int(parsed["score"])))
    return score, str(parsed.get("verdict") or "")[:300]
