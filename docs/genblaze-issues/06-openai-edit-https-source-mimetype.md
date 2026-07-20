# `genblaze-openai` image edits reject every remote (https) source: the download is saved with a `.img` suffix OpenAI can't type

**Package versions:** `genblaze` 0.4.3, `genblaze-core` 0.3.6, `genblaze-openai` 0.3.2.
Python 3.12 (platform-independent).
**Provider:** OpenAI images (`openai-dalle` / `DalleProvider`), `/v1/images/edits` path.

## Summary

`DalleProvider` cannot perform an image **edit** when the reference image is an `https://`
URL — which is the normal case whenever the source lives in object storage and is passed as a
presigned URL. The provider downloads the remote image to a temp file created with a fixed
`.img` suffix, and the OpenAI client infers the upload's MIME type from that filename. `.img`
is unknown, so the request goes out as `application/octet-stream` and the API rejects it:

```
OpenAI image edit failed: Error code: 400 -
  {'error': {'message': "Invalid file 'image': unsupported mimetype ('application/octet-stream').
    Supported file formats are 'image/jpeg', 'image/png', and 'image/webp'.",
   'type': 'invalid_request_error', 'param': 'image', 'code': 'unsupported_file_mimetype'}}
```

### Reproduction

```python
import asyncio
from genblaze_core import Modality, Pipeline
from genblaze_core.models.asset import Asset
from genblaze_openai import DalleProvider

ref = Asset(url="https://<any-host>/product.png", media_type="image/png")  # a real reachable PNG
pipe = Pipeline("edit").step(
    DalleProvider(), model="gpt-image-1", modality=Modality.IMAGE,
    prompt="Place this product on a sunlit kitchen counter.",
    external_inputs=[ref], size="1024x1024", input_fidelity="high",
)
asyncio.run(pipe.arun(timeout=120, raise_on_failure=False))
# -> 400 unsupported mimetype ('application/octet-stream')
```

A `file://` source with a real extension (e.g. `…/product.png`) works, because that path
keeps its true suffix — so the bug is specific to the https download path.

## Root cause

In `dalle.py`, `_download_https_to_temp` creates the temp file with a hardcoded suffix:

```python
fd, tmp = tempfile.mkstemp(suffix=".img")
```

The downloaded bytes are correct; only the filename is wrong, and the OpenAI SDK's multipart
upload derives the part's `Content-Type` from that filename. `Asset.media_type` (here
`image/png`) is already available on the input and is the authoritative type — it is simply
not consulted when naming the temp file.

## Suggested fix

Name the temp file from the input's declared media type (falling back to sniffing the first
bytes if absent):

```python
_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
suffix = _EXT.get((asset.media_type or "").lower(), ".png")
fd, tmp = tempfile.mkstemp(suffix=suffix)
```

`_materialize_inputs` already has the `Asset` in hand, so the media type can be threaded into
the download helper with no signature churn beyond one argument.

## Impact

Any edit whose source is a presigned/object-storage URL fails — i.e. essentially every
production image-edit workflow that stores originals in S3/B2/GCS. We worked around it by
staging the source to a local temp file with a truthful extension before calling the
provider, but the fix belongs in the connector: the type is knowable from `Asset.media_type`
it already receives.
