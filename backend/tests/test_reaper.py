"""Stale-job reaper: abandoned runs must fail honestly and give the credit back.

The failure being repaired here can't be provoked by raising an exception — `worker._run_job`
already catches those. It is the process *dying* mid-job, which leaves a `running` job with an
outstanding hold and nobody left to reconcile it. These tests reproduce that end state
directly (write the job document a dead worker would have left behind) and assert the reaper
turns it into a terminal status and a refund.
"""
from datetime import timedelta

import pytest

from app import reaper
from app.credits import get_balance, grant, hold
from app.models import utcnow
from app.repo import get_repo

UID = "dev-user"  # conftest's AUTH_DEV_BYPASS identity


@pytest.fixture
def repo(client):
    return get_repo()


def _abandoned_job(repo, *, styles=("studio",), age_seconds=100_000, held=0.0, status="running"):
    """A job document in exactly the shape a killed worker leaves behind."""
    job = repo.create_job(UID, {
        "sku_id": "sku-1",
        "requested_styles": list(styles),
        "steps": [{"style": s, "status": "running"} for s in styles],
        "credits_held": held,
    })
    started = utcnow() - timedelta(seconds=age_seconds)
    return repo.update_job(UID, job["id"], {
        "status": status, "started_at": started, "created_at": started,
    })


def test_running_job_past_its_budget_is_failed(client, repo):
    job = _abandoned_job(repo)
    reaped = reaper.reap_job(UID, job)

    assert reaped["status"] == "failed"
    assert "did not complete" in reaped["error"]
    assert reaped["finished_at"] is not None


def test_reaping_finishes_the_steps_too(client, repo):
    """A job that reads `failed` while its step still reads `running` just moves the spinner."""
    job = _abandoned_job(repo, styles=("studio", "video"))
    reaped = reaper.reap_job(UID, job)

    assert [s["status"] for s in reaped["steps"]] == ["failed", "failed"]
    assert all(s["error"] for s in reaped["steps"])


def test_the_hold_is_refunded_in_full(client, repo):
    client.get("/api/credits")            # issue the signup grant
    grant(UID, 10.0, actor_uid="test", note="seed")
    before = get_balance(UID)

    job = _abandoned_job(repo, held=0.0)
    hold(UID, job_id=job["id"], sku_id="sku-1", amount=0.40)
    repo.update_job(UID, job["id"], {"credits_held": 0.40})
    assert get_balance(UID) == pytest.approx(before - 0.40)

    reaper.reap_job(UID, repo.get_job(UID, job["id"]))

    assert get_balance(UID) == pytest.approx(before)
    assert repo.get_job(UID, job["id"])["credits_held"] == pytest.approx(0.0)


def test_a_live_job_inside_its_budget_is_left_alone(client, repo):
    """The cure must not be worse than the disease: a slow provider is not an abandoned job."""
    job = _abandoned_job(repo, styles=("video",), age_seconds=60)

    assert reaper.is_stale(job) is False
    assert reaper.reap_job(UID, job) is None
    assert repo.get_job(UID, job["id"])["status"] == "running"


def test_the_deadline_scales_with_what_was_asked_for(client):
    """A video pack gets minutes longer than a single studio shot."""
    studio = {"requested_styles": ["studio"]}
    pack = {"requested_styles": ["studio", "lifestyle", "video", "voiceover"]}

    assert reaper.deadline_seconds(pack) > reaper.deadline_seconds(studio)
    assert reaper.deadline_seconds(studio) >= reaper.MIN_DEADLINE_SECONDS


def test_a_job_that_died_while_queued_is_still_reapable(client, repo):
    """No `started_at` — dated from `created_at`, or it could never be reaped at all."""
    job = _abandoned_job(repo, status="queued")
    repo.update_job(UID, job["id"], {"started_at": None})

    assert reaper.reap_job(UID, repo.get_job(UID, job["id"]))["status"] == "failed"


def test_reaping_is_idempotent(client, repo):
    """A second pass must not double-refund — the status write is what makes it safe."""
    client.get("/api/credits")
    grant(UID, 10.0, actor_uid="test", note="seed")

    job = _abandoned_job(repo)
    hold(UID, job_id=job["id"], sku_id="sku-1", amount=0.40)
    repo.update_job(UID, job["id"], {"credits_held": 0.40})

    reaper.reap_job(UID, repo.get_job(UID, job["id"]))
    settled = get_balance(UID)
    assert reaper.reap_job(UID, repo.get_job(UID, job["id"])) is None
    assert get_balance(UID) == pytest.approx(settled)


def test_terminal_jobs_are_never_touched(client, repo):
    for status in ("done", "partial", "failed"):
        job = _abandoned_job(repo, status=status)
        assert reaper.reap_job(UID, job) is None


def test_polling_an_abandoned_job_serves_the_reaped_result(client, repo):
    """The user-visible fix: GET /jobs/{id} resolves the spinner instead of feeding it."""
    job = _abandoned_job(repo)

    body = client.get(f"/api/jobs/{job['id']}").json()

    assert body["status"] == "failed"
    assert "did not complete" in body["error"]


def test_reap_all_settles_each_job_under_its_own_owner(client, repo):
    """Cross-user sweep: crediting the wrong account would be worse than not reaping."""
    other = "other-user"
    grant(other, 10.0, actor_uid="test", note="seed")
    before = get_balance(other)

    job = repo.create_job(other, {"sku_id": "s", "requested_styles": ["studio"], "steps": []})
    hold(other, job_id=job["id"], sku_id="s", amount=0.25)
    started = utcnow() - timedelta(seconds=100_000)
    repo.update_job(other, job["id"], {
        "status": "running", "started_at": started, "created_at": started,
        "credits_held": 0.25,
    })

    assert reaper.reap_all() >= 1
    assert get_balance(other) == pytest.approx(before)
