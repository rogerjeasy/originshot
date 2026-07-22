"""Generation engine — maps Genblaze pipeline runs (or a dev mock) to asset documents.

Real generation requires: Genblaze installed, a provider key (GMI), and B2 configured
(the Genblaze ObjectStorageSink writes to B2). Otherwise the dev mock runs so the full UX
works locally. Each style is isolated so one provider failure yields a *partial* result
rather than a total failure.
"""
from __future__ import annotations

import logging
import uuid

from .config import get_settings
from .models import Modality, Style
from .storage import key_from_url

log = logging.getLogger("originshot.generation")

# Order is also execution order: studio must precede video (which consumes its hero frame),
# and voiceover runs last so it can, in a later step, be muxed onto that hero video. The
# voiceover audio itself does not depend on the video — it renders from the narration script.
GENERATED_STYLES = [Style.studio, Style.lifestyle, Style.onmodel, Style.variant, Style.video,
                    Style.voiceover]

# Default variant sweep (kept small to bound cost).
VARIANT_COLORS = ["matte black", "sage green"]
VARIANT_ANGLES = ["three-quarter"]


def genblaze_available() -> bool:
    try:
        import genblaze_core  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


class GenerationUnavailable(RuntimeError):
    """Raised when real generation isn't configured and mocking isn't permitted.

    Carries the specific missing pieces so an operator sees *what* to fix instead of a
    generic failure. Surfaced as a 503 by the API layer.
    """


def missing_generation_requirements() -> list[str]:
    """Which prerequisites for real generation are absent. Empty ⇒ ready to generate.

    Image generation needs *an* image provider, not one specific vendor — since 2026-07-20
    either `OPENAI_API_KEY` or `GMI_API_KEY` satisfies it (see providers.image_chain). Naming
    only GMI here would report a fully-working OpenAI-served deployment as "unconfigured"
    and refuse every request with a 503.
    """
    s = get_settings()
    missing = []
    if not (s.openai_api_key or s.gmi_api_key):
        missing.append("an image provider key (OPENAI_API_KEY or GMI_API_KEY)")
    if not s.b2_configured:
        missing.append("B2 storage (B2_KEY_ID / B2_APP_KEY / B2_BUCKET)")
    if not genblaze_available():
        missing.append("genblaze-core SDK (pip install genblaze-core)")
    return missing


def generation_mode() -> str:
    """What will actually run: "genblaze", "mock" (tests only), or "unconfigured".

    "unconfigured" is a real, reported state rather than a silent fall-through to fake
    output — see Settings.mock_generation_enabled for why the mock is off by default.
    """
    if not missing_generation_requirements():
        return "genblaze"
    return "mock" if get_settings().mock_generation_enabled else "unconfigured"


def brand_prompt_fragment(brand: dict | None) -> str:
    """Full brand fragment for contextual styles (lifestyle/on-model/variant)."""
    if not brand:
        return ""
    parts = [str(brand[k]).strip() for k in ("vibe", "lighting", "palette", "props", "notes")
             if brand.get(k)]
    return "; ".join(parts)


def brand_tone_fragment(brand: dict | None) -> str:
    """Lighter fragment for studio/video — avoids palette/props that fight a pure-white bg."""
    if not brand:
        return ""
    parts = [str(brand[k]).strip() for k in ("vibe", "lighting") if brand.get(k)]
    return "; ".join(parts)


class StepReporter:
    """Callback surface for live per-step progress.

    Generation is a sequence of independent provider calls that each take tens of seconds.
    Without this the client can only see "running" for the whole run and has to fake a
    progress bar. The worker passes an implementation that persists each event onto the job
    document; `_NullReporter` keeps the pipelines callable without one.

    Every method is best-effort by contract: a reporting failure must never fail a run that
    the provider already billed for.
    """

    def start(self, style: Style) -> None: ...
    def finish(self, style: Style, assets: list[dict]) -> None: ...
    def fail(self, style: Style, error: str) -> None: ...
    def skip(self, style: Style, reason: str) -> None: ...


class _NullReporter(StepReporter):
    pass


