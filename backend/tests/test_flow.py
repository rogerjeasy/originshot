def test_create_and_list_sku(client):
    r = client.post("/api/skus", json={"title": "Blue Mug"})
    assert r.status_code == 201
    sku = r.json()
    assert sku["title"] == "Blue Mug"
    assert sku["owner_uid"] == "dev-user"

    listed = client.get("/api/skus")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_generate_requires_upload_first(client):
    sku = client.post("/api/skus", json={"title": "X"}).json()
    r = client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})
    assert r.status_code == 400


def test_full_upload_generate_verify_flow(client, png_bytes):
    sku = client.post("/api/skus", json={"title": "Ceramic Mug"}).json()

    files = {"file": ("photo.png", png_bytes(), "image/png")}
    up = client.post(f"/api/skus/{sku['id']}/upload", files=files)
    assert up.status_code == 201
    original = up.json()
    assert original["is_authentic"] is True
    assert original["style"] == "original"
    assert original["url"]  # presigned/local URL present

    gen = client.post(
        f"/api/skus/{sku['id']}/generate", json={"styles": ["studio", "lifestyle"]}
    )
    assert gen.status_code == 202
    job_id = gen.json()["id"]

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "done"            # BackgroundTasks complete within TestClient
    assert len(job["asset_ids"]) == 2         # studio + lifestyle (mock), video skipped

    assets = client.get(f"/api/skus/{sku['id']}/assets").json()
    styles = {a["style"] for a in assets}
    assert {"original", "studio", "lifestyle"} <= styles

    # public provenance verify on the authentic original
    v = client.get(f"/api/verify/{original['sha256']}").json()
    assert v["found"] is True and v["verified"] is True and v["is_authentic"] is True


def test_analytics(client, png_bytes):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    files = {"file": ("photo.png", png_bytes(), "image/png")}
    client.post(f"/api/skus/{sku['id']}/upload", files=files)
    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})

    a = client.get("/api/analytics").json()
    assert a["total_assets"] >= 2
    assert "dedup_savings_pct" in a
    # Mock generation bills nothing, so real settled spend is zero — and stays separate
    # from the list-price estimate, which counts the generated asset.
    assert a["actual_cost_usd"] == 0.0
    assert a["estimated_cost_usd"] > 0
    assert "ledger" in a["cost_source"]
    # The mock's `passthrough` model is in no fallback list, so the rate reads 0.
    assert a["fallback_rate"] == 0.0


def test_analytics_settled_spend_and_fallback_rate(client, png_bytes):
    """actual_cost_usd tracks the ledger; fallback_rate is measured from job steps."""
    import pytest
    from app import credits
    from app.repo import get_repo
    from originshot_pipelines.registry import IMAGE_EDIT_MODEL, VIDEO_FALLBACKS

    sku = client.post("/api/skus", json={"title": "Lens"}).json()
    files = {"file": ("photo.png", png_bytes(), "image/png")}
    client.post(f"/api/skus/{sku['id']}/upload", files=files)
    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})

    # Settle a job exactly the way the worker does: hold the quote, settle at real cost.
    credits.grant("dev-user", 5.0, actor_uid="test", note="seed")
    credits.hold("dev-user", job_id="j-settle", sku_id=sku["id"], amount=1.0)
    credits.settle("dev-user", job_id="j-settle", sku_id=sku["id"], held=1.0, actual=0.54)

    # A finished job whose video step was served by a fallback model. Together with the
    # mock studio step above that makes 3 done steps, 1 of them a fallback.
    get_repo().create_job("dev-user", {
        "sku_id": sku["id"],
        "status": "done",
        "requested_styles": ["studio", "video"],
        "steps": [
            {"style": "studio", "status": "done", "model": IMAGE_EDIT_MODEL},
            {"style": "video", "status": "done", "model": VIDEO_FALLBACKS[0]},
        ],
    })

    a = client.get("/api/analytics").json()
    assert a["actual_cost_usd"] == 0.54
    assert a["fallback_rate"] == pytest.approx(33.3)
