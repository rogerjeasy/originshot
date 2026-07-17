"""Validate the real Genblaze mapping logic with a faked SDK (no genblaze install needed)."""
import pytest

from app import generation


# ── Fakes mirroring the REAL Genblaze result shape (verified Week 1) ────
# Asset carries media (no provider/model/key); provider/model/cost live on the Step;
# Manifest exposes to_canonical_json()/verify()/manifest_uri.
class FakeAsset:
    def __init__(self, sha: str):
        self.sha256 = sha
        self.url = f"https://b2.example/{sha}.png"
        self.media_type = "image/png"
        self.size_bytes = 12345
        self.width = 2048
        self.height = 2048
        self.duration = None


class FakeStep:
    def __init__(self, asset: FakeAsset):
        self.assets = [asset]
        self.provider = "gmicloud"
        self.model = "gemini-3-pro-image-preview"
        self.cost_usd = 0.04


class FakeRun:
    def __init__(self, asset: FakeAsset):
        self.steps = [FakeStep(asset)]
        self.run_id = "run-123"


class FakeManifest:
    canonical_hash = "deadbeef"
    manifest_uri = None  # None ⇒ generation._map persists its own sidecar

    def verify(self) -> bool:
        return True

    def to_canonical_json(self) -> str:
        return '{"provenance": true}'


class FakeResult:
    def __init__(self, sha: str):
        self.run = FakeRun(FakeAsset(sha))
        self.manifest = FakeManifest()

    def save(self, path, *, embed=True, policy=None):
        # Mimic SmartEmbedder: append a marker so the file bytes (and thus sha) change.
        path.write_bytes(path.read_bytes() + b"<<MANIFEST>>")
        return type("EmbedResult", (), {"path": path, "method": "inline"})()


class FakePipeline:
    def __init__(self, sha: str):
        self._sha = sha

    async def arun(self, sink=None, timeout=None):
        return FakeResult(self._sha)


class FakeStorage:
    def __init__(self):
        self.puts: list[str] = []

    def presigned_get(self, key: str) -> str:
        return f"https://signed/{key}"

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        self.puts.append(key)
        return key


@pytest.fixture
def fake_sdk(monkeypatch):
    """Replace pipeline builders with fakes; capture the kwargs they were called with."""
    captured: dict[str, dict] = {}
    monkeypatch.setattr(generation, "generation_mode", lambda: "genblaze")
    from listsnap_pipelines import lifestyle, onmodel, storage, studio, variants, video

    monkeypatch.setattr(storage, "make_sink", lambda: object())

    def fake_studio(*a, **k):
        captured["studio"] = k
        return FakePipeline("aa11")

    def fake_onmodel(*a, **k):
        captured["onmodel"] = k
        return FakePipeline("bb22")

    def fake_video(*a, **k):
        captured["video"] = k
        return FakePipeline("cc33")

    async def fake_lifestyle(src, desc, sink, scenes=None, brand_suffix=""):
        captured["lifestyle"] = {"brand_suffix": brand_suffix}
        return [FakeResult("dd44"), FakeResult("ee55")]

    async def fake_variants(src, desc, sink, colors=(), angles=(), brand_suffix=""):
        captured["variant"] = {"brand_suffix": brand_suffix}
        return [FakeResult("ff66")]

    monkeypatch.setattr(studio, "build_studio_pipeline", fake_studio)
    monkeypatch.setattr(onmodel, "build_onmodel_pipeline", fake_onmodel)
    monkeypatch.setattr(video, "build_hero_video", fake_video)
    monkeypatch.setattr(lifestyle, "run_lifestyle", fake_lifestyle)
    monkeypatch.setattr(variants, "run_variants", fake_variants)

    # Embedding deps: fake the byte download and the post-embed extract/verify (the fake
    # bytes aren't a real PNG, so the SDK extractor can't run — the real roundtrip is
    # covered in test_sdk_integration.py).
    from listsnap_pipelines import provenance

    monkeypatch.setattr(generation, "_fetch_bytes", lambda url: b"\x89PNG-fake-bytes")
    monkeypatch.setattr(provenance, "extract_and_verify", lambda path, mime: True)
    return captured


