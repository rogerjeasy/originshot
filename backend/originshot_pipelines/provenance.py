"""Provenance helpers: embed/verify Genblaze manifests + disclosure text.

✅ VERIFIED (genblaze-core 0.3.2; re-verified on 0.3.6 — see the note at the end):
  * Embedding is **explicit, not automatic** — `ObjectStorageSink` has no `embed_policy`.
    The canonical path is `PipelineResult.save(path, embed=True, policy=EmbedPolicy(...))`,
    which uses `SmartEmbedder` (falls back to a sidecar for formats that can't carry one).
  * `EmbedPolicy` rules (enforced by the SDK):
      - `embed_mode="full"`  → embeds the complete manifest; requires NO redaction
        (`prompt_visibility=PUBLIC`, `include_params=True`, `include_seed=True`). The file
        verifies standalone.
      - `embed_mode="pointer"` → embeds `{canonical_hash, manifest_uri}`; allows redaction
        but REQUIRES `manifest.manifest_uri` to be set (full manifest lives at that URI).
  * Extraction handlers are keyed by MIME: `get_handler("image/png").extract(path)`.
    `manifest.verify()` checks the manifest's internal canonical hash, so it stays valid
    after embedding (PNG iTXt / MP4 box additions don't touch the canonical payload).
  * Content-binding: PNG (iTXt) and MP4 (uuid box) embeds are clean appends, so stripping
    the manifest recovers the exact committed bytes. JPEG and WebP were not: both SDK
    handlers re-encoded through Pillow, destroying the committed bytes and making a
    strip-and-rehash check impossible. So `embed_manifest` injects the manifest
    **byte-preservingly** (JPEG APP1 XMP segment / WebP RIFF `XMP ` chunk) in `full` mode,
    leaving the original bytes intact for `canonical_content_hash` to strip back out.

🔁 RE-VERIFIED against genblaze-core 0.3.6 (2026-07-19), SDK `result.save(embed=True)`,
   strip-and-rehash against the pre-embed bytes:
      PNG  → recovers original ✓      JPEG → recovers original ✓ (fixed upstream)
      WEBP → recovers original ✗, and the decoded pixels change (still re-encodes)
   So the JPEG half of our workaround is now redundant and the **WebP half is still
   load-bearing**. Both paths are kept: one code path for both formats is simpler than a
   format-conditional one, it costs nothing, and it keeps content-binding independent of
   which formats the SDK happens to preserve in a given release.
"""
from __future__ import annotations

from pathlib import Path


def policy_for(mode: str):
    """Map our `manifest_embed_mode` setting to an EmbedPolicy (or None for 'none')."""
    from genblaze_core import EmbedPolicy, PromptVisibility

    mode = (mode or "full").lower()
    if mode == "none":
        return None
    if mode == "pointer":
        # Privacy-preserving: file carries only the hash + URI; full manifest stays in B2.
        return EmbedPolicy(prompt_visibility=PromptVisibility.REDACTED, embed_mode="pointer")
    # "full" — self-contained, standalone-verifiable. Full mode forbids redaction.
    return EmbedPolicy(
        prompt_visibility=PromptVisibility.PUBLIC,
        embed_mode="full",
        include_params=True,
        include_seed=True,
    )


def embed_manifest(result, local_path: Path, *, mode: str = "full", sidecar_uri: str | None = None):
    """Embed `result.manifest` into the media file at `local_path` per `mode`.

    For `mode="pointer"`, `sidecar_uri` (a reachable URL to the full manifest) must be
    provided — it is written onto the manifest before embedding. Returns the SDK
    `EmbedResult`, or None when `mode == "none"`.
    """
    policy = policy_for(mode)
    if policy is None:
        return None
    # JPEG/WebP: the SDK handler re-encodes (losing the committed bytes), which would defeat
    # content-binding. In full mode, inject the manifest byte-preservingly so a downstream
    # strip can recover the exact committed bytes. PNG/MP4 (clean appends) use the SDK path.
    if mode.lower() == "full":
        injected = _embed_xmp_preserving(Path(local_path).read_bytes(), result.manifest)
        if injected is not None:
            Path(local_path).write_bytes(injected)
            return None
    if mode.lower() == "pointer" and sidecar_uri:
        result.manifest.manifest_uri = sidecar_uri
    return result.save(local_path, embed=True, policy=policy)


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

