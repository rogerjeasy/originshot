"""Recovering provenance from B2 when the database row is gone.

The regression these pin down was live in production on 2026-08-01: 6 of 30 transparency-log
entries resolved to `found: false` on `/api/verify/{sha}`, and the UI told the visitor
"Nothing in the ledger matches it" about a hash sitting in the instance's own signed,
checkpointed log. The asset table is mutable and the chain is not, so deleting a SKU strands
the entry.

`app/recovery.py` closes it by reading the manifest back from the B2 key the entry already
commits to. These tests hold the line on both halves of that: it must resolve what it can,
and it must never dress a recovered answer up as a byte-proven one.
"""
import json
import uuid

import pytest

from app import recovery
from app.repo import get_repo
from app.storage import get_storage

SUBJECT = "c" * 64          # the hash a caller asks about (post-embed, as the ledger records)
PRE_EMBED = "b" * 64        # what the manifest itself recorded (pre-embed) — deliberately different
ORIGINAL = "a" * 64         # the authentic original the step consumed


def build_manifest(*, run_name="originshot-lifestyle", provider="openai-dalle",
                   model="gpt-image-1", modality="image", inputs=True,
                   valid_hash=True) -> dict:
    """A sidecar manifest shaped like the real ones on B2, with a correct canonical hash.

    Mirrors the document pulled from `assets/manifests/*.json` in production, so a change to
    the SDK's schema breaks these tests rather than only breaking production.
    """
    from genblaze_core.models.manifest import parse_manifest

    step = {
        "step_id": "22222222-2222-4222-8222-222222222222",
        "run_id": "11111111-1111-4111-8111-111111111111",
        "step_index": 0,
        "step_type": "generate",
        "status": "succeeded",
        "modality": modality,
        "model": model,
        "provider": provider,
        "prompt": "a mug on a sunlit counter",
        "prompt_visibility": "public",
        "params": {"quality": "medium"},
        "metadata": {},
        "provider_payload": {},
        "retries": 0,
        "started_at": "2026-07-21T10:51:58.191511Z",
        "completed_at": "2026-07-21T10:52:32.243080Z",
        "inputs": [{
            "asset_id": "33333333-3333-4333-8333-333333333333",
            "media_type": "image/png",
            "sha256": ORIGINAL,
            "url": "file:///tmp/in.png",
            "metadata": {},
        }] if inputs else [],
        "assets": [{
            "asset_id": "44444444-4444-4444-8444-444444444444",
            "media_type": "image/png",
            "sha256": PRE_EMBED,
            "url": "file:///tmp/out.png",
            "size_bytes": 1234,
            "metadata": {},
        }],
    }
    doc = {
        "canonical_hash": "0" * 64,
        "encryption_scheme": None,
        "manifest_uri": None,
        "schema_version": "1.5",
        "signature": None,
        "transfer_failures": [],
        "run": {
            "run_id": "11111111-1111-4111-8111-111111111111",
            "name": run_name,
            "status": "completed",
            "created_at": "2026-07-21T10:51:58.191511Z",
            "started_at": "2026-07-21T10:51:58.191511Z",
            "completed_at": "2026-07-21T10:52:32.243080Z",
            "metadata": {},
            "steps": [step],
        },
    }
    if valid_hash:
        doc["canonical_hash"] = parse_manifest(doc).compute_hash()
    return doc


def strand(subject=SUBJECT, *, manifest=None, key=None,
           pointer=None, kind="generated", store=True) -> str:
    """Create the exact production state: a log entry whose asset row does not exist.

    Returns the manifest key. `pointer` overrides what the entry commits to, for the cases
    where the pointer itself is the thing under test.

    The key is unique per call because `LocalStorage` (what the suite runs on) writes to a real
    `.devdata/media` directory that outlives the in-memory repo. A fixed key would leave the
    "manifest missing from B2" cases silently reading a file an earlier test wrote.
    """
    if key is None:
        key = f"manifests/{uuid.uuid4()}/lifestyle.json"
    if store:
        doc = build_manifest() if manifest is None else manifest
        get_storage().put_bytes(key, json.dumps(doc).encode(), "application/json")
    get_repo().append_transparency_entry({
        "subject_sha256": subject,
        "manifest_hash": key if pointer is None else pointer,
        "kind": kind,
        "recorded_at": "2026-07-21T10:53:56Z",
    })
    return key


@pytest.fixture(autouse=True)
def _clear_manifest_cache():
    """The recovery cache is process-global; a stale entry would leak between tests."""
    recovery._cache.clear()
    yield
    recovery._cache.clear()


# ── The unit ──────────────────────────────────────────────────────────
def test_recovers_provenance_from_the_b2_manifest(client):
    strand()
    rec = recovery.recover_from_ledger(SUBJECT)

    assert rec is not None
    assert rec["resolved_from"] == "b2-manifest"
    assert rec["provider"] == "openai-dalle"
    assert rec["model"] == "gpt-image-1"
    assert rec["modality"] == "image"
    assert rec["style"] == "lifestyle"
    # Lineage back to the anchored original is the whole point of resolving this at all.
    assert rec["parent_sha256"] == ORIGINAL
    assert rec["created_at"] == "2026-07-21T10:52:32.243080Z"


