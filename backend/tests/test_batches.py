"""Catalog Mode — generation fanned out across many SKUs.

The interesting assertions here are not "did it generate": that path is covered by the
single-SKU tests and is deliberately the same code. They are the things a batch adds and a
batch can therefore get wrong — that every SKU still holds and settles its own credit, that
running out of money or quota blocks rather than fails, that one bad SKU doesn't take the
catalog with it, and that a bulk download is the same pack as a single download.
"""
import io
import zipfile

import pytest

UID = "dev-user"


def _sku(client, png_bytes, title="Mug", *, with_photo=True) -> dict:
    sku = client.post("/api/skus", json={"title": title}).json()
    if with_photo:
        client.post(f"/api/skus/{sku['id']}/upload",
                    files={"file": ("p.png", png_bytes(), "image/png")})
    return sku


def _catalog(client, png_bytes, n=3) -> list[dict]:
    return [_sku(client, png_bytes, f"Product {i}") for i in range(n)]


# ── Estimate ──────────────────────────────────────────────────────────
def test_estimate_quotes_the_whole_catalog(client, png_bytes):
    skus = _catalog(client, png_bytes, 3)
    body = client.post("/api/batches/estimate", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"],
    }).json()

    assert body["skus"] == 3
    assert body["per_sku_usd"] > 0
    assert body["total_estimate_usd"] == pytest.approx(body["per_sku_usd"] * 3)
    assert body["affordable"] is True
    assert body["quota_remaining"] > 0


def test_estimate_eta_reflects_concurrency_not_summed_work(client, png_bytes):
    """4 SKUs at concurrency 2 is ~2 waves, not 4 sequential packs."""
    skus = _catalog(client, png_bytes, 4)
    one = client.post("/api/batches/estimate", json={
        "sku_ids": [skus[0]["id"]], "styles": ["studio"]}).json()
    four = client.post("/api/batches/estimate", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"]}).json()

    assert four["eta_seconds"] < one["eta_seconds"] * 4
    assert four["eta_seconds"] == one["eta_seconds"] * 2


def test_estimate_refuses_a_sku_with_no_photo(client, png_bytes):
    good = _sku(client, png_bytes, "Has photo")
    bare = _sku(client, png_bytes, "No photo", with_photo=False)
    r = client.post("/api/batches/estimate", json={
        "sku_ids": [good["id"], bare["id"]], "styles": ["studio"]})
    assert r.status_code == 400
    assert "No photo" in r.json()["detail"]


def test_unknown_sku_is_named_not_silently_dropped(client, png_bytes):
    good = _sku(client, png_bytes)
    r = client.post("/api/batches", json={
        "sku_ids": [good["id"], "does-not-exist"], "styles": ["studio"]})
    assert r.status_code == 404
    assert "does-not-exist" in r.json()["detail"]


def test_another_users_sku_is_not_reachable_through_a_batch(client, png_bytes):
    """IDOR: the batch path must scope SKUs exactly as the single-SKU routes do."""
    from app.auth import CurrentUser, get_current_user
    from app.main import app as fastapi_app

    victim = _sku(client, png_bytes, "A's product")
    fastapi_app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        uid="user-b", email="b@example.com", email_verified=True)
    try:
        r = client.post("/api/batches", json={
            "sku_ids": [victim["id"]], "styles": ["studio"]})
        assert r.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()


# ── Running ───────────────────────────────────────────────────────────
def test_a_catalog_run_generates_for_every_sku(client, png_bytes):
    skus = _catalog(client, png_bytes, 3)
    batch = client.post("/api/batches", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"],
    }).json()

    # TestClient runs BackgroundTasks synchronously, so the batch is finished on return.
    final = client.get(f"/api/batches/{batch['id']}").json()
    assert final["status"] == "done"
    assert len(final["items"]) == 3
    for item in final["items"]:
        assert item["status"] == "done"
        assert item["job_id"], "every item should reference the job it ran"
        assert item["asset_count"] >= 1

    # And the assets really landed on each SKU, not just on the board.
    for sku in skus:
        assets = client.get(f"/api/skus/{sku['id']}/assets").json()
        assert any(not a["is_authentic"] for a in assets)


def test_every_sku_holds_and_settles_its_own_credit(client, png_bytes):
    """A batch must not be a hole through the denial-of-wallet controls.

    Each item runs the same hold/settle as a single-SKU job, so the ledger should show one
    hold per SKU and no outstanding holds once the catalog finishes.
    """
    from app.credits import summary

    client.get("/api/credits")
    skus = _catalog(client, png_bytes, 3)
    batch = client.post("/api/batches", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"],
    }).json()
    client.get(f"/api/batches/{batch['id']}")

    ledger = client.get("/api/credits/ledger").json()
    holds = [e for e in ledger if e["kind"] == "hold"]
    assert len(holds) == 3, "one hold per SKU"
    assert all(h["job_id"] for h in holds), "every hold must reference its job"
    assert summary(UID)["held_usd"] == pytest.approx(0.0), "no hold left outstanding"


