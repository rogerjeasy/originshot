"""Week-1 SDK lock-in: assert our registry IDs/kwargs match the *installed* Genblaze SDK.

These tests skip cleanly when Genblaze isn't installed (e.g. a minimal dev box), but when it
is, they fail loudly if a model ID, the reference-image kwarg, or a result-shape assumption
drifts from reality — so the placeholders that bit us in Week 1 can't silently come back.
"""
import pytest

pytest.importorskip("genblaze")
pytest.importorskip("genblaze_gmicloud")

from originshot_pipelines import registry  # noqa: E402


def _image_ids():
    from genblaze_gmicloud.models import build_image_registry

    return set(build_image_registry().known())


def _video_ids():
    from genblaze_gmicloud.models import build_video_registry

    return set(build_video_registry().known())


def _allows(spec, kwarg: str) -> bool:
    """True if a ModelSpec permits `kwarg`.

    A `param_allowlist` of None means the SDK doesn't restrict params for that model
    (permissive) — which is exactly the case for `gemini-3-pro-image-preview` and is *why*
    passing `image`/`aspect_ratio` succeeds against the live request-queue API.
    """
    allow = getattr(spec, "param_allowlist", None)
    return allow is None or kwarg in allow


def test_image_model_resolves_in_gmi_sdk():
    """Our image model must resolve to a usable ModelSpec via the GMI SDK.

    NOTE: `gemini-3-pro-image-preview` is RUNTIME-VERIFIED (it accepts a reference `image` +
    prompt on the live request-queue API) but is *not* in the SDK's static catalog
    (`build_image_registry().known()` lists only the seededit/reve models, which 404 for our
    account — see registry.py). So we assert `.get()` returns a spec, not catalog membership.
    """
    from genblaze_gmicloud.models import build_image_registry

    spec = build_image_registry().get(registry.IMAGE_EDIT_MODEL)
    assert spec is not None, registry.IMAGE_EDIT_MODEL
    # Any declared fallbacks, if we add them later, MUST be in the static catalog.
    ids = _image_ids()
    for m in registry.IMAGE_EDIT_FALLBACKS:
        assert m in ids, m


def test_video_model_ids_exist_in_gmi_registry():
    ids = _video_ids()
    assert registry.VIDEO_MODEL in ids, registry.VIDEO_MODEL
    assert registry.TEXT2VIDEO_MODEL in ids, registry.TEXT2VIDEO_MODEL
    for m in registry.VIDEO_FALLBACKS:
        assert m in ids, m


def test_reference_image_kwarg_is_allowlisted():
    """Both image and video models must accept the kwarg we pass the source image as."""
    from genblaze_gmicloud.models import build_image_registry, build_video_registry

    img = build_image_registry().get(registry.IMAGE_EDIT_MODEL)
    vid = build_video_registry().get(registry.VIDEO_MODEL)
    assert _allows(img, registry.REFERENCE_IMAGE_KWARG)
    assert _allows(vid, registry.REFERENCE_IMAGE_KWARG)
    assert _allows(img, "aspect_ratio")
    assert _allows(vid, "duration")


async def test_manifest_embed_extract_verify_roundtrip(tmp_path):
    """Real embed → extract → verify on a PNG, exercising provenance.py end-to-end."""
    from genblaze import Modality, Pipeline
    from genblaze import MockProvider
    from PIL import Image

    from originshot_pipelines import provenance

    png = tmp_path / "shot.png"
    Image.new("RGB", (48, 48), (180, 60, 60)).save(png, format="PNG")
    before = png.read_bytes()

    pipe = Pipeline("t").step(MockProvider(), model="m", prompt="p", modality=Modality.IMAGE)
    pipe.preflight = False
    res = await pipe.arun(timeout=30, raise_on_failure=False)

    # "full" mode embeds a self-contained, standalone-verifiable manifest.
    embres = provenance.embed_manifest(res, png, mode="full")
    assert embres is not None
    assert png.read_bytes() != before, "embedding should change the file bytes"
    assert provenance.extract_and_verify(png, "image/png") is True
    # "none" mode is a no-op.
    assert provenance.embed_manifest(res, png, mode="none") is None


async def test_studio_builder_runs_with_mock_provider():
    """The real studio builder + Pipeline API produce a verifiable manifest."""
    from genblaze import MockProvider

    from originshot_pipelines import studio

    pipe = studio.build_studio_pipeline(
        "https://example.com/source.png", "a blue ceramic mug", provider=MockProvider()
    )
    pipe.preflight = False
    res = await pipe.arun(timeout=30, raise_on_failure=False)
    step = res.run.steps[0]
    assert step.assets, "expected at least one asset"
    assert res.manifest.verify() is True
    # The fields generation._map reads must exist on the real objects.
    assert hasattr(step, "provider") and hasattr(step, "model")
    assert hasattr(step.assets[0], "media_type")