def test_verified_is_a_real_check_not_an_assumption(client):
    """A recovered manifest that fails its own integrity check must report verified False."""
    strand(manifest=build_manifest(valid_hash=False))
    rec = recovery.recover_from_ledger(SUBJECT)

    assert rec is not None                      # the record is still resolvable…
    assert rec["manifest_verified"] is False    # …but it does not pass, and says so


def test_unknown_pipeline_name_yields_no_style(client):
    """An unmapped run name must return None, not a guess.

    A replay's manifest names the replay pipeline rather than the style it reproduced; putting
    a plausible-looking label on it would be a wrong answer in a provenance record.
    """
    strand(manifest=build_manifest(run_name="originshot-replay"))
    rec = recovery.recover_from_ledger(SUBJECT)

    assert rec is not None
    assert rec["style"] is None


def test_step_without_inputs_has_no_parent(client):
    strand(manifest=build_manifest(inputs=False))
    rec = recovery.recover_from_ledger(SUBJECT)

    assert rec is not None
    assert rec["parent_sha256"] is None


@pytest.mark.parametrize("case, kwargs", [
    ("hash is not in the log at all", {}),
    ("entry carries no manifest pointer", {"pointer": ""}),
    ("manifest object is missing from B2", {"store": False}),
])
def test_returns_none_when_nothing_can_be_recovered(client, case, kwargs):
    """Each of these must fall through to the caller's honest "no record" answer."""
    if case != "hash is not in the log at all":
        strand(**kwargs)
    assert recovery.recover_from_ledger(SUBJECT) is None


def test_pointer_outside_our_bucket_is_never_fetched(client):
    """A log entry must not be able to send the verifier fetching from an arbitrary host.

    `key_from_url` returns None for anything outside our bucket, and recovery refuses rather
    than treating a foreign URL as a key.
    """
    strand(pointer="https://evil.example.com/manifest.json")
    assert recovery.recover_from_ledger(SUBJECT) is None


def test_a_failed_load_is_not_cached(client):
    """A transient B2 error must not become a permanent "not found"."""
    key = strand(store=False)
    assert recovery.recover_from_ledger(SUBJECT) is None

    get_storage().put_bytes(key, json.dumps(build_manifest()).encode(), "application/json")
    assert recovery.recover_from_ledger(SUBJECT) is not None


# ── The endpoints ─────────────────────────────────────────────────────
def test_get_verify_no_longer_contradicts_the_ledger(client):
    """The exact production regression: in the log, but reported as no record."""
    strand()
    body = client.get(f"/api/verify/{SUBJECT}").json()

    assert body["found"] is True
    assert body["verified"] is True
    assert body["resolved_from"] == "b2-manifest"
    assert body["provider"] == "openai-dalle"
    assert body["parent_sha256"] == ORIGINAL
    assert body["ledger"]["seq"] == 0
    assert "No record found" not in body["disclosure"]


def test_a_recovered_answer_never_claims_content_binding(client):
    """From a hash alone there are no bytes to bind, and the disclosure must say so.

    The ledger's subject is the post-embed hash while the manifest records the pre-embed one,
    so the two cannot be compared — claiming `content_bound` here would be the exact kind of
    overreach this project exists to refuse.
    """
    strand()
    body = client.get(f"/api/verify/{SUBJECT}").json()

    assert body["content_bound"] is None
    assert body["embedded"] is False
    assert "Backblaze B2" in body["disclosure"]
    assert "Content-binding cannot be established" in body["disclosure"]


def test_a_hash_in_neither_the_log_nor_the_table_still_reports_nothing(client):
    body = client.get(f"/api/verify/{'d' * 64}").json()

    assert body["found"] is False
    assert body["resolved_from"] == "record"
    assert body["disclosure"] == "No record found for this hash."


def test_a_real_record_still_reports_itself_as_a_record(client, png_bytes):
    """Recovery must not disturb the normal path — `resolved_from` stays "record"."""
    data = png_bytes()
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("m.png", data, "image/png")})

    import hashlib

    sha = hashlib.sha256(data).hexdigest()
    body = client.get(f"/api/verify/{sha}").json()

    assert body["found"] is True
    assert body["resolved_from"] == "record"


def test_manifest_endpoint_recovers_instead_of_404(client):
    strand()
    r = client.get(f"/api/assets/{SUBJECT}/manifest")

    assert r.status_code == 200
    body = r.json()
    assert body["resolved_from"] == "b2-manifest"
    assert body["model"] == "gpt-image-1"
    assert body["parent_sha256"] == ORIGINAL


def test_manifest_endpoint_still_404s_for_a_genuinely_unknown_hash(client):
    assert client.get(f"/api/assets/{'d' * 64}/manifest").status_code == 404


def test_posted_bytes_recover_and_do_bind(client, png_bytes):
    """Posting the file itself resolves the record AND binds it.

    The hash-only path can't compare bytes; this one can — the uploaded bytes hash to exactly
    the subject the signed chain committed to, which is the same standard a byte-exact hit on
    a stored row meets.
    """
    import hashlib

    data = png_bytes()
    sha = hashlib.sha256(data).hexdigest()
    strand(subject=sha)

    body = client.post("/api/verify",
                       files={"file": ("x.png", data, "image/png")}).json()

    assert body["found"] is True
    assert body["resolved_from"] == "b2-manifest"
    assert body["content_bound"] is True
    assert body["model"] == "gpt-image-1"
