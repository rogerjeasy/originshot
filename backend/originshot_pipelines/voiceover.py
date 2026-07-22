"""Product voiceover: listing facts → narration script → spoken audio (OpenAI TTS).

This is the app's **audio modality**, and it exists by a *provider swap*, not a workaround.
GMI's TTS/music models are unreachable through ``genblaze-gmicloud`` 0.3.3 — the
``param_allowlist`` strips the ``text``/``lyrics`` the API requires (documented, and filed, in
``docs/genblaze-issues/04``). Rather than fake audio or cut the feature, the voiceover routes
to **OpenAI TTS through Genblaze's unified provider API** — the very same cross-provider
portability that lets image generation fall from GMI to OpenAI when GMI's request queue runs
out of credit (``providers.py``). One authentic photo already becomes a studio image and a
hero video; the narration adds spoken audio, so a single provenance chain now spans text,
image, video **and** audio.

Two decisions carry the feature:

* **The script is AI-written, and says so.** The narration text is produced by the same chat
  model that writes listing copy (GMI ``GLM``); when that endpoint 429s the script falls back
  to a deterministic template so the audio still renders — the same "never hard-depend on
  chat" rule the QA and listing tiers already follow. :func:`narration_script` returns the
  text *and* how it was produced, so the manifest can disclose an AI-written script rather
  than pass it off as human copy.
* **The narration carries its own provenance.** The TTS output flows through the ordinary
  generation ``_map`` path (``app/generation.py``): the manifest embeds into the MP3 (ID3, via
  genblaze-core's ``Mp3Handler`` + ``mutagen``), the bytes are stored content-addressably on
  B2, and the asset gets a transparency-log entry like every other. ``content_bound`` is
  ``None`` for audio — the strip-and-rehash canonical hash covers PNG/MP4/JPEG/WebP, not audio
  — which is stated honestly wherever the audio result is shown; the muxed narrated *video*
  (MP4) does get full content-binding.

Live-verified 2026-07-22 against our own key: ``tts-1`` → 262 KB MP3 in 3.7s,
``gpt-4o-mini-tts`` → 250 KB MP3 in 7.0s, both complete valid MPEG audio; embedded manifest
round-trips to ``present + verified``.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .registry import (
    VOICEOVER_FORMAT,
    VOICEOVER_MODEL,
    VOICEOVER_VOICE,
)

log = logging.getLogger("originshot.voiceover")

# Default delivery direction for models that accept it (the gpt-*-tts family). tts-1/tts-1-hd
# reject an `instructions` param, so it is only sent when the model supports it — see
# `_supports_instructions`.
DEFAULT_INSTRUCTIONS = (
    "Read as a warm, premium product narrator: unhurried, confident and natural, "
    "as if introducing a piece you're proud of. No hard-sell energy."
)

# A narration read aloud over a ~5s hero video wants to be short. This bounds both the script
# prompt and the deterministic fallback, and is enforced in code (the model is asked, not
# trusted) so a chatty model can't produce a 30-second monologue over a 5-second clip.
MAX_SCRIPT_WORDS = 55


# ── Narration script ──────────────────────────────────────────────────
def _clean_desc(sku: dict) -> str:
    return (sku.get("description") or sku.get("title") or "this product").strip()


def _fallback_script(sku: dict) -> str:
    """A deterministic spoken script from the SKU's own facts — no model involved.

    Used when no chat key is configured or the chat endpoint fails. Deliberately plain and
    honest: it states what the seller stated, adds no claim of its own, and stays inside
    :data:`MAX_SCRIPT_WORDS`. A generic-but-true narration beats a failed style.
    """
    title = (sku.get("title") or "This product").strip()
    desc = (sku.get("description") or "").strip()
    category = (sku.get("category") or "").strip()
    lead = title if title.lower() != "untitled product" else "This product"
    parts = [f"{lead}."]
    if desc:
        # First sentence of the seller's own description, trimmed.
        first = re.split(r"(?<=[.!?])\s+", desc)[0].strip()
        if first:
            parts.append(first if first.endswith((".", "!", "?")) else first + ".")
    elif category:
        parts.append(f"A {category} made to last.")
    parts.append("Every frame verifiable — provenance you can check.")
    return _trim_words(" ".join(parts))


def _trim_words(text: str) -> str:
    """Collapse whitespace and cap at MAX_SCRIPT_WORDS without cutting mid-sentence oddly."""
    words = re.sub(r"\s+", " ", (text or "").strip()).split(" ")
    if len(words) <= MAX_SCRIPT_WORDS:
        return " ".join(words)
    clipped = " ".join(words[:MAX_SCRIPT_WORDS]).rstrip(",;: ")
    return clipped if clipped.endswith((".", "!", "?")) else clipped + "."


def _build_script_prompt(sku: dict, brand: dict | None) -> str:
    facts = [f"Product: {sku.get('title') or 'Untitled product'}"]
    if sku.get("category"):
        facts.append(f"Category: {sku['category']}")
    if sku.get("description"):
        facts.append(f"Seller's description: {sku['description']}")
    if brand:
        tone = "; ".join(str(brand[k]).strip() for k in ("vibe", "lighting")
                         if brand.get(k))
        if tone:
            facts.append(f"Brand tone: {tone}")
    return (
        "Write a short spoken narration for a product video. Use ONLY the facts below — "
        "never invent materials, dimensions, or claims not stated.\n\n"
        + "\n".join(facts)
        + f"\n\nConstraints: at most {MAX_SCRIPT_WORDS} words; plain sentences a narrator "
        "reads aloud; warm and premium; no marketing clichés (no 'introducing', 'elevate', "
        "'unleash', 'game-changer'); no hashtags, no emoji, no stage directions. "
        "Reply with ONLY the narration text, nothing else."
    )


def _strip_wrapping_quotes(text: str) -> str:
    t = (text or "").strip()
    if len(t) >= 2 and t[0] in "\"'" and t[-1] in "\"'":
        t = t[1:-1].strip()
    return t


def narration_script(
    sku: dict,
    brand: dict | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout: int = 60,
) -> tuple[str, dict]:
    """Return ``(script_text, provenance)`` for the product-video narration.

    ``provenance`` is ``{"source": "model"|"template", "model": <id or None>}`` so the caller
    can record — in the asset and the manifest — that the *script itself* was AI-written (or
    templated), rather than presenting generated words as human copy.

    The chat path mirrors ``listing.generate_listing`` exactly (same GMI OpenAI-compatible
    endpoint, same "treat failure as try-again, never a broken SKU" contract). Any failure —
    no key, transport error, empty completion — falls back to :func:`_fallback_script` so the
    voiceover still produces audio.
    """
    if not api_key:
        return _fallback_script(sku), {"source": "template", "model": None}

    import httpx

    from .registry import GMI_CHAT_BASE_URL, VOICEOVER_SCRIPT_MODEL

    model = model or VOICEOVER_SCRIPT_MODEL
    base_url = base_url or GMI_CHAT_BASE_URL
    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": 0.5,
                "max_tokens": 800,  # a short script + reasoning-model headroom
                "messages": [{"role": "user", "content": _build_script_prompt(sku, brand)}],
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        content = (resp.json()["choices"][0]["message"].get("content") or "").strip()
        content = _strip_wrapping_quotes(content)
        if not content:
            raise ValueError("script model returned empty content")
        return _trim_words(content), {"source": "model", "model": model}
    except Exception as e:  # noqa: BLE001 — chat is best-effort; template keeps audio alive
        log.warning("narration script model failed (%s); using deterministic fallback", e)
        return _fallback_script(sku), {"source": "template", "model": None}


# ── OpenAI TTS provider (with the issue-05 Windows file:// fix) ─────────
def _fix_file_uri(url: str | None) -> str | None:
    """Rebuild a provider ``file://`` URL with ``Path.as_uri()``; None if not fixable.

    ``genblaze_openai``'s TTS provider builds every output URL as ``f"file://{quote(path)}"``
    (tts.py). On POSIX that is correct (``file:///tmp/x.mp3``); on Windows the path has no
    leading slash, so the whole path lands in the URL's **netloc** and ``ObjectStorageSink``
    then cannot upload it — the exact defect filed as genblaze issue 05 for the image provider,
    which reappears here because TTS constructs the URL the same way.

    ``Path.as_uri()`` is the stdlib spelling and is byte-identical on POSIX, so this is a no-op
    on Render (Linux) and only repairs local Windows development. Reconstructing the path from
    ``netloc + path`` (unquoted) handles both shapes; if the file isn't there we leave the URL
    untouched rather than guess.
    """
    if not url or not url.startswith("file://"):
        return None
    from urllib.parse import unquote, urlparse

    parsed = urlparse(url)
    candidate = Path(unquote(parsed.netloc + parsed.path))
    if not candidate.exists():
        return None
    return candidate.resolve().as_uri()


def _make_tts_provider(api_key: str | None, output_dir: str | None = None):
    """``OpenAITTSProvider`` with output URLs repaired for Windows (genblaze issue 05).

    Subclassed rather than monkeypatched so the change is scoped to the provider *this app*
    constructs, mirroring ``providers._make_openai_provider`` for the image path.
    """
    from genblaze_openai import OpenAITTSProvider

    class _OriginShotTTSProvider(OpenAITTSProvider):
        def generate(self, step, config=None):
            step = super().generate(step, config)
            for asset in getattr(step, "assets", []):
                fixed = _fix_file_uri(getattr(asset, "url", None))
                if fixed:
                    asset.url = fixed
            return step

    return _OriginShotTTSProvider(api_key=api_key, output_dir=output_dir)


def _supports_instructions(model: str) -> bool:
    """Only the gpt-*-tts family accepts an `instructions` delivery-tone param; tts-1 rejects it."""
    return model.startswith("gpt-") and model.endswith("-tts")


# ── Pipeline ───────────────────────────────────────────────────────────
def voiceover_step_kwargs(
    script: str,
    *,
    model: str | None = None,
    voice: str | None = None,
    instructions: str | None = DEFAULT_INSTRUCTIONS,
) -> dict:
    """The kwargs for ``Pipeline.step(tts_provider, **kwargs)`` — split out so it is testable
    without a live provider (mirroring ``providers.ImageAdapter.build_kwargs``).

    ``instructions`` (delivery tone) is only included for models that accept it; tts-1/tts-1-hd
    reject the param, so sending it would 400 an otherwise-valid request.
    """
    from genblaze_core import Modality

    model = model or VOICEOVER_MODEL
    voice = voice or VOICEOVER_VOICE
    kwargs: dict = {
        "model": model,
        "prompt": script,
        "modality": Modality.AUDIO,
        "voice": voice,
        "response_format": VOICEOVER_FORMAT,
    }
    if instructions and _supports_instructions(model):
        kwargs["instructions"] = instructions
    return kwargs


def build_voiceover_pipeline(
    script: str,
    *,
    provider=None,
    api_key: str | None = None,
    model: str | None = None,
    voice: str | None = None,
    instructions: str | None = DEFAULT_INSTRUCTIONS,
    output_dir: str | None = None,
):
    """A one-step Genblaze Pipeline that renders ``script`` to speech on OpenAI TTS.

    ``provider`` may be injected for tests; otherwise the app's Windows-safe TTS provider is
    constructed.
    """
    from genblaze_core import Pipeline

    provider = provider if provider is not None else _make_tts_provider(api_key, output_dir)
    kwargs = voiceover_step_kwargs(script, model=model, voice=voice, instructions=instructions)
    return Pipeline("originshot-voiceover").step(provider, **kwargs)


async def run_voiceover(
    script: str,
    *,
    sink,
    timeout: int,
    provider=None,
    api_key: str | None = None,
    model: str | None = None,
    voice: str | None = None,
    instructions: str | None = DEFAULT_INSTRUCTIONS,
):
    """Render ``script`` to speech and store it via ``sink`` (B2). Returns the PipelineResult."""
    pipeline = build_voiceover_pipeline(
        script, provider=provider, api_key=api_key, model=model, voice=voice,
        instructions=instructions,
    )
    return await pipeline.arun(sink=sink, timeout=timeout)


# ── Narrated video: mux the narration onto the hero video (content-bound MP4) ──
# The mux is the payoff — a product video that talks — and, because the muxed container is an
# MP4, it is the audio path's one asset that DOES get full content-binding (the strip-and-
# rehash canonical hash covers MP4; standalone audio does not). It runs through the SDK's
# FFmpegCompositor in a real Genblaze pipeline, so the result carries a manifest and flows
# through the ordinary generation `_map` path like every other asset.
#
# ffmpeg is optional. If neither a system ffmpeg nor the bundled `imageio-ffmpeg` binary is
# present, the mux is skipped and the standalone narration audio still ships — the same
# graceful-degradation contract the rest of the app follows. `imageio-ffmpeg` bundles a static
# binary cross-platform, so shipping it as a dependency makes the mux work on Render without
# apt-installing ffmpeg into the image.

# Loop the hero video to this many seconds before muxing. It only needs to exceed any plausible
# narration (MAX_SCRIPT_WORDS ≈ 30s of speech at the outside); the compositor's `-shortest`
# then trims the output to the audio's true length, so the exact value never needs probing.
LOOP_CEILING_SECONDS = 60


def ffmpeg_binary() -> str | None:
    """A usable ffmpeg path: a system one on PATH, else the bundled imageio-ffmpeg binary.

    None ⇒ no ffmpeg available, so the narrated-video mux is skipped (audio still ships).
    """
    import shutil

    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 — treat an unimportable/absent binary as "no ffmpeg"
        return None


def loop_video_to_ceiling(video_path: Path, out_path: Path, *, ffmpeg: str,
                          seconds: int = LOOP_CEILING_SECONDS, timeout: int = 120) -> None:
    """Stream-copy `video_path` looped to `seconds` (no re-encode). The mux `-shortest`s it back
    down to the narration length, so this just guarantees the video never runs out first."""
    import subprocess

    subprocess.run(
        [ffmpeg, "-y", "-stream_loop", "-1", "-i", str(video_path),
         "-t", str(seconds), "-c", "copy", str(out_path)],
        check=True, capture_output=True, timeout=timeout,
    )


def _make_compositor(ffmpeg: str, output_dir: str | None):
    """``FFmpegCompositor`` with the issue-05 Windows output-URL repaired (as for TTS/DALL·E)."""
    from genblaze_core.providers.compositor import FFmpegCompositor

    class _OriginShotCompositor(FFmpegCompositor):
        def generate(self, step, config=None):
            step = super().generate(step, config)
            for asset in getattr(step, "assets", []):
                fixed = _fix_file_uri(getattr(asset, "url", None))
                if fixed:
                    asset.url = fixed
            return step

    return _OriginShotCompositor(ffmpeg_path=ffmpeg, output_dir=output_dir)


def build_narrated_pipeline(looped_video_uri: str, audio_uri: str, *, ffmpeg: str,
                            output_dir: str | None = None,
                            video_sha256: str | None = None, audio_sha256: str | None = None):
    """A one-step compositor Pipeline that muxes `audio_uri` onto `looped_video_uri`.

    Passing the input hashes lets the SDK record real input lineage and keeps the manifest's
    canonical hash stable (the compositor warns loudly otherwise).
    """
    from genblaze_core import Modality, Pipeline
    from genblaze_core.models.asset import Asset

    video_in = Asset(url=looped_video_uri, media_type="video/mp4", sha256=video_sha256)
    audio_in = Asset(url=audio_uri, media_type="audio/mpeg", sha256=audio_sha256)
    return Pipeline("originshot-narrated-video").step(
        _make_compositor(ffmpeg, output_dir),
        model="ffmpeg-mux",           # the compositor has no model; the step API requires one
        modality=Modality.VIDEO,
        external_inputs=[video_in, audio_in],
    )
