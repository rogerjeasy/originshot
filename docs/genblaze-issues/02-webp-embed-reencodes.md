# WebP manifest embedding re-encodes the image, breaking content-binding (JPEG was fixed, WebP wasn't)

**Package versions:** `genblaze` 0.4.3, `genblaze-core` 0.3.6 (the GitHub v0.5.0 release).
Python 3.12, Pillow 11, Windows.

## Summary

`PipelineResult.save(path, embed=True, policy=EmbedPolicy(embed_mode="full"))` re-encodes
WebP files through Pillow. The original bytes are destroyed, so stripping the manifest back
out cannot recover the bytes the manifest committed to — which makes it impossible to prove
that a WebP's pixels are the ones its manifest was signed for.

PNG and JPEG both round-trip correctly. **JPEG appears to have been fixed since 0.3.2**
(thank you) — WebP was not.

## Reproduction

Embed with the SDK, then strip the manifest and compare against the pre-embed hash:

```python
original = <bytes of a WebP>
want = hashlib.sha256(original).hexdigest()

path.write_bytes(original)
result.save(path, embed=True, policy=EmbedPolicy(
    prompt_visibility=PromptVisibility.PUBLIC, embed_mode="full",
    include_params=True, include_seed=True))

got = strip_manifest_and_hash(path)   # recompute the canonical content hash
assert got == want
```

Result on 0.3.6:

| Format | strip-and-rehash recovers original | decoded pixels identical |
|---|---|---|
| PNG  | ✅ True  | ✅ True |
| JPEG | ✅ True  | ✅ True |
| WEBP | ❌ False | ❌ **False** |

The pixel column matters: for WebP this is not just a container rewrite, it is a lossy
re-encode. The delivered image is not the image that was generated.

## Impact

Any workflow that needs "these exact pixels are the ones this manifest describes" cannot
use the SDK's WebP path. Since a manifest that can be detached or re-signed proves nothing,
content-binding is the property that makes embedded provenance meaningful at all — so this
silently removes the guarantee for one of the four supported formats.

It is also silent: `save()` succeeds, `manifest.verify()` still returns `True` (the manifest
is internally consistent), and nothing indicates the committed bytes are gone. A caller only
discovers it by independently re-hashing.

## Workaround

We inject the manifest byte-preservingly ourselves — JPEG via an `APP1` XMP segment, WebP
via a RIFF `XMP ` chunk — leaving the original bytes untouched so a downstream strip
recovers them exactly. Happy to open a PR porting the WebP RIFF-chunk writer upstream if
that would be useful.

## Expected

WebP embedding writes the `XMP ` chunk into the existing RIFF container without decoding
and re-encoding the image data, matching the PNG (`iTXt`) and MP4 (`uuid` box) behaviour.
Failing that, `save()` should refuse or warn loudly when the chosen format cannot preserve
the committed bytes, rather than reporting success.