try:
    from genblaze_core.media.png import ITXT_KEY as _ITXT_KEY  # genblaze PNG manifest keyword
except Exception:  # noqa: BLE001
    _ITXT_KEY = "genblaze:manifest"

try:
    from genblaze_core.media.mp4 import GENBLAZE_UUID_BYTES as _GENBLAZE_UUID_BYTES
except Exception:  # noqa: BLE001
    import uuid as _uuid

    _GENBLAZE_UUID_BYTES = _uuid.UUID("6d6f6461-6c66-6c6f-7700-000000000001").bytes

# XMP APP1 marker namespace (Adobe standard) + the genblaze manifest tag the SDK writes.
_XMP_APP1_NS = b"http://ns.adobe.com/xap/1.0/\x00"
_GENBLAZE_XMP_TAG = b"<mf:manifest>"
_JPEG_SOI = b"\xff\xd8"


def _strip_png_manifest(data: bytes) -> bytes | None:
    """Return PNG bytes with the genblaze manifest iTXt chunk removed (else None).

    Mirrors the SDK's embed (a single ``genblaze:manifest`` iTXt inserted after IHDR), so
    removing that one chunk recovers the exact pre-embed bytes the manifest committed to.
    Uses only the (frozen) PNG container spec — no private SDK internals.
    """
    import struct

    if not data.startswith(_PNG_SIGNATURE):
        return None
    key = _ITXT_KEY.encode() if isinstance(_ITXT_KEY, str) else _ITXT_KEY
    out = bytearray(_PNG_SIGNATURE)
    pos = len(_PNG_SIGNATURE)
    try:
        while pos < len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            ctype = data[pos + 4:pos + 8]
            total = 12 + length
            payload = data[pos + 8:pos + 8 + length]
            if not (ctype == b"iTXt" and payload.split(b"\x00", 1)[0] == key):
                out += data[pos:pos + total]
            pos += total
    except Exception:  # noqa: BLE001 — malformed PNG ⇒ can't canonicalize
        return None
    return bytes(out)


def _strip_mp4_manifest(data: bytes) -> bytes | None:
    """Return MP4 bytes with the genblaze manifest UUID box removed (else None).

    The SDK appends a single `uuid` box (prefixed with `GENBLAZE_UUID_BYTES`) at EOF and
    never shifts pre-existing bytes, so removing that one box recovers the exact pre-embed
    bytes the manifest committed to. Walks the (stable) ISO-BMFF box structure — handling
    32-bit, 64-bit (`size==1`), and to-EOF (`size==0`) box sizes — and copies every
    non-genblaze top-level box verbatim.
    """
    import struct

    if len(data) < 8 or data[4:8] != b"ftyp":
        return None
    out = bytearray()
    pos, n = 0, len(data)
    try:
        while pos + 8 <= n:
            size32 = struct.unpack(">I", data[pos:pos + 4])[0]
            box_type = data[pos + 4:pos + 8]
            if size32 == 1:
                box_size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            elif size32 == 0:
                box_size = n - pos
            else:
                box_size = size32
            if box_size < 8 or pos + box_size > n:
                out += data[pos:]  # malformed tail — copy verbatim and stop
                break
            is_genblaze = (
                box_type == b"uuid"
                and box_size > 24
                and data[pos + 8:pos + 24] == _GENBLAZE_UUID_BYTES
            )
            if not is_genblaze:
                out += data[pos:pos + box_size]
            pos += box_size
    except Exception:  # noqa: BLE001 — malformed MP4 ⇒ can't canonicalize
        return None
    return bytes(out)


