"""Replay — executable provenance: re-run a generation from its own manifest.

Everything else provenance does in this project is retrospective — it proves how an
existing file was made. Replay points the same record forward: the manifest carries the
complete step spec (provider, model, prompt, seed, params), so it can *drive* a new run
instead of merely describing an old one. "Any asset can be regenerated or audited from
its manifest" stops being a claim about intent and becomes a button.

Two deliberate departures from a fresh generation:

  * **The spec comes from the manifest, verbatim.** The prompt is read from the stored
    manifest, never rebuilt from the current prompt templates — if the templates have
    changed since the original run, a replay still runs the *original* words. That is the
    entire point: reproducibility against the record, not against today's code.
  * **No fallback chain.** A fresh generation is allowed to degrade to a fallback model,
    because its promise is "produce the style". A replay's promise is "this exact spec" —
    an output quietly served by a different model would contradict the very manifest being
    replayed, so `fallback_models` recorded in the params is stripped and the run fails
    loudly if the recorded model is gone.

The one thing that cannot be replayed verbatim is the reference-image parameter: the
manifest recorded a presigned URL that expired minutes after the run. The replay
re-presigns the same *content* instead — the asset's `parent_sha256` resolves to the
anchored authentic original, which is a stronger binding than any URL (the bytes are
identified by hash, not by where they happened to live). Video assets are excluded for
exactly this reason: their input was a generated intermediate (the hero frame), not the
anchored original, so the source an honest replay needs is not hash-resolvable from the
asset's lineage.

Determinism is NOT claimed. The seed is carried when the manifest has one, but providers
do not guarantee bit-identical output even seeded — a replay reproduces the *run*, and the
new asset gets its own hash, manifest and ledger entry rather than pretending to be the
old one.
"""
from __future__ import annotations

from .registry import REFERENCE_IMAGE_KWARG


class ReplayUnavailable(RuntimeError):
    """This manifest cannot drive a new run. The message states exactly why."""


# Keys in the recorded params that must not be copied into a replay step:
# the reference-image URL is expired (re-presigned by the caller), and the fallback chain
# would let a replay silently run on a model other than the one it claims to replay.
_STRIPPED_PARAM_KEYS = {"image", "image_url", REFERENCE_IMAGE_KWARG, "fallback_models"}


def parse_manifest_step(manifest: dict) -> dict:
    """Extract the replayable step spec from a canonical manifest JSON document.

    Returns {model, prompt, negative_prompt, seed, params, provider, source_run_id}.
    Raises ReplayUnavailable when the manifest cannot honestly specify a new run — the
    caller surfaces the reason instead of falling back to the current prompt builders,
    which would be a fresh generation wearing a replay's name.
    """
    run = manifest.get("run") or {}
    steps = run.get("steps") or []
    if not steps:
        raise ReplayUnavailable("manifest records no steps")
    step = steps[0] or {}

    model = step.get("model")
    if not model:
        raise ReplayUnavailable("manifest step records no model")

    prompt = step.get("prompt")
    if not prompt:
        # `pointer`/`none` embed modes redact prompts (EmbedPolicy); a sidecar written that
        # way describes the run but cannot re-specify it.
        raise ReplayUnavailable(
            "manifest was stored without the prompt (redacted embed policy) — "
            "replay needs the full spec"
        )

    modality = str(step.get("modality") or "image").lower()
    if modality != "image":
        raise ReplayUnavailable(f"only image steps can be replayed (this step is {modality})")

    params = {k: v for k, v in dict(step.get("params") or {}).items()
              if k not in _STRIPPED_PARAM_KEYS}
    return {
        "model": model,
        "prompt": prompt,
        "negative_prompt": step.get("negative_prompt"),
        "seed": step.get("seed"),
        "params": params,
        "provider": step.get("provider"),
        "source_run_id": run.get("run_id"),
    }


def build_replay_pipeline(spec: dict, source_image_uri: str, *, provider=None):
    """Return a Genblaze Pipeline that re-runs `spec` against a fresh source presign.

    `provider` may be injected for testing; otherwise the GMI Cloud image provider is used
    (the only provider whose manifests this instance issues today).
    """
    from genblaze_core import Modality, Pipeline

    if provider is None:
        from genblaze_gmicloud import GMICloudImageProvider

        provider = GMICloudImageProvider()

    step_kwargs = {
        **spec["params"],
        "model": spec["model"],
        "prompt": spec["prompt"],
        "modality": Modality.IMAGE,
        REFERENCE_IMAGE_KWARG: source_image_uri,
    }
    if spec.get("negative_prompt"):
        step_kwargs["negative_prompt"] = spec["negative_prompt"]
    if spec.get("seed") is not None:
        step_kwargs["seed"] = spec["seed"]
    return Pipeline("originshot-replay").step(provider, **step_kwargs)
