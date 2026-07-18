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
