"""Provider adaptation — one image-edit request, several incompatible provider contracts.

Every image style in this app asks the same question: *"here is the authentic photo of a
product, restage it like this, and keep it recognisably the same object."* Two providers
answer that question today, and they disagree about almost every detail of how to ask it:

| | GMI Cloud (`gmicloud-image`) | OpenAI (`openai-dalle`) |
|---|---|---|
| reference image | `image=<url>` — an ordinary **step param** | `external_inputs=[Asset]` → `Step.inputs`, which is what routes the call to `/images/edits` |
| output shape | `aspect_ratio="4:5"` | `size="1024x1536"` from a fixed enum |
| fidelity knob | *(none — implicit in the model)* | `input_fidelity="high"` |
| cost reporting | `Step.cost_usd` populated | **`None`** — the SDK dropped OpenAI pricing in genblaze-core 0.3.0 |

Hiding that behind `if provider == ...` inside four pipeline modules would spread the same
four-way conditional across studio, lifestyle, on-model and variants. Instead each provider
gets one adapter that owns its whole contract, and the pipelines build against
:class:`ImageEditRequest` — the request as *this product* understands it (a source photo, a
prompt, an aspect) rather than as any one vendor spells it.

**Params that do nothing are never sent.** Unrecognised kwargs still land in ``Step.params``
and are recorded verbatim in the provenance manifest, so forwarding ``aspect_ratio`` to
OpenAI — which ignores it in favour of ``size`` — would write a parameter into a provenance
record that demonstrably did not shape the output. In a project whose entire claim is that
the manifest describes how the file was really made, that is a lie with a hash on it. Each
adapter therefore emits only kwargs its provider actually reads.

**Live-probe evidence (2026-07-20), not catalog presence** — the standard the rest of
`registry.py` holds to:

    OpenAI  gpt-image-1  + input_fidelity=high, medium quality, 1024x1024
      → real edit of the anchored mug (05993b99…) into a lifestyle scene in 26.3s.
        Two-tone glaze split, the dark horizontal line through the upper band, handle
        geometry and speckle all preserved — i.e. it holds product identity, which is the
        only property this app cannot compromise on.
    GMI     gemini-3-pro-image-preview
      → HTTP 402 Insufficient credits on the request-queue API (account balance, not
        entitlement). GMI's *chat* endpoint bills separately and still answers 200, which is
        why QA scoring, Resolve and listing copy are unaffected.

That 402 is also why cross-provider fallback exists here rather than in the SDK: Genblaze's
``fallback_models=`` retries other models *on the same provider*, so it cannot route around
a provider whose whole account is out of credit. See :func:`image_chain`.
"""
from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

from .registry import (
    IMAGE_EDIT_FALLBACKS,
    IMAGE_EDIT_MODEL,
    OPENAI_IMAGE_EDIT_FALLBACKS,
    OPENAI_IMAGE_EDIT_MODEL,
    OPENAI_IMAGE_QUALITY,
    REFERENCE_IMAGE_KWARG,
)

log = logging.getLogger("originshot.providers")

# Provider ids, as reported by the SDK on `Step.provider`. These are the strings that end up
# on asset documents, in the analytics provider-mix chart, and in the manifest — so they are
# the SDK's names, never ours.
GMICLOUD = "gmicloud-image"
OPENAI = "openai-dalle"


def with_feedback(prompt: str, feedback: str | None) -> str:
    """Append QA correction guidance to a prompt for a retry attempt.

    Kept as a plain string append (not a structured field) because the reference-image edit
    providers take a single natural-language instruction — the correction has to live in the
    same prompt the base style does. Empty feedback returns the prompt untouched, so the first
    attempt is never altered.
    """
    if not feedback:
        return prompt
    return f"{prompt} Correct these issues from the previous attempt: {feedback}."


@dataclass(frozen=True)
class ImageEditRequest:
    """One "restage this product photo" request, in this product's own vocabulary.

    Attributes:
        prompt: The fully-built prompt (the style modules own prompt construction).
        source_uri: Presigned https URL of the authentic original, or a file:// URL in dev.
        prompt_name: Pipeline name, e.g. "originshot-studio" — carried into the manifest.
        aspect: A key of :data:`registry.ASPECT` ("1:1", "4:5", …).
        source_sha256: Content hash of the source. Optional, but supplying it lets the SDK
            record real input lineage instead of warning about an unhashed external input.
        source_media_type: MIME of the source; only OpenAI needs it (it opens a file handle).
    """

    prompt: str
    source_uri: str
    prompt_name: str = "originshot-image"
    aspect: str = "1:1"
    source_sha256: str | None = None
    source_media_type: str = "image/png"