async def generate_assets(uid, sku, original, styles, *, storage, brand=None,
                          marketplaces=None, reporter: StepReporter | None = None):
    """Return (asset_dicts, errors). `errors` non-empty + assets present ⇒ partial."""
    wanted = [Style(s) for s in styles if Style(s) in GENERATED_STYLES]
    reporter = reporter or _NullReporter()
    mode = generation_mode()
    if mode == "genblaze":
        return await _run_genblaze(
            sku, original, wanted, storage, brand, marketplaces or [], reporter
        )
    if mode == "mock":
        return await _run_mock(sku, original, wanted, reporter)
    # Refuse rather than fabricate. A user must never be handed a copy of their own upload
    # dressed up as a generated asset.
    raise GenerationUnavailable(
        "Generation is not configured — missing: "
        + ", ".join(missing_generation_requirements())
    )


# ── Dev mock ───────────────────────────────────────────────────────────
async def _run_mock(sku, original, wanted, reporter: StepReporter) -> tuple[list[dict], list[str]]:
    import asyncio

    delay = get_settings().mock_step_delay_seconds
    run_id = f"mock-{uuid.uuid4().hex[:8]}"
    out: list[dict] = []
    errors: list[str] = []
    for style in wanted:
        # Neither a video nor audio can be fabricated from the uploaded image the mock copies.
        # Reported as an error (not just a skipped step) so the job settles as *partial*: a run
        # that silently returns "done" without a style the user explicitly asked for is the job
        # status lying about what was delivered.
        if style is Style.video:
            reason = "video cannot be mocked — configure a provider"
            reporter.skip(style, reason)
            errors.append(f"video: {reason}")
            continue
        if style is Style.voiceover:
            reason = "voiceover cannot be mocked — configure OPENAI_API_KEY (OpenAI TTS)"
            reporter.skip(style, reason)
            errors.append(f"voiceover: {reason}")
            continue
        reporter.start(style)
        if delay:
            await asyncio.sleep(delay)
        asset = {
            "sku_id": sku["id"],
            "sha256": original["sha256"],
            "b2_key": original["b2_key"],
            "b2_url": None,
            "modality": Modality.image.value,
            "style": style.value,
            "is_authentic": False,
            "parent_sha256": original["sha256"],
            "run_id": run_id,
            "provider": "mock-dev",
            "model": "passthrough",
            "manifest_key": None,
            "manifest_verified": None,
            "embedded": False,
            "mime_type": original.get("mime_type"),
            "width": original.get("width"),
            "height": original.get("height"),
            "duration": None,
        }
        out.append(asset)
        reporter.finish(style, [asset])
    return out, errors


