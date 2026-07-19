"""The Library — cross-SKU listing with server-side filters.

Isolation is the assertion that matters most: the library is the one read that spans a
user's whole catalog, which makes it the one read where an ownership-scoping mistake
would leak *everything* at once.
"""
UID = "dev-user"


def _seed_two_products(client, png_bytes):
    """Two SKUs, each with an original + mock-generated pack (distinct colors ⇒ distinct hashes)."""
    ids = []
    for i, color in enumerate([(200, 40, 40), (40, 200, 40)]):
        sku = client.post("/api/skus", json={"title": f"Product {i}"}).json()
        client.post(f"/api/skus/{sku['id']}/upload",
                    files={"file": ("p.png", png_bytes(color=color), "image/png")})
        client.post(f"/api/skus/{sku['id']}/generate",
                    json={"styles": ["studio", "lifestyle"]})
        ids.append(sku["id"])
    return ids


def test_library_spans_skus_and_presigns(client, png_bytes):
    _seed_two_products(client, png_bytes)
    assets = client.get("/api/assets").json()
    # 2 originals + 2×2 generated (mock: studio + lifestyle each)
    assert len(assets) == 6
    assert {a["sku_id"] for a in assets} and len({a["sku_id"] for a in assets}) == 2
    assert all(a["url"] for a in assets)  # every row carries a servable URL
    # Newest first — the second product's assets precede the first's.
    created = [a["created_at"] for a in assets]
    assert created == sorted(created, reverse=True)


def test_library_filters(client, png_bytes):
    _seed_two_products(client, png_bytes)

    studio = client.get("/api/assets?style=studio").json()
    assert len(studio) == 2 and all(a["style"] == "studio" for a in studio)

    originals = client.get("/api/assets?authentic=true").json()
    assert len(originals) == 2 and all(a["is_authentic"] for a in originals)

    generated = client.get("/api/assets?authentic=false").json()
    assert len(generated) == 4 and not any(a["is_authentic"] for a in generated)

    # Hash-prefix search resolves the same handle the ledger and /verify use.
    target = originals[0]["sha256"]
    hits = client.get(f"/api/assets?q={target[:12]}").json()
    assert any(a["sha256"] == target for a in hits)
    # A generated asset is also findable via its parent's hash prefix.
    assert any(a["parent_sha256"] == target for a in hits if not a["is_authentic"])

    # QA filter: the mock attaches no reports, so "none" is everything and "passed" empty —
    # absence of a report must never be presented as a pass.
    assert len(client.get("/api/assets?qa=none").json()) == 6
    assert client.get("/api/assets?qa=passed").json() == []

    assert len(client.get("/api/assets?limit=3").json()) == 3

    assert client.get("/api/assets?qa=bogus").status_code == 422


def test_library_is_owner_scoped(client, png_bytes):
    """Another user's catalog must never appear, whatever filters are sent."""
    from app.repo import get_repo

    _seed_two_products(client, png_bytes)
    get_repo().add_asset("someone-else", {
        "sku_id": "foreign-sku", "sha256": "f" * 64, "b2_key": "assets/ff/ff/foreign.png",
        "modality": "image", "style": "studio", "is_authentic": False,
    })

    for query in ("", "?style=studio", "?q=ffff"):
        rows = client.get(f"/api/assets{query}").json()
        assert all(a["owner_uid"] == UID for a in rows)
