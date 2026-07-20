"""SDK lock-in for the OpenAI image path — the same drift guard as test_sdk_integration.py.

Separate file (rather than appended to the GMI one) so an OpenAI-only deployment that never
installs `genblaze-gmicloud` still runs these, and vice versa.

What drifts here is not model *names* but the **size enum**. `gpt-image-1` accepts only a
fixed set of sizes and `_validate_params` raises `ProviderError` on anything else — so if
OpenAI retires a size, our aspect→size mapping starts failing every run at submit time. That
is a CI failure worth having, not a production one.
"""
import pytest

pytest.importorskip("genblaze_openai")

from originshot_pipelines import providers, registry  # noqa: E402


def _spec():
    from genblaze_openai.dalle import _MODELS

    return _MODELS.get(registry.OPENAI_IMAGE_EDIT_MODEL)


def test_our_openai_model_is_known_to_the_connector():
    """A known model gets validated params; an unknown one silently uses _DEFAULT_SPEC."""
    assert _spec() is not None, registry.OPENAI_IMAGE_EDIT_MODEL


def test_our_model_supports_input_fidelity():
    """`input_fidelity=high` is the only reason this provider is viable here.

    On a model where it is unsupported the SDK downgrades to a warning and forwards it
    anyway, so the run would succeed while quietly dropping product-identity preservation —
    exactly the silent failure this app cannot tolerate. (gpt-image-1-mini is such a model,
    which is why it is not our default.)
    """
    assert _spec().supports_input_fidelity is True


def test_every_size_we_can_emit_is_accepted_by_the_model():
    """Our whole aspect vocabulary must map into the model's fixed size enum."""
    fixed = _spec().fixed_sizes
    assert fixed is not None, "gpt-image-1 is expected to use a fixed size enum"

    emitted = {providers.openai_size_for(a) for a in registry.ASPECT.values()}
    emitted.add(providers.openai_size_for("anything-unmapped"))  # the default
    unknown = emitted - set(fixed)
    assert not unknown, f"sizes not accepted by {registry.OPENAI_IMAGE_EDIT_MODEL}: {unknown}"


def test_our_quality_value_is_accepted():
    assert registry.OPENAI_IMAGE_QUALITY in _spec().valid_qualities


def test_the_connector_forwards_every_param_we_send():
    """Params outside the connector's forward list never reach OpenAI.

    They would still be recorded in the provenance manifest, so a silently-dropped param is
    a manifest describing a run that did not happen.
    """
    from genblaze_openai.dalle import DalleProvider

    kwargs = providers.OpenAIAdapter().build_kwargs(
        providers.ImageEditRequest(
            prompt="p", source_uri="https://example.com/a.png", aspect="4:5",
        )
    )
    # Params the adapter emits that the connector must actually forward to the API.
    forwarded = {"size", "quality", "input_fidelity"}
    provider = DalleProvider(api_key="test-not-used")

    class _Step:
        model = registry.OPENAI_IMAGE_EDIT_MODEL
        prompt = "p"
        params = {k: v for k, v in kwargs.items() if k in forwarded}

    built = provider._build_request_params(_Step(), _spec())
    for key in forwarded:
        assert key in built, f"{key} is dropped before the request leaves the SDK"


def test_edit_routing_depends_on_step_inputs():
    """Documents the contract the adapter is built around, so a future change trips here.

    DalleProvider.generate routes on `bool(step.inputs)`. If that ever becomes param-driven,
    OpenAIAdapter.build_kwargs must change with it — otherwise every "edit" silently becomes
    a text-to-image render of a product nobody photographed.
    """
    import inspect

    from genblaze_openai.dalle import DalleProvider

    src = inspect.getsource(DalleProvider.generate)
    assert "step.inputs" in src