# ── Real Genblaze path ─────────────────────────────────────────────────
async def _run_genblaze(sku, original, wanted, storage, brand, marketplaces, reporter):
    from originshot_pipelines import (
        lifestyle,
        onmodel,
        presets,
        providers,
        storage as sink_module,
        studio,
        variants,
        video,
    )

    settings = get_settings()
    sink = sink_module.make_sink()
    source_uri = storage.presigned_get(original["b2_key"])
    desc = (sku.get("description") or sku.get("title") or "product").strip()
    parent = original["sha256"]
    img_t, vid_t = settings.image_timeout_seconds, settings.video_timeout_seconds

    brand_full = brand_prompt_fragment(brand)
    brand_tone = brand_tone_fragment(brand)
    studio_aspect = presets.studio_aspect_for(marketplaces)

    out: list[dict] = []
    errors: list[str] = []
    hero_url: str | None = None

    # Each style is one unit of work: it reports start → finish/fail, and a failure is
    # isolated so the remaining styles still run (that's what makes a run "partial" rather
    # than lost). Studio must run before video, which consumes its output as the hero frame;
    # GENERATED_STYLES fixes that order, so iterate it rather than the caller's list.
    # Every image style runs through the cross-provider chain (originshot_pipelines/
    # providers.py): the first configured provider serves, and a provider that actually
    # fails — a 402 on an exhausted account, an outage — falls across to the next rather
    # than failing the style. `run_image_edit` returns the provider that served alongside
    # the result; the asset document records it from the SDK's own Step.provider, so a pack
    # assembled from two providers explains itself asset by asset.
    src_mime = original.get("mime_type") or "image/png"

    # Each runner takes optional `feedback`: on a QA retry it carries the specific corrections
    # the previous attempt failed (qa.feedback_from_reports), which the request builders splice
    # into the prompt — so the second attempt fixes what was wrong rather than re-rolling.
    async def _studio(feedback: str | None = None) -> list[dict]:
        nonlocal hero_url
        req = studio.studio_request(
            source_uri, desc, brand_suffix=brand_tone, aspect=studio_aspect,
            source_sha256=parent, source_media_type=src_mime, feedback=feedback,
        )
        res, _adapter = await providers.run_image_edit(req, sink=sink, timeout=img_t)
        asset = _map(sku, res, Style.studio, parent, storage)
        # The hero image feeds the image-to-video step. After embedding we store the
        # studio image under our own key, so presign that; else use the sink URL.
        hero_url = (
            storage.presigned_get(asset["b2_key"]) if asset.get("b2_key")
            else asset.get("b2_url")
        ) or hero_url
        return [asset]

    async def _lifestyle(feedback: str | None = None) -> list[dict]:
        results = await lifestyle.run_lifestyle(
            source_uri, desc, sink, brand_suffix=brand_full, timeout=img_t,
            source_sha256=parent, feedback=feedback,
        )
        return [_map(sku, r, Style.lifestyle, parent, storage) for r, _ in results]

    async def _onmodel(feedback: str | None = None) -> list[dict]:
        req = onmodel.onmodel_request(
            source_uri, desc, brand_suffix=brand_full,
            source_sha256=parent, source_media_type=src_mime, feedback=feedback,
        )
        res, _adapter = await providers.run_image_edit(req, sink=sink, timeout=img_t)
        return [_map(sku, res, Style.onmodel, parent, storage)]

    async def _variant(feedback: str | None = None) -> list[dict]:
        results = await variants.run_variants(
            source_uri, desc, sink, colors=VARIANT_COLORS, angles=VARIANT_ANGLES,
            brand_suffix=brand_full, timeout=img_t, source_sha256=parent, feedback=feedback,
        )
        return [_map(sku, r, Style.variant, parent, storage) for r, _ in results]

    async def _video() -> list[dict]:
        res = await video.build_hero_video(
            hero_url, desc, brand_suffix=brand_tone
        ).arun(sink=sink, timeout=vid_t)
        return [_map(sku, res, Style.video, parent, storage)]

    async def _voiceover() -> list[dict]:
        # Two Genblaze hops, two providers, two modalities: the listing/chat model (GMI GLM)
        # writes the narration script, then OpenAI TTS renders it to speech — the cross-
        # provider orchestration the unified API is for. The script is AI-written; both the
        # text and how it was produced are recorded on the asset (and the manifest), never
        # passed off as human copy. A chat 429 degrades to a deterministic script rather than
        # failing the style — the same rule the QA and listing tiers follow.
        from originshot_pipelines import voiceover as vo

        script, script_prov = vo.narration_script(
            sku, brand, api_key=settings.gmi_api_key, timeout=settings.qa_vlm_timeout_seconds,
        )
        res = await vo.run_voiceover(
            script, sink=sink, timeout=settings.audio_timeout_seconds,
            api_key=settings.openai_api_key, model=settings.voiceover_model,
            voice=settings.voiceover_voice,
        )
        audio_asset = _map(sku, res, Style.voiceover, parent, storage)
        audio_asset["script"] = script
        audio_asset["script_source"] = script_prov.get("source")
        audio_asset["script_model"] = script_prov.get("model")
        produced = [audio_asset]

        # The payoff: mux the narration onto the delivered hero video → a product video that
        # talks. This is the one audio-path asset that gets full content-binding (it's an MP4).
        # Best-effort and gracefully degrading: no hero video (video wasn't requested/failed)
        # or no ffmpeg ⇒ the standalone narration audio still ships. It never fails the style.
        hero_video = next(
            (a for a in out if a.get("style") == Style.video.value
             and a.get("modality") == Modality.video.value and a.get("b2_key")),
            None,
        )
        if hero_video:
            try:
                narrated = await _mux_narrated_video(
                    sku, audio_asset, hero_video, parent, storage, sink
                )
                if narrated:
                    produced.append(narrated)
            except Exception as e:  # noqa: BLE001 — the audio is already delivered; mux is a bonus
                log.warning("narrated video mux failed (%s); delivering audio only", e)
        return produced

    runners = {
        Style.studio: _studio,
        Style.lifestyle: _lifestyle,
        Style.onmodel: _onmodel,
        Style.variant: _variant,
        Style.video: _video,
        Style.voiceover: _voiceover,
    }

    vlm_call = _make_vlm_call(settings)
    ref_bytes: bytes | None = None
    if settings.qa_enabled and vlm_call is not None:
        try:
            ref_bytes = _fetch_bytes(source_uri)
        except Exception as e:  # noqa: BLE001 — QA degrades, generation proceeds
            log.warning("QA reference fetch failed (%s); VLM tier disabled for this run", e)

    for style in GENERATED_STYLES:
        if style not in wanted:
            continue
        if style is Style.video and not hero_url:
            reason = "requires a studio image (include 'studio' in styles)"
            reporter.skip(style, reason)
            errors.append(f"video: {reason}")
            continue
        if style is Style.voiceover and not settings.openai_api_key:
            # The audio path is OpenAI TTS (GMI audio is unreachable — issue 04). Missing the
            # key is a skip with an honest reason, not a fabricated silent clip.
            reason = "requires OPENAI_API_KEY (OpenAI TTS — GMI audio unreachable, issue 04)"
            reporter.skip(style, reason)
            errors.append(f"voiceover: {reason}")
            continue
        reporter.start(style)
        try:
            produced = await runners[style]()
            # Image QA (deterministic + VLM product-match) is meaningless for video and audio:
            # there is no reference product to match a waveform against.
            if settings.qa_enabled and style not in (Style.video, Style.voiceover):
                produced = await _qa_and_maybe_retry(
                    style, runners[style], produced, storage,
                    reference=ref_bytes, vlm_call=vlm_call,
                    retry=settings.qa_retry_enabled,
                )
                # A studio retry re-ran _studio(), which repointed hero_url at the retry's
                # asset — repoint it at the batch QA actually kept, so the video step is
                # always derived from the delivered hero frame.
                if style is Style.studio and produced:
                    kept = produced[0]
                    hero_url = (
                        storage.presigned_get(kept["b2_key"]) if kept.get("b2_key")
                        else kept.get("b2_url")
                    ) or hero_url
            out.extend(produced)
            reporter.finish(style, produced)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{style.value}: {e}")
            reporter.fail(style, str(e))

    return out, errors


