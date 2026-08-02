"""One SKU, one live job — and the server is the authority on which one that is.

Two halves of the same rule live here: a duplicate submit is refused (below), and the run
that refused it can be found again (`GET /skus/{id}/job`), so refusing never strands anyone.

Part one — a re-submitted generation must not double-charge.

Every extra `POST /skus/{id}/generate` creates its own job *and holds its own estimate*. That
is fine when the user meant it and a denial-of-wallet hole when they didn't — and they often
didn't, because the studio's Generate button used to give no feedback for the whole
round-trip, so an unanswered click looked like a click that hadn't registered. Users clicked
again. On a free-tier instance the duplicate jobs then competed for 512 MB until the process
died, stranding every one of those holds.

The client now disables itself on the first click. This is the server-side half, which holds
for a stale tab, a retried request, or a second browser — none of which the client can see.

The guard reaps first and refuses second, so a *dead* job can never lock a SKU out of
generating: it is only ever blocked by a run that is genuinely still inside its budget.
"""
from datetime import timedelta

import pytest

from app.credits import get_balance
from app.models import utcnow
from app.repo import get_repo

UID = "dev-user"  # conftest's AUTH_DEV_BYPASS identity


@pytest.fixture
def sku(client, png_bytes):
    """A SKU with its authentic original uploaded — ready to generate."""
    doc = client.post("/api/skus", json={"title": "Ceramic Mug"}).json()
    client.post(
        f"/api/skus/{doc['id']}/upload",
        files={"file": ("mug.png", png_bytes(), "image/png")},
    )
    return doc


def _live_job(sku_id: str, *, age_seconds: int, held: float = 0.70) -> dict:
    """A job document for `sku_id` that still claims to be running."""
    repo = get_repo()
    job = repo.create_job(UID, {
        "sku_id": sku_id,
        "requested_styles": ["studio", "lifestyle"],
        "steps": [{"style": "studio", "status": "running"}],
        "credits_held": held,
    })
    started = utcnow() - timedelta(seconds=age_seconds)
    return repo.update_job(UID, job["id"], {
        "status": "running", "started_at": started, "created_at": started,
    })


def test_second_generate_while_one_is_running_is_refused(client, sku):
    live = _live_job(sku["id"], age_seconds=30)

    r = client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})

    assert r.status_code == 409
    # The refusal has to be actionable: the caller is told which run is in the way.
    assert live["id"] in r.json()["detail"]


def test_the_refused_submit_holds_no_credit(client, sku):
    client.get("/api/credits")                     # issue the signup grant
    _live_job(sku["id"], age_seconds=30)
    before = get_balance(UID)

    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})

    # The whole point of refusing: a duplicate submit must not move the balance.
    assert get_balance(UID) == pytest.approx(before)


def test_the_refused_submit_creates_no_job(client, sku):
    _live_job(sku["id"], age_seconds=30)
    before = len(get_repo().list_jobs(UID))

    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})

    assert len(get_repo().list_jobs(UID)) == before


def test_an_abandoned_job_does_not_lock_the_sku_forever(client, sku):
    """Reap first, refuse second — otherwise a dead run would bar the SKU permanently."""
    dead = _live_job(sku["id"], age_seconds=100_000)

    r = client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})

    assert r.status_code == 202
    # The stale job was resolved on the way through, not merely stepped over.
    assert get_repo().get_job(UID, dead["id"])["status"] == "failed"


def test_a_live_job_on_a_different_sku_is_not_in_the_way(client, sku, png_bytes):
    """The lock is per SKU: generating two products at once is ordinary use."""
    other = client.post("/api/skus", json={"title": "Kettle"}).json()
    client.post(
        f"/api/skus/{other['id']}/upload",
        files={"file": ("kettle.png", png_bytes(), "image/png")},
    )
    _live_job(other["id"], age_seconds=30)

    r = client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})

    assert r.status_code == 202


# ── Finding the run again (GET /skus/{id}/job) ────────────────────────
def test_the_live_job_can_be_found_again(client, sku):
    """Reloading the studio mid-run must not lose the run.

    Without this the page came back with no progress at all — and now that a duplicate submit
    is refused, the user would also be told a job is running with no way to see it.
    """
    live = _live_job(sku["id"], age_seconds=30)

    body = client.get(f"/api/skus/{sku['id']}/job").json()

    assert body["id"] == live["id"]
    assert body["status"] == "running"


def test_no_live_job_reads_as_nothing_running(client, sku):
    assert client.get(f"/api/skus/{sku['id']}/job").json() is None


def test_a_finished_job_is_not_offered_as_live(client, sku):
    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})

    assert client.get(f"/api/skus/{sku['id']}/job").json() is None


def test_looking_up_the_live_job_reaps_an_abandoned_one(client, sku):
    """Same reap-on-read contract as GET /jobs/{id}: a dead run resolves, it doesn't linger."""
    dead = _live_job(sku["id"], age_seconds=100_000)

    assert client.get(f"/api/skus/{sku['id']}/job").json() is None
    assert get_repo().get_job(UID, dead["id"])["status"] == "failed"


def test_replay_is_refused_while_a_job_is_running(client, sku):
    """A replay is an ordinary job holding ordinary credit — same rule."""
    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})
    asset = next(
        a for a in get_repo().list_assets(UID, sku["id"]) if not a["is_authentic"]
    )
    # The mock writes no manifest sidecar, and replay refuses a manifest-less asset before it
    # ever reaches the concurrency guard. Give it one so this test exercises the guard.
    asset["manifest_key"] = "manifests/run-1/studio.json"
    live = _live_job(sku["id"], age_seconds=30)

    r = client.post(f"/api/skus/{sku['id']}/assets/{asset['id']}/replay")

    assert r.status_code == 409
    # Replay has its own 409s (no manifest, video asset, …) — pin this to the right one.
    assert live["id"] in r.json()["detail"]
