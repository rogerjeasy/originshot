def test_brand_kit_put_then_get(client):
    r = client.put("/api/brand-kit", json={"vibe": "warm minimal", "lighting": "soft natural"})
    assert r.status_code == 200
    assert r.json()["vibe"] == "warm minimal"

    g = client.get("/api/brand-kit")
    assert g.status_code == 200
    assert g.json()["vibe"] == "warm minimal"
    assert g.json()["lighting"] == "soft natural"


def test_generate_stores_marketplaces(client, png_bytes):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload", files={"file": ("p.png", png_bytes(), "image/png")})
    job = client.post(
        f"/api/skus/{sku['id']}/generate",
        json={"styles": ["studio"], "marketplaces": ["amazon", "etsy"]},
    ).json()
    fetched = client.get(f"/api/jobs/{job['id']}").json()
    assert set(fetched["marketplaces"]) == {"amazon", "etsy"}


def test_export_includes_presets(client, png_bytes):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload", files={"file": ("p.png", png_bytes(), "image/png")})
    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})

    r = client.post(f"/api/skus/{sku['id']}/export", json={"marketplaces": ["amazon"]})
    assert r.status_code == 200
    data = r.json()
    assert any(p["marketplace"] == "amazon" and p["width"] == 2000 for p in data["presets"])
    assert data["count"] >= 2  # original + studio