async def test_real_generation_maps_all_styles(fake_sdk):
    sku = {"id": "sku1", "title": "Mug", "description": "a blue mug"}
    original = {"sha256": "origsha", "b2_key": "assets/orig.png"}
    storage = FakeStorage()

    assets, errors = await generation.generate_assets(
        "uid", sku, original, ["studio", "lifestyle", "onmodel", "variant", "video"], storage=storage
    )

    assert errors == []
    styles = sorted(a["style"] for a in assets)
    assert styles == ["lifestyle", "lifestyle", "onmodel", "studio", "variant", "video"]

    studio_asset = next(a for a in assets if a["style"] == "studio")
    assert studio_asset["provider"] == "gmicloud"           # from Step, not Asset
    assert studio_asset["model"] == "gemini-3-pro-image-preview"
    assert studio_asset["mime_type"] == "image/png"         # Asset.media_type
    assert studio_asset["cost_usd"] == 0.04                 # from Step.cost_usd
    assert studio_asset["manifest_verified"] is True
    assert studio_asset["manifest_key"] == "manifests/run-123/studio.json"
    assert all(a["parent_sha256"] == "origsha" for a in assets)

    # Embedding wired in: each asset is re-stored under our content-addressable key with the
    # manifest embedded, the sink URL dropped, and sha refreshed to the embedded bytes.
    assert all(a["embedded"] is True for a in assets)
    assert all(a["b2_key"] and a["b2_key"].startswith("assets/") for a in assets)
    assert all(a["b2_url"] is None for a in assets)
    assert all(a["sha256"] != "origsha" for a in assets)

    video_asset = next(a for a in assets if a["style"] == "video")
    assert video_asset["modality"] == "video"

    # Two puts per asset: the sidecar manifest + the embedded media object.
    assert len(storage.puts) == 2 * len(assets)


async def test_brand_kit_and_marketplace_applied(fake_sdk):
    sku = {"id": "sku1", "title": "Mug", "description": "a blue mug"}
    original = {"sha256": "origsha", "b2_key": "assets/orig.png"}
    brand = {"vibe": "warm minimal", "lighting": "soft natural", "palette": "earthy neutrals"}

    assets, errors = await generation.generate_assets(
        "uid", sku, original, ["studio", "lifestyle", "variant"],
        storage=FakeStorage(), brand=brand, marketplaces=["social"],
    )
    assert errors == []
    # studio gets the lighter "tone" fragment (vibe+lighting) and the social aspect (4:5)
    assert "warm minimal" in fake_sdk["studio"]["brand_suffix"]
    assert "earthy neutrals" not in fake_sdk["studio"]["brand_suffix"]
    assert fake_sdk["studio"]["aspect"] == "4:5"
    # contextual styles get the full fragment incl. palette
    assert "earthy neutrals" in fake_sdk["lifestyle"]["brand_suffix"]
    assert "earthy neutrals" in fake_sdk["variant"]["brand_suffix"]


async def test_video_without_studio_is_a_partial_error(fake_sdk):
    sku = {"id": "s", "title": "X", "description": None}
    original = {"sha256": "orig", "b2_key": "assets/o.png"}
    assets, errors = await generation.generate_assets(
        "u", sku, original, ["video"], storage=FakeStorage()
    )
    assert assets == []
    assert any("video" in e for e in errors)


async def test_mock_mode_skips_video(monkeypatch):
    monkeypatch.setattr(generation, "generation_mode", lambda: "mock")
    sku = {"id": "s", "title": "X", "description": None}
    original = {"sha256": "orig", "b2_key": "assets/o.png", "mime_type": "image/png",
                "width": 10, "height": 10}
    assets, errors = await generation.generate_assets(
        "u", sku, original, ["studio", "video"], storage=None
    )
    assert errors == []
    styles = {a["style"] for a in assets}
    assert "studio" in styles and "video" not in styles
    assert assets[0]["provider"] == "mock-dev"
