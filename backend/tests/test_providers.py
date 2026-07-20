"""Cross-provider image adaptation (originshot_pipelines/providers.py).

The failures these guard against are all *silent* ones — a step that runs, costs money and
returns a plausible image while having done the wrong thing:

  * OpenAI given the source as a param instead of `external_inputs` renders a generic
    product from text and never sees the seller's photo at all;
  * a param the provider ignores still lands in the provenance manifest, so the manifest
    describes a run that did not happen;
  * a provider reporting no cost settles as free and refunds the user's whole hold.

None of these raise. Each is asserted here rather than left to a live run to discover.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from originshot_pipelines import providers
from originshot_pipelines.providers import GMICLOUD, OPENAI, ImageEditRequest

pytest.importorskip("genblaze_core")


def _req(aspect: str = "1:1") -> ImageEditRequest:
    return ImageEditRequest(
        prompt="Professional e-commerce product photograph of a blue mug.",
        source_uri="https://s3.example.com/bucket/assets/ab/cd/abcd.png?X-Amz-Signature=x",
        prompt_name="originshot-studio",
        aspect=aspect,
        source_sha256="abcd" * 16,
    )


def _local_req() -> ImageEditRequest:
    """A request whose source needs no staging — keeps fallback tests off the network."""
    return ImageEditRequest(
        prompt="p", source_uri="file:///tmp/x.png", prompt_name="originshot-studio",
    )


# ── OpenAI contract ───────────────────────────────────────────────────
def test_openai_seeds_step_inputs_not_an_image_param():
    """`external_inputs` is what routes the call to /images/edits.

    Passing the source as `image=` (GMI's contract) would leave Step.inputs empty, so
    DalleProvider would call /images/generations and invent a product from the prompt. The
    output would look fine and be of the wrong object — the one failure this whole app
    exists to prevent.
    """
    kwargs = providers.OpenAIAdapter().build_kwargs(_req())

    assert "image" not in kwargs
    inputs = kwargs["external_inputs"]
    assert len(inputs) == 1
    assert inputs[0].url.startswith("https://s3.example.com/")
    assert inputs[0].sha256 == "abcd" * 16


def test_openai_requests_high_input_fidelity():
    """The knob that makes this provider usable for provenance-grade product shots."""
    assert providers.OpenAIAdapter().build_kwargs(_req())["input_fidelity"] == "high"


def test_openai_never_forwards_params_it_ignores():
    """Unread kwargs still land in Step.params and are recorded in the manifest verbatim.

    `aspect_ratio` is GMI's vocabulary; gpt-image-* reads `size`. Forwarding it anyway would
    write a parameter into a signed provenance record that demonstrably did not shape the
    output.
    """
    kwargs = providers.OpenAIAdapter().build_kwargs(_req(aspect="4:5"))
    assert "aspect_ratio" not in kwargs
    assert kwargs["size"] == "1024x1536"


@pytest.mark.parametrize(
    ("aspect", "size"),
    [("1:1", "1024x1024"), ("4:5", "1024x1536"), ("16:9", "1536x1024"), ("weird", "1024x1024")],
)
def test_openai_size_mapping_covers_our_aspect_vocabulary(aspect, size):
    assert providers.openai_size_for(aspect) == size


# ── GMI contract (regression guard) ───────────────────────────────────
def test_gmi_contract_is_unchanged_by_the_refactor():
    """GMI's step shape must survive the adapter refactor byte-for-byte."""
    kwargs = providers.GMICloudAdapter().build_kwargs(_req(aspect="4:5"))

    assert kwargs["image"] == _req().source_uri          # reference rides as a param
    assert kwargs["aspect_ratio"] == "4:5"               # native aspect vocabulary
    assert kwargs["model"] == "gemini-3-pro-image-preview"
    assert "external_inputs" not in kwargs
    assert "size" not in kwargs


# ── Chain selection ───────────────────────────────────────────────────
def _configure(monkeypatch, *, openai: bool, gmi: bool):
    from app import config

    settings = config.get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test" if openai else None)
    monkeypatch.setattr(settings, "gmi_api_key", "gmi-test" if gmi else None)


def test_auto_chain_prefers_gmi_then_openai(monkeypatch):
    _configure(monkeypatch, openai=True, gmi=True)
    assert [a.provider_id for a in providers.image_chain("auto")] == [GMICLOUD, OPENAI]


def test_auto_chain_drops_unconfigured_providers(monkeypatch):
    _configure(monkeypatch, openai=True, gmi=False)
    assert [a.provider_id for a in providers.image_chain("auto")] == [OPENAI]


def test_pinning_an_unconfigured_provider_yields_no_chain(monkeypatch):
    """A pinned provider is a decision, not a preference.

    Silently serving a different provider would put a false provider name on the asset, the
    manifest and the ledger entry.
    """
    _configure(monkeypatch, openai=True, gmi=False)
    assert providers.image_chain(GMICLOUD) == []


def test_unknown_provider_is_rejected_loudly(monkeypatch):
    _configure(monkeypatch, openai=True, gmi=True)
    with pytest.raises(ValueError, match="Unknown IMAGE_PROVIDER"):
        providers.image_chain("stable-diffusion-fanfic")


def test_default_adapter_needs_no_credentials(monkeypatch):
    """Choosing a parameter contract must not require an API key — only running does."""
    _configure(monkeypatch, openai=False, gmi=False)
    assert providers.default_chain() == []
    assert providers.default_adapter().provider_id == GMICLOUD


# ── Source staging (genblaze issue 06 workaround) ─────────────────────
def test_staging_is_skipped_when_the_provider_reads_urls_directly():
    """GMI takes the presigned URL as-is — staging it would be a pointless download."""
    with providers._stage_source(_req(), providers.GMICloudAdapter()) as staged:
        assert staged.source_uri == _req().source_uri


def test_staging_is_skipped_for_a_source_that_is_already_local():
    with providers._stage_source(_local_req(), providers.OpenAIAdapter()) as staged:
        assert staged.source_uri == "file:///tmp/x.png"


def test_staging_gives_openai_a_file_url_with_a_truthful_extension(monkeypatch, tmp_path):
    """The whole point: `.img` makes OpenAI see application/octet-stream and 400.

    Also asserts the URL is `file:///…` with an EMPTY netloc — the SDK's own
    f"file://{quote(path)}" spelling puts a Windows path in the netloc and its own validator
    rejects it (issue 05).
    """
    from urllib.parse import urlparse

    class _Resp:
        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"\x89PNG\r\n\x1a\n"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import httpx

    monkeypatch.setattr(httpx, "stream", lambda *a, **k: _Resp())

    with providers._stage_source(_req(), providers.OpenAIAdapter()) as staged:
        parsed = urlparse(staged.source_uri)
        assert parsed.scheme == "file"
        assert parsed.netloc == ""                 # issue 05
        assert staged.source_uri.endswith(".png")  # issue 06
        from urllib.request import url2pathname

        assert Path(url2pathname(parsed.path)).read_bytes().startswith(b"\x89PNG")


def test_staged_file_is_removed_even_when_the_provider_raises(monkeypatch):
    """A failed generation must not leave the seller's product photo in a temp dir."""
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    class _Resp:
        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"bytes"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import httpx

    monkeypatch.setattr(httpx, "stream", lambda *a, **k: _Resp())

    captured: dict = {}
    with pytest.raises(RuntimeError, match="boom"):
        with providers._stage_source(_req(), providers.OpenAIAdapter()) as staged:
            captured["path"] = Path(url2pathname(urlparse(staged.source_uri).path))
            assert captured["path"].exists()
            raise RuntimeError("boom")

    assert not captured["path"].exists()


# ── Cross-provider fallback ───────────────────────────────────────────
class _FakeStep:
    def __init__(self, assets):
        self.assets = assets


class _FakeResult:
    def __init__(self, assets):
        self._assets = assets

    def succeeded_steps(self):
        return [_FakeStep(self._assets)]

    def error_summary(self):
        return "no assets"


async def test_run_image_edit_falls_across_providers(monkeypatch):
    """A provider whose account is out of credit must not fail the style.

    `fallback_models=` cannot do this — it retries other models on the *same* provider, so a
    402 that applies to the whole account defeats it. This is the case that made the app's
    image path resilient while GMI sat at zero balance.
    """
    attempted: list[str] = []

    class _Pipe:
        def __init__(self, provider_id):
            self._pid = provider_id

        async def arun(self, sink=None, timeout=None):
            attempted.append(self._pid)
            if self._pid == GMICLOUD:
                raise RuntimeError("GMICloud submit failed (402): Insufficient credits.")
            return _FakeResult(["asset"])

    monkeypatch.setattr(
        providers, "build_image_pipeline",
        lambda req, adapter, provider=None: _Pipe(adapter.provider_id),
    )
    chain = [providers.GMICloudAdapter(), providers.OpenAIAdapter()]

    result, adapter = await providers.run_image_edit(
        _local_req(), sink=None, timeout=5, chain=chain
    )

    assert attempted == [GMICLOUD, OPENAI]      # tried the cheap one first, then fell across
    assert adapter.provider_id == OPENAI        # and reports who actually served
    assert result.succeeded_steps()[0].assets == ["asset"]


async def test_run_image_edit_treats_an_empty_result_as_failure(monkeypatch):
    """A run that "succeeds" with no asset is a failure that forgot to raise."""
    class _Empty:
        async def arun(self, sink=None, timeout=None):
            return _FakeResult([])

    monkeypatch.setattr(
        providers, "build_image_pipeline", lambda req, adapter, provider=None: _Empty()
    )
    with pytest.raises(RuntimeError, match="no assets"):
        await providers.run_image_edit(
            _local_req(), sink=None, timeout=5, chain=[providers.OpenAIAdapter()]
        )


async def test_run_image_edit_reports_every_provider_that_failed(monkeypatch):
    class _Broken:
        def __init__(self, pid):
            self._pid = pid

        async def arun(self, sink=None, timeout=None):
            raise RuntimeError(f"{self._pid} exploded")

    monkeypatch.setattr(
        providers, "build_image_pipeline",
        lambda req, adapter, provider=None: _Broken(adapter.provider_id),
    )
    chain = [providers.GMICloudAdapter(), providers.OpenAIAdapter()]
    with pytest.raises(RuntimeError) as exc:
        await providers.run_image_edit(_local_req(), sink=None, timeout=5, chain=chain)

    # Both provider labels survive into the error — a pack that failed everywhere has to
    # say so per provider, or an operator cannot tell an outage from an empty wallet.
    assert "GMI Cloud" in str(exc.value)
    assert "OpenAI" in str(exc.value)


async def test_run_image_edit_refuses_without_a_configured_provider(monkeypatch):
    _configure(monkeypatch, openai=False, gmi=False)
    with pytest.raises(RuntimeError, match="No image provider is configured"):
        await providers.run_image_edit(_local_req(), sink=None, timeout=5)
