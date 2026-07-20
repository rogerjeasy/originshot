"""Update + delete SKU endpoints, and their owner-or-admin authorization boundary.

The security property under test is the boundary itself: an authenticated user must be able
to edit and delete their OWN products, an admin must be able to moderate ANYONE's, and a
non-owner who is not an admin must not even learn that a stranger's SKU exists (404, not 403).
"""
import pytest

from app.models import Role

UID = "dev-user"  # conftest's AUTH_DEV_BYPASS identity


@pytest.fixture
def repo(client):
    from app.repo import get_repo

    return get_repo()


def _make_admin(repo, uid=UID):
    repo.set_user(uid, {"roles": [Role.customer.value, Role.admin.value]})


def _seed_other_sku(repo, title="Stranger's mug"):
    """A SKU owned by a different user, created directly through the repo."""
    return repo.create_sku("other-user", {"title": title, "description": "not yours"})


# ── Update ─────────────────────────────────────────────────────────────
def test_owner_can_update_own_sku(client):
    sku = client.post("/api/skus", json={"title": "Mug", "description": "old"}).json()
    r = client.patch(f"/api/skus/{sku['id']}", json={"description": "new copy", "category": "Home"})
    assert r.status_code == 200
    body = r.json()
    assert body["description"] == "new copy"
    assert body["category"] == "Home"
    assert body["title"] == "Mug"  # untouched


def test_partial_update_leaves_omitted_fields_and_cannot_null_title(client):
    sku = client.post("/api/skus", json={"title": "Keep me", "description": "d"}).json()
    # title:null is ignored (SkuOut requires a title) — the field is left as-is.
    r = client.patch(f"/api/skus/{sku['id']}", json={"title": None, "category": "C"})
    assert r.status_code == 200
    assert r.json()["title"] == "Keep me"
    assert r.json()["category"] == "C"


def test_empty_update_is_rejected(client):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    assert client.patch(f"/api/skus/{sku['id']}", json={}).status_code == 400


def test_update_rejects_an_over_long_title(client):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    assert client.patch(f"/api/skus/{sku['id']}", json={"title": "x" * 141}).status_code == 422


def test_non_owner_cannot_update_and_gets_404(client, repo):
    other = _seed_other_sku(repo)
    r = client.patch(f"/api/skus/{other['id']}", json={"title": "hijacked"})
    assert r.status_code == 404
    assert repo.find_sku_by_id(other["id"])[1]["title"] == "Stranger's mug"  # unchanged


def test_admin_can_update_another_users_sku(client, repo):
    other = _seed_other_sku(repo)
    _make_admin(repo)
    r = client.patch(f"/api/skus/{other['id']}", json={"title": "moderated"})
    assert r.status_code == 200
    # The edit landed on the real owner's record, not the admin's namespace.
    owner_uid, sku = repo.find_sku_by_id(other["id"])
    assert owner_uid == "other-user"
    assert sku["title"] == "moderated"


# ── Delete ─────────────────────────────────────────────────────────────
def test_owner_can_delete_own_sku_and_it_disappears(client):
    sku = client.post("/api/skus", json={"title": "Trash me"}).json()
    r = client.delete(f"/api/skus/{sku['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == sku["id"]
    assert client.get(f"/api/skus/{sku['id']}").status_code == 404
    assert all(s["id"] != sku["id"] for s in client.get("/api/skus").json())


def test_delete_removes_assets_and_indexes_but_not_the_ledger(client, repo):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    sid = sku["id"]
    # Two assets: an authentic original and a generated one carrying a pHash.
    repo.add_asset(UID, {"sku_id": sid, "sha256": "a" * 64, "phash": "0f0f0f0f0f0f0f0f",
                         "style": "studio", "is_authentic": False, "modality": "image"})
    repo.add_asset(UID, {"sku_id": sid, "sha256": "b" * 64, "style": "original",
                         "is_authentic": True, "modality": "image"})
    # A ledger entry for one of them — this must survive the delete.
    from app import transparency
    transparency.record_asset({"sha256": "a" * 64, "is_authentic": False})
    size_before = repo.transparency_size()

    r = client.delete(f"/api/skus/{sid}")
    assert r.status_code == 200
    assert r.json()["assets_removed"] == 2
    assert repo.find_asset_by_sha("a" * 64) is None      # asset + index gone
    assert repo.find_similar_by_phash("0f0f0f0f0f0f0f0f", 0) is None
    assert repo.transparency_size() == size_before        # ledger untouched (append-only)


def test_non_owner_cannot_delete_and_gets_404(client, repo):
    other = _seed_other_sku(repo)
    assert client.delete(f"/api/skus/{other['id']}").status_code == 404
    assert repo.find_sku_by_id(other["id"]) is not None    # still there


def test_admin_can_delete_another_users_sku(client, repo):
    other = _seed_other_sku(repo)
    repo.add_asset("other-user", {"sku_id": other["id"], "sha256": "c" * 64,
                                  "style": "studio", "is_authentic": False, "modality": "image"})
    _make_admin(repo)
    r = client.delete(f"/api/skus/{other['id']}")
    assert r.status_code == 200
    assert r.json()["assets_removed"] == 1
    assert repo.find_sku_by_id(other["id"]) is None


def test_deleting_a_missing_sku_is_404(client):
    assert client.delete("/api/skus/does-not-exist").status_code == 404
