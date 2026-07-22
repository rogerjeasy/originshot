"""Voiceover: narration script + OpenAI TTS wiring (originshot_pipelines/voiceover.py).

The failures these guard against are the ones that would quietly undermine the feature's
claims:

  * a script that invents a product claim (the audio must state only what the seller stated);
  * a chat outage that fails the whole style instead of degrading to a deterministic script;
  * an `instructions` param sent to tts-1, which 400s a request that would otherwise work;
  * the issue-05 Windows `file://` URL that makes the sink unable to upload the audio to B2;
  * an unpriced TTS step (Step.cost_usd is None) settling as free and refunding the hold;
  * audio being misclassified as an image because modality was decided by style alone.

None of these raise on their own. Each is asserted here rather than left to a live run.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlparse

import pytest

from originshot_pipelines import voiceover as vo

SKU = {
    "id": "sku1",
    "title": "Handmade Ceramic Mug",
    "category": "kitchen",
    "description": "A two-tone glazed stoneware mug. Holds 350ml. Dishwasher safe.",
}


# ── Narration script ──────────────────────────────────────────────────
def test_script_falls_back_to_template_without_a_key():
    """No chat key ⇒ a deterministic script from the SKU's own facts, honestly labelled."""
    script, prov = vo.narration_script(SKU, api_key=None)
    assert script.strip()
    assert prov == {"source": "template", "model": None}
    # Uses the seller's stated facts, invents nothing external.
    assert "Handmade Ceramic Mug" in script
    assert len(script.split()) <= vo.MAX_SCRIPT_WORDS


def test_script_uses_the_chat_model_when_available(monkeypatch):
    """With a key, the listing/chat model writes the script and provenance says `model`."""
    import httpx

    class _Resp:
        def raise_for_status(self):  # noqa: D401
            return None

        def json(self):
            return {"choices": [{"message": {"content": "A quiet, well-made mug for slow mornings."}}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    script, prov = vo.narration_script(SKU, api_key="gmi-test", model="zai-org/GLM-5.1-FP8")
    assert script == "A quiet, well-made mug for slow mornings."
    assert prov == {"source": "model", "model": "zai-org/GLM-5.1-FP8"}


def test_script_falls_back_when_the_model_fails(monkeypatch):
    """A chat 429/timeout must degrade to a template, never fail the style."""
    import httpx

    def _boom(*a, **k):
        raise httpx.HTTPError("all endpoints overloaded")

    monkeypatch.setattr(httpx, "post", _boom)
    script, prov = vo.narration_script(SKU, api_key="gmi-test")
    assert script.strip()
    assert prov["source"] == "template"


def test_script_caps_word_count(monkeypatch):
    """A chatty model can't produce a 200-word monologue over a 5-second clip."""
    import httpx

    long_text = " ".join(["word"] * 200) + "."

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": long_text}}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    script, _ = vo.narration_script(SKU, api_key="gmi-test")
    assert len(script.split()) <= vo.MAX_SCRIPT_WORDS


def test_script_strips_wrapping_quotes(monkeypatch):
    """Models love to wrap the answer in quotes; a narrator shouldn't read them aloud."""
    import httpx

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '"Just the words, please."'}}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    script, _ = vo.narration_script(SKU, api_key="gmi-test")
    assert script == "Just the words, please."


def test_empty_model_content_falls_back(monkeypatch):
    """An empty completion is a failure, not a valid (silent) script."""
    import httpx

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "   "}}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    script, prov = vo.narration_script(SKU, api_key="gmi-test")
    assert script.strip()
    assert prov["source"] == "template"


# ── Step kwargs / instructions gating ─────────────────────────────────
def test_step_kwargs_shape():
    pytest.importorskip("genblaze_core")
    from genblaze_core import Modality

    kwargs = vo.voiceover_step_kwargs("hello", model="tts-1", voice="nova")
    assert kwargs["model"] == "tts-1"
    assert kwargs["prompt"] == "hello"
    assert kwargs["modality"] == Modality.AUDIO
    assert kwargs["voice"] == "nova"
    assert kwargs["response_format"] == vo.VOICEOVER_FORMAT


def test_instructions_only_for_gpt_tts_models():
    pytest.importorskip("genblaze_core")
    # gpt-4o-mini-tts accepts a delivery-tone instruction…
    assert "instructions" in vo.voiceover_step_kwargs("hi", model="gpt-4o-mini-tts")
    # …tts-1 rejects it, so it must never be sent (would 400 the request).
    assert "instructions" not in vo.voiceover_step_kwargs("hi", model="tts-1")


def test_supports_instructions():
    assert vo._supports_instructions("gpt-4o-mini-tts")
    assert vo._supports_instructions("gpt-5-mini-tts")
    assert not vo._supports_instructions("tts-1")
    assert not vo._supports_instructions("tts-1-hd")


