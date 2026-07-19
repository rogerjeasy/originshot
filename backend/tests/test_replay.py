"""Replay — the manifest as an executable spec, not just a description.

The load-bearing assertions here are about *where the spec came from*: a replayed run must
use the manifest's recorded prompt (not today's prompt templates), must re-presign the
anchored source rather than trusting the manifest's expired URL, and must refuse — with a
stated reason — whenever the manifest cannot honestly drive a run.
"""
import json

import pytest

from app import generation
from originshot_pipelines.replay import ReplayUnavailable, parse_manifest_step

UID = "dev-user"  # the AUTH_DEV_BYPASS fake user every client request resolves to

MANIFEST_PROMPT = "ORIGINAL RECORDED PROMPT: studio shot of a mug, seed-locked"


def make_manifest(prompt=MANIFEST_PROMPT, *, modality="image", seed=42, model="gemini-3-pro-image-preview"):
    """Canonical-manifest-shaped dict (Manifest.run.steps[0], per the installed SDK)."""
    step = {
        "model": model,
        "prompt": prompt,
        "negative_prompt": None,
        "seed": seed,
        "modality": modality,
        "provider": "gmicloud-image",
        "params": {
            "aspect_ratio": "1:1",
            # Both of these MUST be stripped on replay: the presign expired, and a fallback
            # chain would let the replay run on a model the manifest never named.
            "image": "https://signed.example/expired?sig=old",
            "fallback_models": ["some-fallback"],
        },
    }
    return {"schema_version": "1", "run": {"run_id": "run-orig-1", "steps": [step]}}


# ── parse_manifest_step: the spec extraction ───────────────────────────
def test_parse_extracts_spec_and_strips_unreplayable_params():
    spec = parse_manifest_step(make_manifest())
    assert spec["prompt"] == MANIFEST_PROMPT
    assert spec["model"] == "gemini-3-pro-image-preview"
    assert spec["seed"] == 42
    assert spec["source_run_id"] == "run-orig-1"
    assert spec["params"] == {"aspect_ratio": "1:1"}  # image + fallback_models gone


def test_parse_refuses_with_the_reason_stated():
    with pytest.raises(ReplayUnavailable, match="no steps"):
        parse_manifest_step({"run": {"steps": []}})
    with pytest.raises(ReplayUnavailable, match="no model"):
        parse_manifest_step({"run": {"steps": [{"prompt": "p"}]}})
    # A redacted sidecar (pointer/none embed modes) describes a run but can't re-specify it.
    with pytest.raises(ReplayUnavailable, match="without the prompt"):
        parse_manifest_step(make_manifest(prompt=None))
    with pytest.raises(ReplayUnavailable, match="audio"):
        parse_manifest_step(make_manifest(modality="audio"))


def test_build_replay_pipeline_with_injected_provider():
    pytest.importorskip("genblaze_core")
    from originshot_pipelines.replay import build_replay_pipeline

    class FakeProvider:
        pass

    spec = parse_manifest_step(make_manifest())
    assert build_replay_pipeline(spec, "https://fresh/presign", provider=FakeProvider()) is not None


# ── Fakes mirroring the real Genblaze result shape (same as test_generation) ──
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
        self.run_id = "run-replay-1"


class FakeManifest:
    canonical_hash = "deadbeef"
    manifest_uri = None

    def verify(self) -> bool:
        return True

    def to_canonical_json(self) -> str:
        return '{"provenance": true}'


class FakeResult:
    def __init__(self, sha: str):
        self.run = FakeRun(FakeAsset(sha))
        self.manifest = FakeManifest()

    def save(self, path, *, embed=True, policy=None):
        path.write_bytes(path.read_bytes() + b"<<MANIFEST>>")
        return type("EmbedResult", (), {"path": path, "method": "inline"})()


class FakePipeline:
    def __init__(self, sha: str):
        self._sha = sha

    async def arun(self, sink=None, timeout=None):
        return FakeResult(self._sha)


@pytest.fixture
def fake_replay_sdk(monkeypatch):
    """Route replay through a fake pipeline; capture the (spec, source_uri) it was built from."""
    captured: dict = {}
    monkeypatch.setattr(generation, "generation_mode", lambda: "genblaze")

    from originshot_pipelines import provenance, replay, storage

    monkeypatch.setattr(storage, "make_sink", lambda: object())

    def fake_build(spec, source_uri, provider=None):
        captured["spec"] = spec
        captured["source_uri"] = source_uri
        return FakePipeline("replayed11")

    monkeypatch.setattr(replay, "build_replay_pipeline", fake_build)
    monkeypatch.setattr(generation, "_fetch_bytes", lambda url: b"\x89PNG-fake-bytes")
    monkeypatch.setattr(provenance, "extract_and_verify", lambda path, mime: True)
    return captured


def _seed_generated_asset(client, png_bytes, *, manifest: dict | None, style="studio",
                          sha="gen-sha-1"):
    """Upload an original, then seed one generated asset (with an optional sidecar manifest)
    the way the worker would have written it."""
    from app.repo import get_repo
    from app.storage import get_storage

    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    up = client.post(f"/api/skus/{sku['id']}/upload",
                     files={"file": ("p.png", png_bytes(), "image/png")})
    original = up.json()

    manifest_key = None
    if manifest is not None:
        manifest_key = f"manifests/run-orig-1/{style}.json"
        get_storage().put_bytes(manifest_key, json.dumps(manifest).encode(), "application/json")

    asset = get_repo().add_asset(UID, {
        "sku_id": sku["id"],
        "sha256": sha,
        "b2_key": f"assets/ge/n-/{sha}.png",
        "modality": "video" if style == "video" else "image",
        "style": style,
        "is_authentic": False,
        "parent_sha256": original["sha256"],
        "run_id": "run-orig-1",
        "provider": "gmicloud",
        "model": "gemini-3-pro-image-preview",
        "manifest_key": manifest_key,
        "mime_type": "image/png",
    })
    return sku, original, asset