# ── Aspect translation ────────────────────────────────────────────────
# gpt-image-* accepts only a fixed size enum (1024x1024 / 1536x1024 / 1024x1536 / auto), so
# our aspect vocabulary has to be mapped onto it rather than passed through.
#
# ⚠️ Honest imprecision: "4:5" maps to 1024x1536, which is 2:3 — taller than asked. OpenAI
# has no 4:5 size. This is safe *here* specifically because marketplace deliverables are
# re-rendered to exact per-channel dimensions downstream (presets.py cover-crops lifestyle
# channels), so the listing file is exact regardless; only the master's framing is looser.
# Recorded rather than rounded away, because "close enough" undocumented is how a pack
# silently starts failing a channel's dimension rule.
_OPENAI_SIZE_BY_ASPECT: dict[str, str] = {
    "1:1": "1024x1024",
    "4:5": "1024x1536",
    "9:16": "1024x1536",
    "16:9": "1536x1024",
    "3:2": "1536x1024",
}
_OPENAI_DEFAULT_SIZE = "1024x1024"


def openai_size_for(aspect: str) -> str:
    """Nearest gpt-image size for one of our aspect keys."""
    return _OPENAI_SIZE_BY_ASPECT.get(aspect, _OPENAI_DEFAULT_SIZE)


# ── Adapters ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ImageAdapter:
    """How one provider wants an image-edit step spelled.

    `build_kwargs` returns the kwargs for `Pipeline.step(provider, **kwargs)`; `make_provider`
    constructs the SDK provider lazily so importing this module never requires every
    genblaze-* plugin to be installed.
    """

    provider_id: str
    label: str
    model: str
    fallback_models: list[str] = field(default_factory=list)
    # True when the provider cannot consume a remote URL directly and the source must be
    # staged to a local file first. See _stage_source.
    needs_local_source: bool = False

    def configured(self) -> bool:  # pragma: no cover - overridden
        raise NotImplementedError

    def make_provider(self):  # pragma: no cover - overridden
        raise NotImplementedError

    def build_kwargs(self, req: ImageEditRequest) -> dict:  # pragma: no cover - overridden
        raise NotImplementedError


class GMICloudAdapter(ImageAdapter):
    """GMI Cloud — the reference image rides as an ordinary step param."""

    def __init__(self) -> None:
        super().__init__(
            provider_id=GMICLOUD,
            label="GMI Cloud",
            model=IMAGE_EDIT_MODEL,
            fallback_models=list(IMAGE_EDIT_FALLBACKS),
        )

    def configured(self) -> bool:
        from app.config import get_settings

        return bool(get_settings().gmi_api_key)

    def make_provider(self):
        from genblaze_gmicloud import GMICloudImageProvider

        return GMICloudImageProvider()

    def build_kwargs(self, req: ImageEditRequest) -> dict:
        from genblaze_core import Modality

        return {
            "model": self.model,
            "prompt": req.prompt,
            "modality": Modality.IMAGE,
            "aspect_ratio": req.aspect,
            "fallback_models": self.fallback_models,
            REFERENCE_IMAGE_KWARG: req.source_uri,
        }


class OpenAIAdapter(ImageAdapter):
    """OpenAI images — the reference image must seed ``Step.inputs`` to reach /images/edits.

    `DalleProvider.generate` routes on ``bool(step.inputs)``: with inputs it calls
    ``client.images.edit``, without them ``client.images.generate``. Passing the source as a
    param named `image` (GMI's contract) would therefore silently produce a *text-to-image*
    render of a generic product — plausible-looking output that is not the seller's item at
    all. That failure is invisible to every check except the QA product-match score, which is
    precisely the failure mode this app exists to prevent, so it is worth stating loudly.
    """

    def __init__(self) -> None:
        super().__init__(
            provider_id=OPENAI,
            label="OpenAI",
            model=OPENAI_IMAGE_EDIT_MODEL,
            fallback_models=list(OPENAI_IMAGE_EDIT_FALLBACKS),
            needs_local_source=True,   # see _stage_source — genblaze issue 06
        )

    def configured(self) -> bool:
        from app.config import get_settings

        return bool(get_settings().openai_api_key)

    def make_provider(self):
        return _make_openai_provider()

    def build_kwargs(self, req: ImageEditRequest) -> dict:
        from genblaze_core import Modality
        from genblaze_core.models.asset import Asset

        source = Asset(
            url=req.source_uri,
            media_type=req.source_media_type,
            sha256=req.source_sha256,
        )
        return {
            "model": self.model,
            "prompt": req.prompt,
            "modality": Modality.IMAGE,
            # NOT `image=`: seeding Step.inputs is what selects the edit endpoint.
            "external_inputs": [source],
            "size": openai_size_for(req.aspect),
            "quality": OPENAI_IMAGE_QUALITY,
            # The whole reason this provider is usable for provenance-grade product shots.
            "input_fidelity": "high",
            "fallback_models": self.fallback_models,
        }


