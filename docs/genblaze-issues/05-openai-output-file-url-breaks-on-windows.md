# `genblaze-openai` builds output asset `file://` URLs that are invalid on Windows, breaking the sink and step-chaining

**Package versions:** `genblaze` 0.4.3, `genblaze-core` 0.3.6, `genblaze-openai` 0.3.2.
Python 3.12, Windows 11.
**Provider:** OpenAI images (`openai-dalle` / `DalleProvider`).

## Summary

Every image `DalleProvider` produces is handed back with a `file://` URL constructed as
`f"file://{quote(str(path))}"` (`dalle.py`, `_persist_image_bytes`). On POSIX that yields a
valid `file:///tmp/x.png`. On Windows the absolute path has no leading slash, so the **entire
path becomes the URL's netloc** and `urlparse(url).path` is empty:

```python
from urllib.parse import quote, urlparse
p = r"C:\Users\me\AppData\Local\Temp\x.png"
u = f"file://{quote(str(p))}"
# 'file://C%3A%5CUsers%5Cme%5CAppData%5CLocal%5CTemp%5Cx.png'
urlparse(u).netloc  # 'C%3A%5CUsers%5Cme%5C…'   ← whole path in netloc
urlparse(u).path    # ''                          ← empty
```

Two things downstream then break, and both are load-bearing:

1. **`ObjectStorageSink` cannot upload any OpenAI-generated asset.** The sink resolves the
   empty path against the process CWD, decides the file is "outside allowed directories", and
   refuses the transfer:

   ```
   Asset transfer failed for <id>: Access denied: local file path
   C:\…\backend is outside allowed directories. Files must be under temp or output_dir.
   Run <id>: 1/1 asset transfers failed
   ```

   So a pipeline that generates with OpenAI and stores with `ObjectStorageSink` produces
   nothing on Windows, even though the OpenAI call itself returned `200 OK` and the bytes are
   sitting in a temp file.

2. **The provider's own output can't be chained into a second step.** `validate_chain_input_url`
   rejects a `file://` URL with a non-empty netloc (correctly — see issue below), so feeding
   one `DalleProvider` step's output into another raises
   `file:// URL must have empty or 'localhost' netloc`.

## Root cause

`_persist_image_bytes` (and the edit-input download path, see the companion issue 06) build
the URL by hand with `quote()` instead of using `pathlib.Path.as_uri()`, which is the stdlib
method that produces an RFC-8089-correct `file://` URL on every platform:

```python
from pathlib import Path
Path(r"C:\Users\me\x.png").resolve().as_uri()   # 'file:///C:/Users/me/x.png'  ✓
Path("/tmp/x.png").resolve().as_uri()            # 'file:///tmp/x.png'          ✓ (identical to today on POSIX)
```

Because `as_uri()` is byte-identical to the current output on POSIX, the fix changes nothing
for Linux/macOS deployments (e.g. Cloud Run, Render) and only repairs Windows.

## Suggested fix

In `DalleProvider._persist_image_bytes`, replace

```python
return (f"file://{quote(str(out_path.resolve()))}", sha256_hex, size)
```

with

```python
return (out_path.resolve().as_uri(), sha256_hex, size)
```

The same substitution is needed in the edit-input temp-file handling (issue 06).

## Impact

Local development and any Windows-hosted deployment cannot use `DalleProvider` with
`ObjectStorageSink` or in a multi-step chain at all. We worked around it downstream by
subclassing `DalleProvider` to override `_persist_image_bytes` with `Path.as_uri()`, but the
one-line change above fixes it for everyone at the source.