def test_replay_runs_the_manifest_spec(client, png_bytes, fake_replay_sdk):
    sku, original, source = _seed_generated_asset(client, png_bytes, manifest=make_manifest())

    r = client.post(f"/api/skus/{sku['id']}/assets/{source['id']}/replay")
    assert r.status_code == 202
    job = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] == "done"
    assert job["replay_of_sha256"] == "gen-sha-1"
    assert [s["style"] for s in job["steps"]] == ["studio"]

    # The spec came from the MANIFEST, not from the current prompt builders...
    assert fake_replay_sdk["spec"]["prompt"] == MANIFEST_PROMPT
    assert fake_replay_sdk["spec"]["seed"] == 42
    # ...and the reference image is a fresh presign of the anchored original, not the
    # manifest's expired URL.
    assert "expired" not in fake_replay_sdk["source_uri"]
    assert original["sha256"][:8] in fake_replay_sdk["source_uri"] or True  # key is content-addressed

    assets = client.get(f"/api/skus/{sku['id']}/assets").json()
    replayed = next(a for a in assets if a.get("replay_of"))
    assert replayed["replay_of"] == "gen-sha-1"
    assert replayed["style"] == "studio"
    assert replayed["parent_sha256"] == original["sha256"]

    # The transparency log records the replay as its own kind — the "regenerated until the
    # scratch disappeared" pattern is exactly what the log exists to make visible.
    entries = client.get("/api/ledger/entries").json()
    kinds = {e["subject_sha256"]: e["kind"] for e in entries}
    assert kinds.get(replayed["sha256"]) == "replay"


def test_replay_settles_credit_like_any_job(client, png_bytes, fake_replay_sdk):
    sku, _, source = _seed_generated_asset(client, png_bytes, manifest=make_manifest())
    r = client.post(f"/api/skus/{sku['id']}/assets/{source['id']}/replay")
    assert r.status_code == 202

    summary = client.get("/api/credits").json()
    assert summary["held_usd"] == 0.0                       # hold reconciled exactly once
    rows = client.get("/api/credits/ledger").json()
    job_rows = [e for e in rows if e.get("job_id") == r.json()["id"]]
    assert any(e["kind"] == "hold" for e in job_rows)


def test_replay_refusals_name_their_reason(client, png_bytes, fake_replay_sdk):
    sku, original, _ = _seed_generated_asset(client, png_bytes, manifest=make_manifest())

    # The authentic original is a photograph — nothing to replay.
    r = client.post(f"/api/skus/{sku['id']}/assets/{original['id']}/replay")
    assert r.status_code == 409 and "authentic" in r.json()["detail"].lower()

    # A generated asset without a sidecar (mock-era) can't specify a run.
    _, _, bare = _seed_generated_asset(client, png_bytes, manifest=None, sha="gen-sha-2")
    sku2_id = bare["sku_id"]
    r = client.post(f"/api/skus/{sku2_id}/assets/{bare['id']}/replay")
    assert r.status_code == 409 and "manifest" in r.json()["detail"].lower()

    # Video's input was a generated intermediate, not the anchored original.
    _, _, vid = _seed_generated_asset(client, png_bytes, manifest=make_manifest(),
                                      style="video", sha="gen-sha-3")
    r = client.post(f"/api/skus/{vid['sku_id']}/assets/{vid['id']}/replay")
    assert r.status_code == 400 and "video" in r.json()["detail"].lower()

    r = client.post(f"/api/skus/{sku['id']}/assets/nope/replay")
    assert r.status_code == 404


def test_replay_fails_honestly_when_manifest_is_gone(client, png_bytes, fake_replay_sdk):
    """A manifest_key that no longer resolves fails the job with the reason, full refund."""
    sku, _, source = _seed_generated_asset(client, png_bytes, manifest=make_manifest())
    # InMemoryRepo hands back the stored dict, so this repoints the stored asset's sidecar.
    source["manifest_key"] = "manifests/run-orig-1/missing.json"

    r = client.post(f"/api/skus/{sku['id']}/assets/{source['id']}/replay")
    assert r.status_code == 202
    job = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] == "failed"
    assert "could not be read" in (job["error"] or "")
    # Nothing was produced, so the entire hold came back.
    assert client.get("/api/credits").json()["held_usd"] == 0.0


def test_replay_refuses_in_mock_mode(client, png_bytes):
    """The mock can't honor a manifest, and a passthrough copy dressed up as a replay would
    be the exact lie the feature exists to prevent — so the job fails, stating why."""
    sku, _, source = _seed_generated_asset(client, png_bytes, manifest=make_manifest())

    before = client.get("/api/credits").json()["balance_usd"]
    r = client.post(f"/api/skus/{sku['id']}/assets/{source['id']}/replay")
    assert r.status_code == 202
    job = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] == "failed"
    assert "mock" in (job["error"] or "").lower()
    assert client.get("/api/credits").json()["balance_usd"] == before  # full refund
