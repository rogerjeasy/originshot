# JPEG and WebP manifest embedding re-encodes the image through Pillow, breaking content-binding (PNG does not)

**Package versions:** `genblaze` 0.4.3, `genblaze-core` 0.3.6 (the GitHub v0.5.0 release).
Python 3.12, Pillow 11, Windows.

## Summary

`get_handler(mime).embed(path, manifest)` **decodes and re-encodes** the image for JPEG and
WebP. The original bytes are destroyed, so stripping the manifest back out cannot recover the
bytes the manifest committed to — which makes it impossible to prove that the delivered pixels
are the ones the manifest was signed for.

`PngHandler` is the counter-example and the model to follow: it splices an `iTXt` chunk into
the raw byte stream and never opens the image.

| Handler | Approach | Byte-preserving |
|---|---|---|
| `PngHandler` (`media/png.py:154-157`) | `read_media_bytes()` → `_embed_chunks()` → write | ✅ yes |
| `JpegHandler` (`media/jpeg.py:110-122`) | `Image.open()` → `img.save(..., quality="keep")` | ❌ no |
| `WebpHandler` (`media/webp.py:84-85`) | `Image.open()` → `img.save(..., lossless=…, quality=…)` | ❌ no |

## Reproduction

Embed through the real handler and compare decoded pixels before and after. Source is an
actual 1024×1024 product photograph (not a synthetic pattern — a smooth photo is the *kind*
case for both codecs):

```python
from genblaze_core.media import get_handler
from genblaze_core.models import Manifest
from genblaze_core.models.run import Run

buf = io.BytesIO(); im.save(buf, fmt, **kw); orig = buf.getvalue()
p.write_bytes(orig)
get_handler(mime).embed(p, Manifest(run=Run(run_id="repro-1")))
after = p.read_bytes()
assert pixels(orig) == pixels(after)
```

Result on `genblaze-core` 0.3.6:

| Format | decoded pixels identical | bytes | drift |
|---|---|---|---|
| PNG  | ✅ True  | 336 999 → 337 469 | 0 / 1 048 576 subpixels |
| JPEG | ❌ False | 74 498 → 75 366 | 8 069 / 1 048 576 subpixels, max Δ 5 |
| WEBP | ❌ False | 29 174 → 30 732 | 170 077 / 1 048 576 subpixels, max Δ 12 |

JPEG's `quality="keep"` preserves the quantization tables and so keeps the drift small, but it
is **not** zero — the round-trip is still lossy, which is all that matters for a hash. WebP is
far worse: with a lossy source the handler re-encodes at the handler's own `quality`, so ~16%
of subpixels move.

## Impact

Any workflow that needs "these exact pixels are the ones this manifest describes" can only use
the PNG path. Since a manifest that can be detached or re-signed proves nothing,
content-binding is the property that makes embedded provenance meaningful at all — so this
silently removes the guarantee for two of the four supported image formats.

It is also silent: `embed()` succeeds, `manifest.verify()` still returns `True` (the manifest is
internally consistent), and nothing indicates the committed bytes are gone. A caller only
discovers it by independently re-hashing, which is precisely the check most callers will assume
the SDK already did.

## Workaround

We inject the manifest byte-preservingly ourselves — JPEG via an `APP1` XMP segment, WebP via a
RIFF `XMP ` chunk — leaving the original bytes untouched so a downstream strip recovers them
exactly. Happy to open a PR porting either writer upstream if that would be useful.

## Expected

JPEG and WebP embedding writes the metadata segment/chunk into the existing container without
decoding the image data, matching the PNG (`iTXt`) and MP4 (`uuid` box) behaviour. Both formats
support this: JPEG takes an `APP1` segment after `SOI`, and WebP is a RIFF container that takes
an `XMP ` chunk (converting a simple-format `VP8`/`VP8L` file to extended `VP8X` first).

Failing that, `embed()` should refuse — or at minimum warn loudly — when the chosen format
cannot preserve the committed bytes, rather than reporting success.