def test_insufficient_credit_blocks_the_run_up_front(client, png_bytes, monkeypatch):
    """A catalog nobody can afford is refused before any provider is called."""
    import app.credits as credits_mod

    skus = _catalog(client, png_bytes, 3)
    monkeypatch.setattr(credits_mod, "get_balance", lambda uid: 0.01)
    r = client.post("/api/batches", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"]})
    assert r.status_code == 402


def test_running_out_mid_catalog_blocks_rather_than_fails(client, png_bytes, monkeypatch):
    """Balance exhausted partway through is `blocked`, not `failed`.

    Those SKUs never started and cost nothing, so the distinction is what tells a seller to
    top up and re-run instead of reporting that their photos broke.
    """
    import app.api.generate as generate_api
    from app.credits import InsufficientCredit

    skus = _catalog(client, png_bytes, 3)
    real_submit = generate_api.submit_generation
    calls = {"n": 0}

    def submit_then_run_dry(uid, sku, sku_id, styles, marketplaces):
        calls["n"] += 1
        if calls["n"] > 1:
            raise InsufficientCredit(0.0, 0.04)
        return real_submit(uid, sku, sku_id, styles, marketplaces)

    monkeypatch.setattr("app.api.generate.submit_generation", submit_then_run_dry)

    batch = client.post("/api/batches", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"],
        # Serialise so "the first one succeeds" is deterministic.
    }).json()
    final = client.get(f"/api/batches/{batch['id']}").json()

    statuses = sorted(i["status"] for i in final["items"])
    assert statuses.count("blocked") == 2
    assert "done" in statuses
    assert final["status"] == "partial"
    blocked = next(i for i in final["items"] if i["status"] == "blocked")
    assert "insufficient credit" in blocked["error"]


