"""POST /verify — re-prove a file's provenance from its actual bytes (not stored state)."""
import io

import pytest
from PIL import Image


def _png(color=(30, 90, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(buf, format="PNG")
    return buf.getvalue()


def test_verify_upload_plain_image_has_no_manifest(client):
    files = {"file": ("plain.png", _png(), "image/png")}
    r = client.post("/api/verify", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["embedded"] is False
    assert body["verified"] is False
    assert body["found"] is False
    assert "no embedded manifest" in body["disclosure"].lower()


async def test_verify_upload_embedded_file_self_verifies(client):
    """A downloaded, manifest-embedded file verifies from its bytes with no DB record.

    The manifest is signed for the exact bytes we embed into, which is what the real
    pipeline produces (generation._embed_and_store re-hashes after embedding). Skipping
    that step would build a file whose manifest commits one hash while its pixels hash to
    another — genuinely tampered-looking, and since genblaze-core 0.3.6 correctly reported
    as such, because MockProvider now emits a placeholder `sha256` of 64 zeros where it
    previously left the field unset.
    """
    pytest.importorskip("genblaze")
    import hashlib
    import tempfile
    from pathlib import Path

    from originshot_pipelines import provenance

    canon = _png()
    res = await _manifest_committing(hashlib.sha256(canon).hexdigest())

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "shot.png"
        path.write_bytes(canon)
        provenance.embed_manifest(res, path, mode="full")
        embedded = path.read_bytes()

    r = client.post("/api/verify", files={"file": ("shot.png", embedded, "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["embedded"] is True
    assert body["verified"] is True
    assert body["content_bound"] is True
    assert body["found"] is False                     # not stored in this instance
    assert "provenance manifest" in body["disclosure"].lower()


async def _manifest_committing(sha: str):
    """A mock-run manifest re-signed to commit a specific asset content hash."""
    from genblaze import Modality, MockProvider, Pipeline

    pipe = Pipeline("t").step(MockProvider(), model="m", prompt="p", modality=Modality.IMAGE)
    pipe.preflight = False
    res = await pipe.arun(timeout=30, raise_on_failure=False)
    res.manifest.run.steps[0].assets[0].sha256 = sha
    res.manifest.compute_hash()  # re-sign so verify() still holds with the new committed hash
    return res


async def test_verify_upload_content_bound_true(client):
    """An embedded file whose bytes match the manifest's signed hash is content-bound."""
    pytest.importorskip("genblaze")
    import hashlib
    import tempfile
    from pathlib import Path

    from originshot_pipelines import provenance

    canon = _png((220, 30, 30))
    res = await _manifest_committing(hashlib.sha256(canon).hexdigest())
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "a.png"
        path.write_bytes(canon)
        provenance.embed_manifest(res, path, mode="full")
        embedded = path.read_bytes()

    body = client.post("/api/verify", files={"file": ("a.png", embedded, "image/png")}).json()
    assert body["embedded"] is True
    assert body["verified"] is True
    assert body["content_bound"] is True


async def test_verify_upload_detects_tampered_content(client):
    """A valid manifest embedded into *different* pixels is flagged as tampered."""
    pytest.importorskip("genblaze")
    import hashlib
    import tempfile
    from pathlib import Path

    from originshot_pipelines import provenance

    canon = _png((220, 30, 30))                       # manifest is signed for THIS content
    res = await _manifest_committing(hashlib.sha256(canon).hexdigest())
    other = _png((30, 30, 220))                       # but we embed it into different pixels
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "b.png"
        path.write_bytes(other)
        provenance.embed_manifest(res, path, mode="full")
        tampered = path.read_bytes()

    body = client.post("/api/verify", files={"file": ("b.png", tampered, "image/png")}).json()
    assert body["embedded"] is True
    assert body["verified"] is True                   # the manifest itself is intact …
    assert body["content_bound"] is False             # … but the bytes don't match its hash
    assert "tampered" in body["disclosure"].lower()


def _mp4(payload: bytes = b"\x00" * 8) -> bytes:
    """A minimal but structurally-valid MP4 (ftyp + mdat) for embed/strip tests."""
    import struct

    ftyp = struct.pack(">I", 20) + b"ftyp" + b"isom" + struct.pack(">I", 0) + b"isom"
    mdat = struct.pack(">I", 8 + len(payload)) + b"mdat" + payload
    return ftyp + mdat


async def test_verify_upload_video_content_bound_true(client):
    """The hero video: an embedded MP4 matching its signed hash is content-bound."""
    pytest.importorskip("genblaze")
    import hashlib
    import tempfile
    from pathlib import Path

    from originshot_pipelines import provenance

    canon = _mp4()
    res = await _manifest_committing(hashlib.sha256(canon).hexdigest())
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "hero.mp4"
        path.write_bytes(canon)
        provenance.embed_manifest(res, path, mode="full")
        embedded = path.read_bytes()

    body = client.post("/api/verify", files={"file": ("hero.mp4", embedded, "video/mp4")}).json()
    assert body["embedded"] is True
    assert body["verified"] is True
    assert body["content_bound"] is True


async def test_verify_upload_video_detects_tampered_frames(client):
    """A valid manifest embedded into a different MP4 payload is flagged as tampered."""
    pytest.importorskip("genblaze")
    import hashlib
    import tempfile
    from pathlib import Path

    from originshot_pipelines import provenance

    canon = _mp4(b"\x00" * 8)
    res = await _manifest_committing(hashlib.sha256(canon).hexdigest())
    other = _mp4(b"\xAB" * 8)                          # different "frames"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "hero.mp4"
        path.write_bytes(other)
        provenance.embed_manifest(res, path, mode="full")
        tampered = path.read_bytes()

    body = client.post("/api/verify", files={"file": ("hero.mp4", tampered, "video/mp4")}).json()
    assert body["embedded"] is True
    assert body["verified"] is True
    assert body["content_bound"] is False
    assert "tampered" in body["disclosure"].lower()


def _img(fmt: str, color=(90, 140, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize(
    ("fmt", "ext", "mime"),
    [("JPEG", ".jpg", "image/jpeg"), ("WEBP", ".webp", "image/webp")],
)
async def test_verify_upload_reencoding_formats_content_bound(client, fmt, ext, mime):
    """JPEG/WebP embedded via our byte-preserving path are content-bound."""
    pytest.importorskip("genblaze")
    import hashlib
    import tempfile
    from pathlib import Path

    from originshot_pipelines import provenance

    canon = _img(fmt)
    res = await _manifest_committing(hashlib.sha256(canon).hexdigest())
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"shot{ext}"
        path.write_bytes(canon)
        provenance.embed_manifest(res, path, mode="full")
        embedded = path.read_bytes()

    body = client.post("/api/verify", files={"file": (f"shot{ext}", embedded, mime)}).json()
    assert body["embedded"] is True
    assert body["verified"] is True
    assert body["content_bound"] is True


@pytest.mark.parametrize(
    ("fmt", "ext", "mime"),
    [("JPEG", ".jpg", "image/jpeg"), ("WEBP", ".webp", "image/webp")],
)
async def test_verify_upload_reencoding_formats_detect_tamper(client, fmt, ext, mime):
    """A valid manifest injected into different JPEG/WebP pixels is flagged as tampered."""
    pytest.importorskip("genblaze")
    import hashlib
    import tempfile
    from pathlib import Path

    from originshot_pipelines import provenance

    canon = _img(fmt, (90, 140, 40))
    res = await _manifest_committing(hashlib.sha256(canon).hexdigest())
    other = _img(fmt, (40, 90, 140))                  # different pixels
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"shot{ext}"
        path.write_bytes(other)
        provenance.embed_manifest(res, path, mode="full")
        tampered = path.read_bytes()

    body = client.post("/api/verify", files={"file": (f"shot{ext}", tampered, mime)}).json()
    assert body["embedded"] is True
    assert body["verified"] is True
    assert body["content_bound"] is False
    assert "tampered" in body["disclosure"].lower()


def test_verify_upload_rejects_oversized(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)  # force the size guard
    r = client.post("/api/verify", files={"file": ("big.png", _png(), "image/png")})
    assert r.status_code == 413