def _strip_jpeg_manifest(data: bytes) -> bytes | None:
    """Return JPEG bytes with the genblaze XMP APP1 segment removed (else None).

    Walks JPEG markers from SOI, dropping only the APP1 (`FFE1`) segment that carries our
    XMP manifest, and stops at SOS so entropy-coded scan data is copied verbatim.
    """
    import struct

    if data[:2] != _JPEG_SOI:
        return None
    out = bytearray(_JPEG_SOI)
    pos, n = 2, len(data)
    try:
        while pos + 4 <= n:
            if data[pos] != 0xFF:
                out += data[pos:]  # not at a marker — copy rest verbatim
                break
            marker = data[pos + 1]
            if marker == 0xDA:  # Start Of Scan — image data runs to EOF
                out += data[pos:]
                break
            seg_len = struct.unpack(">H", data[pos + 2:pos + 4])[0]
            total = 2 + seg_len
            payload = data[pos + 4:pos + total]
            is_ours = (
                marker == 0xE1
                and payload.startswith(_XMP_APP1_NS)
                and _GENBLAZE_XMP_TAG in payload
            )
            if not is_ours:
                out += data[pos:pos + total]
            pos += total
    except Exception:  # noqa: BLE001 — malformed JPEG ⇒ can't canonicalize
        return None
    return bytes(out)


def _embed_jpeg_xmp(data: bytes, xmp: bytes) -> bytes | None:
    """Insert a genblaze XMP APP1 segment right after SOI (byte-preserving), or None."""
    import struct

    if data[:2] != _JPEG_SOI:
        return None
    data = _strip_jpeg_manifest(data) or data  # ensure exactly one genblaze segment
    payload = _XMP_APP1_NS + xmp
    if len(payload) + 2 > 0xFFFF:  # APP1 length field is 16-bit
        return None
    segment = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    return data[:2] + segment + data[2:]


def _webp_chunks_start(data: bytes) -> int | None:
    return 12 if (data[:4] == b"RIFF" and data[8:12] == b"WEBP") else None


def _strip_webp_manifest(data: bytes) -> bytes | None:
    """Return WebP bytes with the genblaze `XMP ` RIFF chunk removed (else None)."""
    import struct

    start = _webp_chunks_start(data)
    if start is None:
        return None
    chunks, out, pos, n = data[start:], bytearray(), 0, len(data) - start
    try:
        while pos + 8 <= n:
            fourcc = chunks[pos:pos + 4]
            size = struct.unpack("<I", chunks[pos + 4:pos + 8])[0]
            total = 8 + size + (size & 1)  # RIFF chunks are word-aligned
            payload = chunks[pos + 8:pos + 8 + size]
            if not (fourcc == b"XMP " and _GENBLAZE_XMP_TAG in payload):
                out += chunks[pos:pos + total]
            pos += total
    except Exception:  # noqa: BLE001 — malformed WebP ⇒ can't canonicalize
        return None
    return b"RIFF" + struct.pack("<I", 4 + len(out)) + b"WEBP" + bytes(out)


def _embed_webp_xmp(data: bytes, xmp: bytes) -> bytes | None:
    """Append a genblaze `XMP ` RIFF chunk and fix the RIFF size (byte-preserving), or None."""
    import struct

    if _webp_chunks_start(data) is None:
        return None
    data = _strip_webp_manifest(data) or data  # ensure exactly one genblaze chunk
    chunk = b"XMP " + struct.pack("<I", len(xmp)) + xmp + (b"\x00" if len(xmp) & 1 else b"")
    body = data[12:] + chunk
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body


def _embed_xmp_preserving(data: bytes, manifest) -> bytes | None:
    """Byte-preservingly embed the manifest as XMP for JPEG/WebP; None for other formats."""
    try:
        from genblaze_core.media.jpeg import MAX_XMP_BYTES, _build_xmp
    except Exception:  # noqa: BLE001 — SDK shape changed; fall back to the SDK embed path
        return None

    is_jpeg = data[:2] == _JPEG_SOI
    is_webp = _webp_chunks_start(data) is not None
    if not (is_jpeg or is_webp):
        return None
    xmp = _build_xmp(manifest.to_canonical_json())
    if len(xmp) > MAX_XMP_BYTES:  # too large for a single metadata segment → SDK sidecar path
        return None
    return _embed_jpeg_xmp(data, xmp) if is_jpeg else _embed_webp_xmp(data, xmp)