# ── Replay: re-run one asset from its stored manifest ──────────────────
async def replay_asset(uid, sku, source_asset, original, *, storage,
                       reporter: StepReporter | None = None):
    """Re-run a generated asset from its manifest. Returns (asset_dicts, errors).

    The manifest is the spec (originshot_pipelines/replay.py): prompt, model, seed and
    params come from the stored record, never from the current prompt builders. The one
    substitution is the reference image — the recorded presign expired long ago, so the
    anchored authentic original is re-presigned by content hash instead.

    Replay refuses outside real-generation mode: the mock fabricates passthrough copies,
    and a passthrough copy presented as "the manifest, re-executed" would be the exact
    lie this feature exists to make impossible.
    """
    from originshot_pipelines import replay as replay_mod

    reporter = reporter or _NullReporter()
    style = Style(source_asset["style"])
    settings = get_settings()

    mode = generation_mode()
    if mode != "genblaze":
        reason = (
            "replay executes the recorded spec against the real provider — the dev mock "
            "cannot honor a manifest"
            if mode == "mock"
            else "Generation is not configured — missing: "
            + ", ".join(missing_generation_requirements())
        )
        reporter.skip(style, reason)
        return [], [f"{style.value}: {reason}"]

    reporter.start(style)
    try:
        manifest = _load_manifest_json(source_asset.get("manifest_key"), storage)
        spec = replay_mod.parse_manifest_step(manifest)

        from originshot_pipelines import storage as sink_module

        source_uri = storage.presigned_get(original["b2_key"])
        res = await replay_mod.build_replay_pipeline(spec, source_uri).arun(
            sink=sink_module.make_sink(), timeout=settings.image_timeout_seconds
        )
        asset = _map(sku, res, style, original["sha256"], storage)
        asset["replay_of"] = source_asset["sha256"]

        # Score once, no retry: a fresh generation retries because its promise is "produce
        # the style"; a replay's promise is "this exact spec", and re-rolling until QA is
        # happier would be a different spec wearing the replay's name.
        if settings.qa_enabled:
            vlm_call = _make_vlm_call(settings)
            ref_bytes = None
            if vlm_call is not None:
                try:
                    ref_bytes = _fetch_bytes(source_uri)
                except Exception as e:  # noqa: BLE001 — QA degrades, replay proceeds
                    log.warning("QA reference fetch failed (%s); VLM tier disabled", e)
            _score_batch(style, [asset], storage,
                         reference=ref_bytes, vlm_call=vlm_call, attempt=1)

        reporter.finish(style, [asset])
        return [asset], []
    except Exception as e:  # noqa: BLE001
        reporter.fail(style, str(e))
        return [], [f"{style.value}: {e}"]


