import pytest


def test_registry_is_importable_without_genblaze():
    from originshot_pipelines import registry

    assert registry.IMAGE_EDIT_MODEL
    assert registry.VIDEO_MODEL
    assert registry.REFERENCE_IMAGE_KWARG


def test_variant_prompt_builder():
    from originshot_pipelines.variants import build_variant_prompts

    prompts = build_variant_prompts("mug", colors=["red", "blue"], angles=["top"])
    assert len(prompts) == 3
    assert any("red" in p for p in prompts)


def test_presets():
    from originshot_pipelines.presets import get_preset

    amazon = get_preset("amazon")
    assert amazon and amazon.background == "white"


def test_studio_builder_with_injected_provider():
    pytest.importorskip("genblaze_core")  # skips cleanly if SDK not installed
    from originshot_pipelines.studio import build_studio_pipeline

    class FakeProvider:  # minimal stand-in
        pass

    pipeline = build_studio_pipeline("https://example/img.png", "blue mug", provider=FakeProvider())
    assert pipeline is not None