_ADAPTERS: dict[str, type[ImageAdapter]] = {
    GMICLOUD: GMICloudAdapter,
    OPENAI: OpenAIAdapter,
}

# Preference order when IMAGE_PROVIDER is "auto". GMI leads on price (list $0.04/image vs
# ~$0.042 at gpt-image-1 medium) and because its model takes our aspect vocabulary exactly.
# Order is preference, not availability — image_chain() filters to configured providers, and
# a provider that is configured but broken (402, outage) is skipped at *run* time by the
# cross-provider fallback rather than being pre-emptively removed here. We cannot tell "out
# of credit" from "temporarily failing" without spending a request to find out, and guessing
# would either strand a working provider or hide a real outage.
AUTO_ORDER: tuple[str, ...] = (GMICLOUD, OPENAI)


def image_chain(preference: str | None = None) -> list[ImageAdapter]:
    """Configured image-edit adapters, best first.

    `preference` pins a single provider by id ("gmicloud-image" / "openai-dalle"); "auto" or
    None walks :data:`AUTO_ORDER`. A pinned provider that isn't configured yields an empty
    chain rather than silently falling back — an operator who named a provider wants that
    provider, and quietly serving a different one would misreport provenance.
    """
    pref = (preference or "auto").strip().lower()
    if pref in ("", "auto"):
        ordered = [_ADAPTERS[p]() for p in AUTO_ORDER]
    elif pref in _ADAPTERS:
        ordered = [_ADAPTERS[pref]()]
    else:
        raise ValueError(
            f"Unknown IMAGE_PROVIDER {preference!r}. "
            f"Expected 'auto' or one of {sorted(_ADAPTERS)}."
        )
    return [a for a in ordered if a.configured()]


def default_chain() -> list[ImageAdapter]:
    """The chain implied by current settings. Empty when no provider is configured."""
    from app.config import get_settings

    return image_chain(get_settings().image_provider)


def default_adapter() -> ImageAdapter:
    """Which provider's *parameter contract* to build a step against.

    Falls back to the first entry in :data:`AUTO_ORDER` when nothing is configured. Choosing
    a contract needs no credentials — only :meth:`ImageAdapter.make_provider` does — so a
    caller supplying its own provider (tests, replay, a one-off single-provider run) must not
    be forced to hold an API key just to shape a step. Running the step still requires a real
    provider, and `run_image_edit` refuses an empty chain.
    """
    chain = default_chain()
    return chain[0] if chain else _ADAPTERS[AUTO_ORDER[0]]()


# ── Output URL repair (workaround for genblaze-openai 0.3.2 on Windows) ───────────────
def _make_openai_provider():
    """`DalleProvider`, with the one output-URL construction that breaks on Windows fixed.

    The SDK builds every output asset's URL as ``f"file://{quote(str(path))}"``
    (dalle.py:539). On POSIX that is correct — ``file:///tmp/x.png``. On Windows the path has
    no leading slash, so the *entire* path becomes the URL's **netloc** and ``path`` is
    empty:

        file://C%3A%5CUsers%5C…%5Cx.png     netloc='C%3A%5C…'  path=''

    Anything that consumes that URL then resolves an empty path. Two things downstream do:

      * ``ObjectStorageSink`` resolves it to the process CWD and refuses the transfer
        ("local file path … is outside allowed directories"), so **no OpenAI-generated asset
        can be uploaded to B2 at all**; and
      * ``validate_chain_input_url`` rejects a non-empty netloc outright, so the provider's
        own output cannot be fed into a second step.

    `Path.as_uri()` is the stdlib spelling and yields a byte-identical result on POSIX, so
    this override changes nothing in production (Render is Linux) while making local
    development on Windows work. One code path, not a platform branch.

    Filed as genblaze issue 05. Subclassed rather than monkeypatched so the change is scoped
    to the provider *this app* constructs and cannot surprise anything else importing the SDK.
    """
    from genblaze_openai import DalleProvider

    class _OriginShotDalleProvider(DalleProvider):
        def _persist_image_bytes(self, img_bytes, step, index, ext):
            if self._output_dir:
                self._output_dir.mkdir(parents=True, exist_ok=True)
                out_path = self._output_dir / f"{step.step_id}_{index}{ext}"
            else:
                fd, tmp = tempfile.mkstemp(suffix=ext)
                os.close(fd)
                out_path = Path(tmp)
            out_path.write_bytes(img_bytes)
            return (
                out_path.resolve().as_uri(),          # ← the fix
                hashlib.sha256(img_bytes).hexdigest(),
                len(img_bytes),
            )

    return _OriginShotDalleProvider()


# ── Source staging (workaround for genblaze-openai 0.3.2) ─────────────
_EXT_BY_MIME = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