def _load_manifest_json(manifest_key: str | None, storage) -> dict:
    """Fetch and parse the sidecar manifest an asset points at.

    `manifest_key` is our own B2 key in the common case, but the sink may have recorded a
    full URI (generation._map prefers `manifest.manifest_uri` when the sink set one) — so
    recover a bucket key from a URL when possible and only fetch over HTTP as a last
    resort. Raises ReplayUnavailable with the precise reason; replay must explain itself.
    """
    import json

    from originshot_pipelines.replay import ReplayUnavailable

    if not manifest_key:
        raise ReplayUnavailable("asset has no stored manifest")
    key = key_from_url(manifest_key) or manifest_key
    try:
        if key.startswith(("http://", "https://")):
            data = _fetch_bytes(key)
        else:
            data = storage.get_bytes(key)
    except Exception as e:  # noqa: BLE001
        raise ReplayUnavailable(f"stored manifest could not be read ({e})") from e
    try:
        return json.loads(data)
    except Exception as e:  # noqa: BLE001
        raise ReplayUnavailable("stored manifest is not valid JSON") from e


def _make_vlm_call(settings):
    """The injected VLM transport for qa.evaluate_image, or None when unavailable."""
    if not (settings.qa_enabled and settings.qa_vlm_enabled and settings.gmi_api_key):
        return None
    from functools import partial

    from originshot_pipelines import qa
    from originshot_pipelines.registry import GMI_CHAT_BASE_URL, QA_VISION_MODEL

    return partial(
        qa.vlm_product_match,
        api_key=settings.gmi_api_key,
        base_url=GMI_CHAT_BASE_URL,
        model=QA_VISION_MODEL,
        timeout=settings.qa_vlm_timeout_seconds,
    )


def _asset_bytes(asset: dict, storage) -> bytes | None:
    """Best-effort download of a just-generated asset's media for QA scoring."""
    try:
        url = (storage.presigned_get(asset["b2_key"]) if asset.get("b2_key")
               else asset.get("b2_url"))
        return _fetch_bytes(url) if url else None
    except Exception as e:  # noqa: BLE001
        log.warning("QA byte fetch failed for %s: %s", asset.get("sha256"), e)
        return None


def _score_batch(style: Style, produced: list[dict], storage, *, reference, vlm_call,
                 attempt: int) -> int:
    """Attach a QA report to every asset in the batch; return how many passed.

    An asset whose bytes can't be fetched gets no report (`qa: None`) and counts as
    passed — QA must never punish an asset for our own download hiccup.
    """
    from originshot_pipelines import qa

    passed = 0
    for asset in produced:
        data = _asset_bytes(asset, storage)
        if data is None:
            asset["qa"] = None
            passed += 1
            continue
        report = qa.evaluate_image(data, style.value, reference=reference, vlm_call=vlm_call)
        report["attempt"] = attempt
        asset["qa"] = report
        if report["passed"]:
            passed += 1
    return passed


