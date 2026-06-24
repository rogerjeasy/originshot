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
