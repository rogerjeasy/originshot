"""Admin surface: the authorization boundary, and the aggregates behind it.

The boundary tests matter most — /api/admin is the one place that reads across users, so
"a non-admin cannot reach it" is a security property, not a UI detail.
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


def test_non_admin_is_refused(client, repo):
    client.get("/api/me")  # exists, but holds only the default customer role
    for path in ("/api/admin/overview", "/api/admin/users", "/api/admin/jobs",
                 "/api/admin/ledger", "/api/admin/health"):
        assert client.get(path).status_code == 403, path


def test_admin_role_grants_access(client, repo):
    client.get("/api/me")
    _make_admin(repo)
    assert client.get("/api/admin/overview").status_code == 200


def test_bootstrap_allowlist_seeds_the_admin_role(client, repo, monkeypatch):
    """An allowlisted, verified email becomes admin and has the role persisted."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "dev@originshot.local")
    get_settings.cache_clear()
    try:
        client.get("/api/me")
        assert client.get("/api/admin/overview").status_code == 200
        assert Role.admin.value in repo.get_user(UID)["roles"]
    finally:
        get_settings.cache_clear()


def test_bootstrap_requires_a_verified_email(client, repo, monkeypatch):
    """An unverified email must not be able to claim an allowlisted address."""
    from app import admin as admin_mod
    from app.auth import CurrentUser
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_EMAILS", "spoofed@originshot.local")
    get_settings.cache_clear()
    try:
        unverified = CurrentUser(
            uid="u2", email="spoofed@originshot.local", email_verified=False
        )
        assert admin_mod.is_admin(unverified) is False
    finally:
        get_settings.cache_clear()


def test_overview_reports_platform_totals(client, repo, png_bytes):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes(), "image/png")})
    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})
    _make_admin(repo)

    body = client.get("/api/admin/overview").json()
    assert body["users_total"] >= 1
    assert body["skus_total"] == 1
    assert body["assets_total"] >= 2          # original + generated
    assert body["jobs_total"] == 1
    assert body["success_rate_pct"] == pytest.approx(100.0)
    assert body["b2"]["backend"] == "local"   # LocalStorage under test


def test_success_rate_ignores_in_flight_jobs(client, repo):
    """A merely-queued job is neither a success nor a failure."""
    repo.create_job(UID, {"sku_id": "s1", "requested_styles": ["studio"]})
    _make_admin(repo)

    body = client.get("/api/admin/overview").json()
    assert body["jobs_total"] == 1
    assert body["success_rate_pct"] == pytest.approx(100.0)


def test_admin_can_grant_credits_and_it_is_attributed(client, repo):
    client.get("/api/credits")
    _make_admin(repo)

    res = client.post(f"/api/admin/users/{UID}/credits",
                      json={"amount_usd": 10.0, "note": "hackathon top-up"})
    assert res.status_code == 200
    entry = res.json()
    assert entry["amount_usd"] == pytest.approx(10.0)
    assert entry["balance_after"] == pytest.approx(15.0)
    assert entry["actor_uid"] == UID
    assert entry["note"] == "hackathon top-up"


def test_grant_to_unknown_user_is_404(client, repo):
    _make_admin(repo)
    res = client.post("/api/admin/users/nobody/credits", json={"amount_usd": 1.0})
    assert res.status_code == 404


def test_admin_cannot_remove_their_own_admin_role(client, repo):
    """Otherwise a deployment can be left with no admins and no way back."""
    client.get("/api/me")
    _make_admin(repo)

    res = client.post(f"/api/admin/users/{UID}/roles", json={"roles": ["customer"]})
    assert res.status_code == 400
    assert Role.admin.value in repo.get_user(UID)["roles"]


def test_admin_can_set_roles_on_another_user(client, repo):
    repo.set_user("other", {"email": "other@example.com", "roles": ["customer"]})
    _make_admin(repo)

    res = client.post("/api/admin/users/other/roles", json={"roles": ["customer", "seller"]})
    assert res.status_code == 200
    assert sorted(res.json()["roles"]) == ["customer", "seller"]


def test_users_listing_includes_credit_position(client, repo, png_bytes):
    client.get("/api/credits")
    _make_admin(repo)

    rows = client.get("/api/admin/users").json()
    me = next(r for r in rows if r["uid"] == UID)
    assert me["credits_balance"] == pytest.approx(5.0)


def test_provider_budget_is_derived_not_fetched_from_gmi(client, repo):
    """The panel must never imply it read a balance from GMI.

    GMI's inference API has no balance endpoint (probed 2026-07-18), so the flag stays False
    and the source string has to say where the number actually came from.
    """
    _make_admin(repo)

    res = client.post("/api/admin/provider-budget", json={"budget_usd": 50.0})
    assert res.status_code == 200
    body = res.json()
    assert body["budget_usd"] == pytest.approx(50.0)
    assert body["configured"] is True
    assert body["provider_api_supports_balance"] is False
    assert "not read from GMI" in body["source"]


def test_provider_budget_subtracts_metered_spend(client, repo):
    """Remaining is budget minus real per-step provider cost, not our user-facing charges."""
    _make_admin(repo)
    client.post("/api/admin/provider-budget", json={"budget_usd": 10.0})
    repo.create_job(UID, {"sku_id": "s1", "requested_styles": ["studio"],
                          "cost_actual": 2.5, "status": "done"})

    body = client.get("/api/admin/provider-budget").json()
    assert body["metered_spend_usd"] == pytest.approx(2.5)
    assert body["remaining_usd"] == pytest.approx(7.5)


def test_provider_budget_requires_admin(client, repo):
    client.get("/api/me")
    assert client.get("/api/admin/provider-budget").status_code == 403
    assert client.post("/api/admin/provider-budget",
                       json={"budget_usd": 5.0}).status_code == 403


def test_health_reports_checks_and_provider_config(client, repo):
    _make_admin(repo)
    body = client.get("/api/admin/health").json()
    names = {c["name"] for c in body["checks"]}
    assert names == {"firebase", "b2"}
    assert body["generation_mode"] == "mock"
    # conftest blanks every provider key.
    assert all(v is False for v in body["providers"].values())