def _retry_feedback(produced: list[dict]) -> str:
    """The correction to feed a retry, derived from attempt 1's failed QA checks.

    Each failed asset's report is lifted into a Genblaze ``EvaluationResult`` via
    `qa.to_evaluation`, and its ``.feedback`` is read exactly as
    `genblaze_core.agents.AgentLoop` reads `ctx.last_evaluation.feedback` to refine the next
    iteration — this is the generate → evaluate → **refine** step, in the SDK's own vocabulary.
    Fragments are aggregated across the batch and de-duplicated so a four-scene style gets one
    coherent instruction. Falls back to the pure string form if the SDK type is unavailable —
    an evaluator quirk must never cost the retry its guidance.
    """
    from originshot_pipelines import qa

    failed = [a["qa"] for a in produced if a.get("qa") and not a["qa"].get("passed")]
    if not failed:
        return ""
    try:
        # Evaluate step: each failed report becomes a Genblaze EvaluationResult — the SDK's
        # agent verdict, carrying both `.passed` and the structured checks in `.metadata`.
        evaluations = [qa.to_evaluation(report) for report in failed]
        if any(e.feedback for e in evaluations):
            # Refine step: aggregate the corrections off those verdicts, de-duplicated by
            # check, into one instruction for the retry — the same `.feedback`-driven loop
            # `genblaze_core.agents.AgentLoop` runs.
            return qa.feedback_from_reports(
                [{"passed": e.passed, "checks": e.metadata.get("checks", [])}
                 for e in evaluations]
            )
    except Exception:  # noqa: BLE001 — SDK types must never break a retry
        pass
    return qa.feedback_from_reports(failed)


async def _qa_and_maybe_retry(style: Style, runner, produced: list[dict], storage, *,
                              reference, vlm_call, retry: bool) -> list[dict]:
    """Evaluate a style's output; regenerate once *with feedback* if it failed; keep the better.

    Retry is at style granularity because that is the provider-call granularity. The retry is
    **informed**: the specific checks attempt 1 failed (wrong background, product not
    preserved, …) are turned into prompt corrections via `qa.feedback_from_reports` and spliced
    into the retry's prompt — so the second attempt is a correction, not another roll of the
    dice. When both ran, the batch with more passing assets wins (ties → the first attempt, so
    a no-better retry doesn't churn the delivered assets). The losing batch's media stays on B2
    (content-addressed, negligible) but is never registered as an asset document.
    """
    ok1 = _score_batch(style, produced, storage,
                       reference=reference, vlm_call=vlm_call, attempt=1)
    if ok1 == len(produced) or not retry:
        return produced

    feedback = _retry_feedback(produced)
    log.info("QA: %s failed (%d/%d passed) — retrying once with feedback: %s",
             style.value, ok1, len(produced), feedback or "(none derivable)")
    try:
        second = await runner(feedback or None)
    except Exception as e:  # noqa: BLE001 — keep the flagged first batch over a hard fail
        log.warning("QA retry for %s failed to run: %s", style.value, e)
        return produced
    ok2 = _score_batch(style, second, storage,
                       reference=reference, vlm_call=vlm_call, attempt=2)
    winner = second if ok2 > ok1 else produced
    for asset in winner:
        if asset.get("qa") is not None:
            asset["qa"]["attempts"] = 2
            # Record the correction that drove the retry, so the UI can show "passed on
            # attempt 2 (refined: …)" rather than an unexplained second try.
            if winner is second and feedback:
                asset["qa"]["retry_feedback"] = feedback
    return winner