def canonical_content_hash(local_path: Path, mime_type: str | None = None) -> str | None:
    """SHA-256 of the media content with any embedded genblaze manifest removed.

    Supported for **PNG** (iTXt), **MP4** (uuid box), and — for files embedded via our
    byte-preserving path — **JPEG** (APP1 XMP) and **WebP** (`XMP ` chunk). Returns None for
    anything else; callers treat None as "couldn't bind from bytes" and fall back to a
    byte-exact stored-record match.
    """
    import hashlib

    data = Path(local_path).read_bytes()
    mime = (mime_type or "").lower()
    stripped: bytes | None = None
    if mime == "image/png" or data.startswith(_PNG_SIGNATURE):
        stripped = _strip_png_manifest(data)
    elif mime == "video/mp4" or (len(data) >= 8 and data[4:8] == b"ftyp"):
        stripped = _strip_mp4_manifest(data)
    elif mime == "image/jpeg" or data[:2] == _JPEG_SOI:
        stripped = _strip_jpeg_manifest(data)
    elif mime == "image/webp" or _webp_chunks_start(data) is not None:
        stripped = _strip_webp_manifest(data)
    if stripped is not None:
        return hashlib.sha256(stripped).hexdigest()
    return None


def verify_file(local_path: Path, mime_type: str | None = None) -> dict:
    """Extract an embedded manifest from a file (sniffing the MIME type if not given),
    verify it, and check content-binding.

    Returns ``{present, verified, content_bound, manifest_hash, manifest_uri}``:
      * ``present``       — a manifest was found in the bytes.
      * ``verified``      — the manifest passes ``verify()`` (internal integrity).
      * ``content_bound`` — True/False if we could recompute the canonical content hash and
                            compare it to the asset hash the manifest commits to; None if we
                            couldn't recompute it (unsupported format / pointer manifest).
    """
    from genblaze_core.media import get_handler, sniff_mime

    none = {"present": False, "verified": False, "content_bound": None,
            "manifest_hash": None, "manifest_uri": None}
    mime = mime_type or sniff_mime(local_path)
    handler = get_handler(mime) if mime else None
    if handler is None:
        return none
    try:
        manifest = handler.extract(local_path)
    except Exception:  # noqa: BLE001 — treat unreadable/absent manifests as not present
        return none
    if manifest is None:
        return none
    try:
        verified = bool(manifest.verify())
    except Exception:  # noqa: BLE001
        verified = False

    # Does the actual content match the asset hash the manifest signed over?
    committed = {
        a.sha256 for step in getattr(manifest.run, "steps", [])
        for a in getattr(step, "assets", []) if getattr(a, "sha256", None)
    }
    content_hash = canonical_content_hash(local_path, mime)
    content_bound = (content_hash in committed) if (content_hash and committed) else None

    return {
        "present": True,
        "verified": verified,
        "content_bound": content_bound,
        "manifest_hash": getattr(manifest, "canonical_hash", None),
        "manifest_uri": getattr(manifest, "manifest_uri", None),
    }


def extract_and_verify(local_path: Path, mime_type: str) -> bool:
    """Convenience wrapper: True only if a manifest is present AND verifies."""
    res = verify_file(local_path, mime_type)
    return bool(res["present"] and res["verified"])


def disclosure_text(*, is_authentic: bool, model: str | None = None,
                    provider: str | None = None, parent_sha256: str | None = None) -> str:
    if is_authentic:
        return "Authentic photo — unedited original. Verifiable via OriginShot manifest."
    parent = (parent_sha256 or "")[:12]
    return (
        f"AI-generated image. Model: {model or 'unknown'} ({provider or 'provider'}). "
        f"Derived from authentic source {parent}. "
        "Provenance verifiable via OriginShot (SHA-256 manifest embedded)."
    )
