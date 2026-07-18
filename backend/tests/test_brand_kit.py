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


def test_export_returns_marketplace_zip(client, png_bytes):
    """The export is a real ZIP: verifiable masters + marketplace renditions + disclosure."""
    import io
    import json
    import zipfile

    from PIL import Image

    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload", files={"file": ("p.png", png_bytes(), "image/png")})
    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})

    r = client.post(f"/api/skus/{sku['id']}/export", json={"marketplaces": ["amazon"]})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert ".zip" in r.headers["content-disposition"]

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert zf.testzip() is None  # archive is not corrupt
    names = zf.namelist()

    # Byte-exact masters (provenance intact) and the paperwork are always present.
    assert any(n.startswith("OriginShot-mug/verified/") for n in names), names
    assert any(n.endswith("/disclosure.txt") for n in names)
    assert any(n.endswith("/README.txt") for n in names)

    # Amazon renditions exist and hit the preset's exact dimensions.
    amazon = [n for n in names if "/amazon/" in n]
    assert amazon, names
    with Image.open(io.BytesIO(zf.read(amazon[0]))) as img:
        assert img.size == (2000, 2000)

    index = json.loads(zf.read(next(n for n in names if n.endswith("/pack.json"))))
    assert index["marketplaces"] == ["amazon"]
    assert index["asset_count"] >= 2  # original + studio


def test_export_without_marketplaces_still_ships_masters(client, png_bytes):
    """No marketplace selected ⇒ verified masters only, no per-channel folders."""
    import io
    import zipfile

    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload", files={"file": ("p.png", png_bytes(), "image/png")})

    r = client.post(f"/api/skus/{sku['id']}/export", json={"marketplaces": []})
    assert r.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert any("/verified/" in n for n in names)
    assert not any("/amazon/" in n for n in names)


def test_export_rejects_empty_sku(client):
    sku = client.post("/api/skus", json={"title": "Empty"}).json()
    assert client.post(f"/api/skus/{sku['id']}/export", json={"marketplaces": []}).status_code == 400