def _map(sku, result, style: Style, parent: str, storage) -> dict:
    # Genblaze data shapes (verified against genblaze-core 0.3.2):
    #   * provider / model / cost live on the *Step*, not the Asset.
    #   * Asset exposes `media_type` (not `mime_type`), `url`, `sha256`, `size_bytes`,
    #     `width`, `height`, `duration` — and has no storage `key`.
    #   * Manifest exposes `canonical_hash`, `manifest_uri`, `verify()`.
    step = result.run.steps[0]
    # In genblaze-core 0.3.2 a failed step (provider error, moderation block, or all
    # fallbacks exhausted) was *returned* with empty `assets` rather than raised, so the
    # caller hit a downstream IndexError instead of the provider's reason.
    # ✅ Fixed upstream as of 0.3.6 (verified 2026-07-19): a failed step now carries
    # status=failed + a populated `error`, and `arun(raise_on_failure=True)` raises
    # PipelineError with the real cause. This guard is kept as belt-and-braces — it is the
    # one place a silent empty-asset result would become a confusing 500.
    if not step.assets:
        reason = getattr(step, "error", None) or getattr(step, "status", None) or "no asset produced"
        raise RuntimeError(str(reason))
    asset = step.assets[0]
    run_id = getattr(getattr(result, "run", None), "run_id", None)
    manifest = getattr(result, "manifest", None)

    manifest_verified = None
    manifest_key = None
    if manifest is not None:
        try:
            manifest_verified = bool(manifest.verify())
        except Exception:  # noqa: BLE001
            manifest_verified = None
        # Prefer the sink-recorded sidecar URI; otherwise persist one ourselves.
        manifest_key = getattr(manifest, "manifest_uri", None) or _persist_manifest(
            storage, run_id or "run", style, manifest
        )

    mime_type = getattr(asset, "media_type", None)
    modality = _modality_for(style, mime_type)
    sink_url = getattr(asset, "url", None)
    out = {
        "sku_id": sku["id"],
        "sha256": getattr(asset, "sha256", None),
        # The Genblaze sink owns the stored object key and returns an unsigned URL. Our
        # bucket is private, so recover the key and let callers presign it; keep the raw
        # URL as a fallback for objects stored outside our bucket.
        "b2_key": key_from_url(sink_url),
        "b2_url": sink_url,
        "modality": modality.value,
        "style": style.value,
        "is_authentic": False,
        "parent_sha256": parent,
        "run_id": run_id,
        "provider": getattr(step, "provider", None),
        "model": getattr(step, "model", None),
        "cost_usd": getattr(step, "cost_usd", None),
        "manifest_key": manifest_key,
        "manifest_verified": manifest_verified,
        "embedded": False,
        "mime_type": mime_type,
        "width": getattr(asset, "width", None),
        "height": getattr(asset, "height", None),
        "duration": getattr(asset, "duration", None),
    }

    # Embed the provenance manifest into the actual media bytes and store the embedded,
    # verifiable deliverable ourselves (content-addressable + presignable). Best-effort:
    # any failure leaves the sink-stored copy + manifest.verify() result untouched.
    if manifest is not None and get_settings().manifest_embed_mode.lower() != "none":
        try:
            _embed_and_store(result, out, storage, mime_type, manifest_key)
        except Exception as e:  # noqa: BLE001
            log.warning("manifest embed failed for %s (%s); using sink copy", style.value, e)

    return out


async def _mux_narrated_video(sku, audio_asset, video_asset, parent, storage, sink) -> dict | None:
    """Mux the narration onto the hero video → a narrated, content-bound MP4 asset (or None).

    Runs the SDK ffmpeg compositor in a real Genblaze pipeline, so the muxed MP4 carries a
    manifest and flows through `_map` like every other asset — content-addressable storage,
    an embedded manifest the strip-and-rehash path can bind (MP4 is supported), and a ledger
    entry. Returns None when ffmpeg is unavailable or an input can't be fetched; the caller
    still ships the standalone narration audio, so a missing mux is a graceful degradation,
    never a failed style.

    The inputs are fetched to a temp dir because the compositor and the pre-loop both need
    local files; the muxed output is uploaded to B2 by the pipeline's sink before `_map`
    re-reads it, so the temp dir is gone by the time the asset is finalized.
    """
    import tempfile
    from pathlib import Path

    from originshot_pipelines import voiceover as vo

    ffmpeg = vo.ffmpeg_binary()
    if not ffmpeg:
        log.info("narrated video skipped: no ffmpeg (system or bundled) available")
        return None

    def _url(a: dict) -> str | None:
        return storage.presigned_get(a["b2_key"]) if a.get("b2_key") else a.get("b2_url")

    v_url, a_url = _url(video_asset), _url(audio_asset)
    if not (v_url and a_url):
        log.info("narrated video skipped: missing a source URL for mux")
        return None

    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        (tmpd / "hero.mp4").write_bytes(_fetch_bytes(v_url))
        (tmpd / "narration.mp3").write_bytes(_fetch_bytes(a_url))
        looped = tmpd / "hero_looped.mp4"
        vo.loop_video_to_ceiling(tmpd / "hero.mp4", looped, ffmpeg=ffmpeg)
        pipe = vo.build_narrated_pipeline(
            looped.resolve().as_uri(),
            (tmpd / "narration.mp3").resolve().as_uri(),
            ffmpeg=ffmpeg,
            output_dir=str(tmpd),
            video_sha256=video_asset.get("sha256"),
            audio_sha256=audio_asset.get("sha256"),
        )
        res = await pipe.arun(sink=sink, timeout=get_settings().video_timeout_seconds)

    asset = _map(sku, res, Style.voiceover, parent, storage)
    # Lineage: the narrated video is derived from two individually provenance-tracked assets.
    asset["muxed_from"] = [video_asset.get("sha256"), audio_asset.get("sha256")]
    return asset


