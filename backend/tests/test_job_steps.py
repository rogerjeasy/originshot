"""Per-step job progress — the data behind the live timer."""
import pytest

UID = "dev-user"


def _sku_with_photo(client, png_bytes):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes(), "image/png")})
    return sku


def test_job_is_created_with_a_pending_step_per_style(client, png_bytes):
    """Steps exist before the worker starts, so the UI can render the plan immediately."""
    sku = _sku_with_photo(client, png_bytes)
    job = client.post(f"/api/skus/{sku['id']}/generate",
                      json={"styles": ["studio", "lifestyle"]}).json()

    assert [s["style"] for s in job["steps"]] == ["studio", "lifestyle"]
    assert job["eta_seconds"] > 0
    assert all(s["eta_seconds"] > 0 for s in job["steps"])


def test_completed_steps_carry_timing_and_provider(client, png_bytes):
    sku = _sku_with_photo(client, png_bytes)
    job = client.post(f"/api/skus/{sku['id']}/generate",
                      json={"styles": ["studio", "lifestyle"]}).json()
    # TestClient runs BackgroundTasks synchronously, so the job is finished on return.
    fetched = client.get(f"/api/jobs/{job['id']}").json()

    assert fetched["status"] == "done"
    assert len(fetched["steps"]) == 2
    for step in fetched["steps"]:
        assert step["status"] == "done"
        assert step["provider"] == "mock-dev"
        assert step["asset_count"] == 1
        assert step["duration_ms"] is not None
        assert step["started_at"] and step["finished_at"]


def test_job_records_when_the_worker_actually_started(client, png_bytes):
    """`started_at` separates queue wait from generation time."""
    sku = _sku_with_photo(client, png_bytes)
    job = client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]}).json()
    fetched = client.get(f"/api/jobs/{job['id']}").json()

    assert fetched["started_at"] is not None
    assert fetched["finished_at"] is not None


def test_video_is_skipped_with_a_reason_in_the_mock(client, png_bytes):
    """A skipped step must say why rather than silently vanishing from the plan."""
    sku = _sku_with_photo(client, png_bytes)
    job = client.post(f"/api/skus/{sku['id']}/generate",
                      json={"styles": ["studio", "video"]}).json()
    fetched = client.get(f"/api/jobs/{job['id']}").json()

    video = next(s for s in fetched["steps"] if s["style"] == "video")
    assert video["status"] == "skipped"
    assert video["error"]


def test_undelivered_style_makes_the_job_partial_not_done(client, png_bytes):
    """`done` must mean every requested style was delivered.

    The mock can't produce video, so a studio+video request delivered only one of two
    requested styles — reporting that as `done` would overstate the result.
    """
    sku = _sku_with_photo(client, png_bytes)
    job = client.post(f"/api/skus/{sku['id']}/generate",
                      json={"styles": ["studio", "video"]}).json()
    fetched = client.get(f"/api/jobs/{job['id']}").json()

    assert fetched["status"] == "partial"
    assert "video" in (fetched["error"] or "")


def test_failed_generation_marks_the_job_failed_and_refunds(client, png_bytes, monkeypatch):
    sku = _sku_with_photo(client, png_bytes)

    async def _boom(*args, **kwargs):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr("app.worker.generate_assets", _boom)
    client.get("/api/credits")

    job = client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]}).json()
    fetched = client.get(f"/api/jobs/{job['id']}").json()

    assert fetched["status"] == "failed"
    assert "provider exploded" in fetched["error"]

    from app.credits import get_balance

    assert get_balance(UID) == pytest.approx(5.0)  # hold fully returned


def test_assets_are_readable_before_the_job_finishes(client, png_bytes, monkeypatch):
    """Incremental delivery: a step's assets must exist the moment it reads `done`.

    The client reloads its grid whenever the completed-step count moves, so a write that
    landed after the status flip would be raced and the grid would come back empty. This
    records, at every job write, how many assets were already stored — and asserts the
    first write that reported a completed step already had that step's asset behind it.
    """
    from app.repo import get_repo

    sku = _sku_with_photo(client, png_bytes)
    repo = get_repo()
    observed: list[tuple[int, int]] = []          # (completed steps, assets stored)
    real_update = repo.update_job

    def spy(uid, job_id, patch):
        steps = patch.get("steps")
        if steps is not None:
            done = sum(1 for s in steps if s.get("status") == "done")
            stored = len([a for a in repo.list_assets(uid, sku["id"])
                          if not a.get("is_authentic")])
            observed.append((done, stored))
        return real_update(uid, job_id, patch)

    monkeypatch.setattr(repo, "update_job", spy)
    client.post(f"/api/skus/{sku['id']}/generate",
                json={"styles": ["studio", "lifestyle"]})

    first_done = next((row for row in observed if row[0] >= 1), None)
    assert first_done is not None, "no step ever reported done"
    assert first_done[1] >= 1, (
        f"the first completed step was published with {first_done[1]} assets stored — "
        "assets must be written before the step flips to done"
    )
    # And the second step's asset lands with the second completion, not at the end.
    second_done = next((row for row in observed if row[0] >= 2), None)
    assert second_done and second_done[1] >= 2


def test_a_crash_after_some_steps_keeps_what_was_produced(client, png_bytes, monkeypatch):
    """A mid-run failure must not discard — or give away free — the steps that succeeded.

    Assets are durable before the job ends now, so refunding the entire hold would hand the
    user real, provider-billed output for nothing.
    """
    from app.credits import get_balance

    sku = _sku_with_photo(client, png_bytes)

    import app.worker as worker_mod

    async def half_then_boom(uid, sku_doc, original, styles, **kwargs):
        reporter = kwargs["reporter"]
        from app.models import Style
        reporter.start(Style.studio)
        reporter.finish(Style.studio, [{
            "sku_id": sku_doc["id"], "sha256": "e" * 64, "modality": "image",
            "style": "studio", "is_authentic": False, "provider": "mock-dev",
            "model": "m", "cost_usd": 0.02,
        }])
        raise RuntimeError("provider exploded mid-run")

    monkeypatch.setattr(worker_mod, "generate_assets", half_then_boom)
    client.get("/api/credits")

    job = client.post(f"/api/skus/{sku['id']}/generate",
                      json={"styles": ["studio", "lifestyle"]}).json()
    fetched = client.get(f"/api/jobs/{job['id']}").json()

    assert fetched["status"] == "partial", "a run that produced assets is not a total failure"
    assert len(fetched["asset_ids"]) == 1
    assert "provider exploded" in fetched["error"]
    # The one completed step was billed, so the balance must reflect it — not a full refund.
    assert get_balance(UID) == pytest.approx(5.0 - 0.02)