@contextlib.contextmanager
def _stage_source(req: ImageEditRequest, adapter: ImageAdapter):
    """Yield a request whose source the provider can actually read.

    **Why this exists.** `genblaze_openai`'s `DalleProvider` downloads an https input to a
    temp file created as ``tempfile.mkstemp(suffix=".img")`` (dalle.py:340). The OpenAI
    client infers the upload's MIME type from that filename, so every remote reference
    arrives as ``application/octet-stream`` and the API rejects it:

        400 Invalid file 'image': unsupported mimetype ('application/octet-stream').
            Supported file formats are 'image/jpeg', 'image/png', and 'image/webp'.

    That makes `/images/edits` unreachable for **any** https source — which is every source
    in this app, since originals live in a private B2 bucket and are handed to providers as
    presigned URLs. The provider's `file://` branch (dalle.py:567) keeps the real filename,
    so staging the bytes locally under a truthful extension restores the edit path.

    Filed as genblaze issue 06. Two SDK defects are sidestepped here at once: the URL is
    built with `Path.as_uri()` because the SDK's own
    ``f"file://{quote(str(path))}"`` construction produces a Windows URL whose entire path
    lands in the netloc, which its own `validate_chain_input_url` then rejects (issue 05).

    The staged file is always removed, including when the provider raises — a failed
    generation must not leave the seller's product photo sitting in a temp directory.
    """
    remote = req.source_uri.lower().startswith(("http://", "https://"))
    if not (adapter.needs_local_source and remote):
        yield req
        return

    import httpx

    suffix = _EXT_BY_MIME.get(req.source_media_type, ".png")
    fd, tmp = tempfile.mkstemp(prefix="originshot-src-", suffix=suffix)
    path = Path(tmp)
    try:
        with open(fd, "wb") as fh:
            with httpx.stream("GET", req.source_uri, timeout=60, follow_redirects=False) as r:
                r.raise_for_status()
                for chunk in r.iter_bytes():
                    fh.write(chunk)
        yield replace(req, source_uri=path.resolve().as_uri())
    finally:
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)


def build_image_pipeline(req: ImageEditRequest, adapter: ImageAdapter, *, provider=None):
    """A one-step Genblaze Pipeline that satisfies `req` on `adapter`'s provider.

    `provider` may be injected for tests; otherwise the adapter constructs the real one.
    """
    from genblaze_core import Pipeline

    provider = provider if provider is not None else adapter.make_provider()
    return Pipeline(req.prompt_name).step(provider, **adapter.build_kwargs(req))


async def run_image_edit(req: ImageEditRequest, *, sink, timeout: int,
                         chain: list[ImageAdapter] | None = None):
    """Run `req` against the first provider in the chain that produces an asset.

    Returns ``(PipelineResult, ImageAdapter)`` so the caller knows which provider actually
    served — that pairing is what the asset document, the manifest and the provider-mix
    chart all record.

    Cross-provider fallback is *our* job, not the SDK's: `fallback_models=` swaps models
    within one provider, so it cannot route around a 402 that applies to the whole account.
    A provider is only skipped after it genuinely fails, and every failure is logged with the
    provider that produced it — a silent downgrade would make a pack's provenance unexplainable.
    """
    adapters = chain if chain is not None else default_chain()
    if not adapters:
        raise RuntimeError(
            "No image provider is configured — set OPENAI_API_KEY or GMI_API_KEY."
        )

    errors: list[str] = []
    for adapter in adapters:
        try:
            # Staged per attempt, not once up front: only some providers need it, and a
            # provider we never reach should never cost a download.
            with _stage_source(req, adapter) as staged:
                pipeline = build_image_pipeline(staged, adapter)
                result = await pipeline.arun(sink=sink, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 — try the next provider, report if none work
            log.warning("image step failed on %s: %s", adapter.provider_id, exc)
            errors.append(f"{adapter.label}: {exc}")
            continue
        if _has_asset(result):
            if errors:
                log.info("image step recovered on %s after %d failure(s)",
                         adapter.provider_id, len(errors))
            return result, adapter
        # A "successful" run with no asset is a failure that didn't raise — genblaze-core
        # 0.3.6 fixed the empty-assets case upstream, but a fallback chain is exactly where
        # a silently empty result would be most expensive to trust.
        summary = _error_summary(result)
        log.warning("image step produced no asset on %s: %s", adapter.provider_id, summary)
        errors.append(f"{adapter.label}: {summary}")

    raise RuntimeError("; ".join(errors) or "image generation failed on every provider")


def _has_asset(result) -> bool:
    try:
        return any(getattr(s, "assets", None) for s in result.succeeded_steps())
    except Exception:  # noqa: BLE001
        return False


def _error_summary(result) -> str:
    try:
        return str(result.error_summary() or "no assets returned")
    except Exception:  # noqa: BLE001
        return "no assets returned"