def _modality_for(style: Style, mime_type: str | None) -> Modality:
    """Modality from the produced media type, with the style as a fallback.

    Media-type first so an asset is classified by what it actually *is* (a provider that
    returns audio/mpeg is audio regardless of style bookkeeping); style covers the case where
    the SDK didn't report a media type.
    """
    mt = (mime_type or "").lower()
    if style is Style.voiceover or mt.startswith("audio/"):
        return Modality.audio
    if style is Style.video or mt.startswith("video/"):
        return Modality.video
    return Modality.image


def _ext_for(mime_type: str | None) -> str:
    return {
        "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
        "video/mp4": ".mp4",
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav",
        "audio/x-wav": ".wav", "audio/aac": ".aac", "audio/flac": ".flac",
        "audio/opus": ".opus", "audio/ogg": ".ogg",
    }.get((mime_type or "").lower(), ".bin")


def _fetch_bytes(url: str) -> bytes:
    """Download generated media bytes (monkeypatched in tests)."""
    import httpx

    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def _embed_and_store(result, out: dict, storage, mime_type: str | None, manifest_key) -> None:
    """Embed `result.manifest` into the media, store it via our storage, and re-verify.

    Mutates `out` in place: sets b2_key (our content-addressable key), clears b2_url,
    refreshes sha256 to the embedded bytes, and sets manifest_verified/embedded.
    """
    import hashlib
    import tempfile
    from pathlib import Path

    from originshot_pipelines import provenance

    from .storage import storage_key

    # Presign when the sink stored into our own (private) bucket — the raw sink URL 403s.
    key = out.get("b2_key")
    url = storage.presigned_get(key) if key else out.get("b2_url")
    if not url:
        return
    data = _fetch_bytes(url)

    # Perceptual hash for "Verify in the Wild" — computed here, from the pixels, so a later
    # marketplace re-encode that strips the manifest can still be matched back to this asset.
    # Taken from the pre-embed bytes on purpose: embedding writes a metadata chunk (PNG iTXt /
    # JPEG APP1 / WebP XMP) and does not touch pixels, so this pHash equals the delivered
    # file's, and it is recorded even if the embed step below fails. Images only — a pHash of
    # a video frame would be a single-frame claim the feature can't stand behind.
    if (mime_type or "").lower().startswith("image/"):
        from originshot_pipelines import perceptual
        out["phash"] = perceptual.phash(data)

    mode = get_settings().manifest_embed_mode.lower()
    ext = _ext_for(mime_type)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"asset{ext}"
        path.write_bytes(data)
        sidecar_uri = storage.presigned_get(manifest_key) if manifest_key else None
        provenance.embed_manifest(result, path, mode=mode, sidecar_uri=sidecar_uri)
        embedded_bytes = path.read_bytes()
        verified = provenance.extract_and_verify(path, mime_type or "")

    sha = hashlib.sha256(embedded_bytes).hexdigest()
    key = storage_key(sha, ext)
    storage.put_bytes(key, embedded_bytes, mime_type or "application/octet-stream")
    out.update({
        "b2_key": key,
        "b2_url": None,
        "sha256": sha,
        "manifest_verified": verified,
        "embedded": True,
    })


def _persist_manifest(storage, run_id: str, style: Style, manifest) -> str | None:
    """Best-effort: write a sidecar manifest JSON to B2 (prompts redacted by EmbedPolicy)."""
    try:
        data = None
        # Manifest API (genblaze-core 0.3.2): canonical JSON is the provenance source of
        # truth; fall back to plain pydantic serialization if unavailable.
        to_canonical = getattr(manifest, "to_canonical_json", None)
        if callable(to_canonical):
            data = to_canonical()
        elif hasattr(manifest, "model_dump_json"):
            data = manifest.model_dump_json()
        if data is None:
            return None
        if isinstance(data, str):
            data = data.encode("utf-8")
        key = f"manifests/{run_id}/{style.value}.json"
        storage.put_bytes(key, data, "application/json")
        return key
    except Exception as e:  # noqa: BLE001
        log.warning("manifest persist failed: %s", e)
        return None