# ── Windows file:// fix (genblaze issue 05, reappearing in TTS) ────────
def test_fix_file_uri_repairs_the_sdk_url(tmp_path):
    """The SDK builds file://{quote(path)}; on Windows that misplaces the whole path into the
    netloc so ObjectStorageSink can't upload it. Rebuild with Path.as_uri() — byte-identical on
    POSIX (a no-op there), corrected on Windows."""
    f = tmp_path / "clip.mp3"
    f.write_bytes(b"\xff\xf3\x00audio")
    sdk_url = f"file://{quote(str(f.resolve()))}"  # exactly what genblaze_openai builds
    fixed = vo._fix_file_uri(sdk_url)
    assert fixed == f.resolve().as_uri()
    # The repaired URL parses to a path that actually exists (the whole point).
    assert Path(urlparse(fixed).path.lstrip("/")).name == "clip.mp3"


def test_fix_file_uri_ignores_non_file_and_missing(tmp_path):
    assert vo._fix_file_uri("https://example.com/x.mp3") is None
    assert vo._fix_file_uri(None) is None
    missing = tmp_path / "nope.mp3"
    assert vo._fix_file_uri(f"file://{quote(str(missing))}") is None


# ── Pipeline construction ─────────────────────────────────────────────
def test_build_pipeline_with_injected_provider():
    pytest.importorskip("genblaze_core")

    class FakeProvider:  # minimal stand-in — no network, no key
        pass

    pipe = vo.build_voiceover_pipeline("narration text", provider=FakeProvider())
    assert pipe is not None


# ── Pricing ───────────────────────────────────────────────────────────
def test_voiceover_has_a_price():
    from app import pricing
    from app.models import Style

    assert pricing.estimate_style(Style.voiceover) == pricing.AUDIO_UNIT_USD
    assert pricing.unit_usd(Style.voiceover) == pricing.AUDIO_UNIT_USD


def test_unpriced_voiceover_settles_at_estimate_not_free():
    """OpenAI TTS reports Step.cost_usd=None; summing only real costs would refund the hold."""
    from app import pricing

    total, source = pricing.billable_cost(
        [{"style": "voiceover", "provider": "openai-tts", "cost_usd": None}]
    )
    assert total == pricing.AUDIO_UNIT_USD
    assert source == "estimate"


# ── Narrated video (ffmpeg mux) ───────────────────────────────────────
def test_ffmpeg_binary_resolves_or_none():
    """Returns a real, existing binary (system ffmpeg or the bundled imageio one) — or None,
    in which case the mux is skipped and audio still ships."""
    from pathlib import Path

    ff = vo.ffmpeg_binary()
    assert ff is None or Path(ff).exists()


def test_build_narrated_pipeline_constructs():
    """Builds the compositor pipeline without running ffmpeg (construction only)."""
    pytest.importorskip("genblaze_core")
    pipe = vo.build_narrated_pipeline(
        "file:///tmp/looped.mp4", "file:///tmp/narration.mp3",
        ffmpeg="ffmpeg", video_sha256="a" * 64, audio_sha256="b" * 64,
    )
    assert pipe is not None


def test_muxed_video_settles_free():
    """The mux is a local ffmpeg op — no provider bill. Its inputs were each already billed."""
    from app import pricing

    total, source = pricing.billable_cost(
        [{"style": "voiceover", "provider": "ffmpeg-compositor", "cost_usd": None}]
    )
    assert total == 0.0
    assert source == "none"


# ── Generation helpers: audio classification ──────────────────────────
def test_modality_for_audio():
    from app.generation import _modality_for
    from app.models import Modality, Style

    assert _modality_for(Style.voiceover, "audio/mpeg") == Modality.audio
    # Media-type wins even if the style bookkeeping says otherwise.
    assert _modality_for(Style.studio, "audio/wav") == Modality.audio
    assert _modality_for(Style.video, "video/mp4") == Modality.video
    assert _modality_for(Style.studio, "image/png") == Modality.image


def test_ext_for_audio():
    from app.generation import _ext_for

    assert _ext_for("audio/mpeg") == ".mp3"
    assert _ext_for("audio/wav") == ".wav"


# ── The dev mock refuses to fabricate audio (stays honest) ─────────────
async def test_mock_skips_voiceover_as_partial():
    """The mock copies the uploaded image; it cannot invent a narration, so it must skip
    voiceover with a reason (⇒ the job settles partial) rather than emit a fake clip."""
    from app.generation import _run_mock

    class _Rep:
        def __init__(self):
            self.skipped = []

        def start(self, style):
            ...

        def finish(self, style, assets):
            ...

        def fail(self, style, error):
            ...

        def skip(self, style, reason):
            self.skipped.append((style, reason))

    from app.models import Style

    original = {"sha256": "a" * 64, "b2_key": "assets/aa/aa/x.png", "mime_type": "image/png"}
    rep = _Rep()
    assets, errors = await _run_mock({"id": "s"}, original, [Style.voiceover], rep)
    assert assets == []
    assert any("voiceover" in e for e in errors)
    assert rep.skipped and rep.skipped[0][0] is Style.voiceover
