# `validate_model()` returns `ok_authoritative` for a model that 404s, and `unknown_permissive` for one that works

**Package versions:** `genblaze` 0.4.3, `genblaze-core` 0.3.6, `genblaze-gmicloud` 0.3.3
(the GitHub v0.5.0 release). Python 3.12, Windows.
**Provider:** GMI Cloud, image models, via the request-queue API.

## Summary

For our GMI Cloud account, `BaseProvider.validate_model()` is **inverted**: the model that
genuinely works reports as unvalidated, and a model that 404s on every real submit reports
with the SDK's strongest verdict.

```python
from genblaze_gmicloud import GMICloudImageProvider
p = GMICloudImageProvider()

p.validate_model("seededit-3-0-i2i-250628")    # -> ok_authoritative      ← 404s on submit
p.validate_model("gemini-3-pro-image-preview") # -> unknown_permissive    ← works fine
p.validate_model("totally-made-up-model-xyz")  # -> unknown_permissive    ← does not exist
p.validate_model("reve-edit-20250915")         # -> not_found
```

Two distinct problems:

1. **`ok_authoritative` is wrong for `seededit-3-0-i2i-250628`.** Per `providers/base.py`
   that outcome means "user-registered, NATIVE-discovery-confirmed". Submitting to it
   returns 404 from `.../ie/requestqueue/.../requests`. Preflight is silent for this
   outcome, so the failure only appears at generation time — after the job is queued and
   the user is waiting.

2. **A real model and a fabricated model are indistinguishable.** Both
   `gemini-3-pro-image-preview` (which serves all of our production traffic) and a
   nonsense string return `unknown_permissive`. So the outcome carries no signal for the
   models an account actually uses, and the preflight WARN it emits is noise we had to
   learn to ignore — which is exactly when a real warning gets missed.

## Impact

We build a product whose entire claim is verifiable provenance, so "which models can this
account actually call?" is a question we must answer *before* spending a user's credit. We
lost most of a day to `seededit`/`reve-*`: they appear in `build_image_registry().known()`,
they run in the GMI **console playground**, and `validate_model()` blessed one of them —
but all of them 404 through the API. We now treat validation as unreliable and keep an
`IMAGE_EDIT_FALLBACKS` list that is deliberately empty, because the only evidence we trust
is a real generation.

## Expected

Either an outcome that distinguishes "this account can call this model" from "this string
looks plausible", or explicit documentation that `validate_model()` is a name-shape check
and not an entitlement check. A dedicated `list_available_models()` scoped to the
authenticated account would solve this cleanly — the console clearly has that information.

## Notes

`build_image_registry().get()` also returns a `ModelSpec` for arbitrary unknown strings
(`get("reve-edit-v1")` → a spec, though only `reve-edit-20250915` is in `known()`), so
`.get()` is not a usable existence check either.