def test_daily_quota_exhaustion_blocks_remaining_items(client, png_bytes, monkeypatch):
    from app.config import get_settings

    skus = _catalog(client, png_bytes, 2)
    monkeypatch.setattr(get_settings(), "daily_generation_quota", 0)

    batch = client.post("/api/batches", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"]}).json()
    final = client.get(f"/api/batches/{batch['id']}").json()

    assert all(i["status"] == "blocked" for i in final["items"])
    assert "quota" in final["items"][0]["error"]
    assert final["status"] == "failed"      # nothing was produced


def test_one_failing_sku_does_not_take_the_catalog_with_it(client, png_bytes, monkeypatch):
    import app.worker as worker_mod

    skus = _catalog(client, png_bytes, 3)
    real_generate = worker_mod.generate_assets
    seen = {"n": 0}

    async def fail_the_second(uid, sku, original, styles, **kwargs):
        seen["n"] += 1
        if seen["n"] == 2:
            raise RuntimeError("provider exploded for this one")
        return await real_generate(uid, sku, original, styles, **kwargs)

    monkeypatch.setattr(worker_mod, "generate_assets", fail_the_second)

    batch = client.post("/api/batches", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"]}).json()
    final = client.get(f"/api/batches/{batch['id']}").json()

    assert final["status"] == "partial"
    assert sum(1 for i in final["items"] if i["status"] == "done") == 2
    assert sum(1 for i in final["items"] if i["status"] in ("failed", "partial")) == 1


def test_concurrency_is_bounded(client, png_bytes, monkeypatch):
    """More SKUs must not mean more simultaneous provider calls."""
    import app.worker as worker_mod
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "catalog_concurrency", 2)
    skus = _catalog(client, png_bytes, 5)

    real_generate = worker_mod.generate_assets
    state = {"now": 0, "peak": 0}

    async def counting(uid, sku, original, styles, **kwargs):
        state["now"] += 1
        state["peak"] = max(state["peak"], state["now"])
        try:
            return await real_generate(uid, sku, original, styles, **kwargs)
        finally:
            state["now"] -= 1

    monkeypatch.setattr(worker_mod, "generate_assets", counting)

    batch = client.post("/api/batches", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"]}).json()
    assert client.get(f"/api/batches/{batch['id']}").json()["concurrency"] == 2
    assert state["peak"] <= 2, f"ran {state['peak']} generations at once"


def test_batch_is_listed_for_its_owner_only(client, png_bytes):
    from app.auth import CurrentUser, get_current_user
    from app.main import app as fastapi_app

    skus = _catalog(client, png_bytes, 2)
    client.post("/api/batches", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"]})
    assert len(client.get("/api/batches").json()) == 1

    fastapi_app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        uid="user-b", email="b@example.com", email_verified=True)
    try:
        assert client.get("/api/batches").json() == []
    finally:
        fastapi_app.dependency_overrides.clear()


# ── Bulk export ───────────────────────────────────────────────────────
def test_catalog_export_ships_a_full_pack_per_sku(client, png_bytes):
    skus = _catalog(client, png_bytes, 2)
    batch = client.post("/api/batches", json={
        "sku_ids": [s["id"] for s in skus], "styles": ["studio"],
        "marketplaces": ["amazon"],
    }).json()
    client.get(f"/api/batches/{batch['id']}")

    r = client.post(f"/api/batches/{batch['id']}/export",
                    json={"marketplaces": ["amazon"]})
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    root = names[0].split("/")[0]

    assert f"{root}/catalog.json" in names
    assert f"{root}/README.txt" in names

    # Each product folder must be a COMPLETE pack — the same one a single export produces.
    product_dirs = {n.split("/")[1] for n in names
                    if n.startswith(f"{root}/OriginShot-")}
    assert len(product_dirs) == 2
    for folder in product_dirs:
        assert f"{root}/{folder}/README.txt" in names
        assert f"{root}/{folder}/pack.json" in names
        assert f"{root}/{folder}/disclosure.txt" in names
        assert f"{root}/{folder}/certificate.pdf" in names
        assert any(n.startswith(f"{root}/{folder}/verified/") for n in names)
        assert any(n.startswith(f"{root}/{folder}/amazon/") for n in names)


def test_catalog_export_matches_the_single_sku_export(client, png_bytes):
    """The bulk pack must not be a thinner version of the one sellers already trust."""
    sku = _sku(client, png_bytes, "Solo mug")
    batch = client.post("/api/batches", json={
        "sku_ids": [sku["id"]], "styles": ["studio"]}).json()
    client.get(f"/api/batches/{batch['id']}")

    single = zipfile.ZipFile(io.BytesIO(
        client.post(f"/api/skus/{sku['id']}/export", json={}).content))
    bulk = zipfile.ZipFile(io.BytesIO(
        client.post(f"/api/batches/{batch['id']}/export", json={}).content))

    single_root = single.namelist()[0].split("/")[0]
    bulk_root = bulk.namelist()[0].split("/")[0]
    single_entries = {n[len(single_root) + 1:] for n in single.namelist()}
    bulk_entries = {
        n.split("/", 2)[2] for n in bulk.namelist()
        if n.startswith(f"{bulk_root}/OriginShot-")
    }
    assert single_entries == bulk_entries


def test_catalog_export_skips_empty_skus_and_says_so(client, png_bytes):
    generated = _sku(client, png_bytes, "Generated")
    # Genuinely assetless: a SKU whose photo was uploaded already has one exportable asset
    # (the authentic original), and shipping that is correct — the skip path is for SKUs
    # that have nothing at all.
    bare = _sku(client, png_bytes, "Never generated", with_photo=False)
    batch = client.post("/api/batches", json={
        "sku_ids": [generated["id"]], "styles": ["studio"]}).json()
    client.get(f"/api/batches/{batch['id']}")

    # Add a SKU that was never generated directly onto the batch's item list.
    from app.repo import get_repo

    repo = get_repo()
    stored = repo.get_batch(UID, batch["id"])
    repo.update_batch(UID, batch["id"], {"items": stored["items"] + [
        {"sku_id": bare["id"], "title": "Never generated", "status": "done",
         "asset_count": 0}]})

    r = client.post(f"/api/batches/{batch['id']}/export", json={})
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    root = zf.namelist()[0].split("/")[0]
    readme = zf.read(f"{root}/README.txt").decode()

    assert "NOT INCLUDED" in readme
    assert "Never generated" in readme
    # It was skipped, not shipped as an empty folder.
    assert not any("never-generated" in n for n in zf.namelist())


def test_export_of_a_catalog_with_nothing_generated_is_a_clear_400(client, png_bytes):
    sku = _sku(client, png_bytes, with_photo=False)
    from app.repo import get_repo

    batch = get_repo().create_batch(UID, {
        "title": None, "status": "queued", "styles": ["studio"], "marketplaces": [],
        "concurrency": 1, "items": [{"sku_id": sku["id"], "title": "Mug",
                                     "status": "pending", "asset_count": 0}],
    })
    r = client.post(f"/api/batches/{batch['id']}/export", json={})
    assert r.status_code == 400
    assert "generated assets" in r.json()["detail"]
