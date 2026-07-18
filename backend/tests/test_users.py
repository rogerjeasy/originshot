"""User registration + roles, and that the email-verified gate is gone."""


def test_register_defaults_to_customer_role(client):
    r = client.post("/api/users", json={"username": "roger"})
    assert r.status_code == 200
    body = r.json()
    assert body["uid"] == "dev-user"
    assert body["username"] == "roger"
    assert body["roles"] == ["customer"]          # array → supports multiple roles later
    assert body["created_at"]


def test_register_is_idempotent_and_keeps_roles(client):
    client.post("/api/users", json={"username": "roger"})
    # Simulate a later role grant, then re-register (as happens on every sign-in).
    from app.repo import get_repo

    get_repo().set_user("dev-user", {"roles": ["customer", "admin"]})
    again = client.post("/api/users", json={"username": "ignored-second-time"}).json()
    assert again["roles"] == ["customer", "admin"]  # never downgraded
    assert again["username"] == "roger"             # first username wins


def test_me_creates_profile_on_first_read(client):
    body = client.get("/api/me").json()
    assert body["uid"] == "dev-user"
    assert body["roles"] == ["customer"]


def test_create_sku_no_longer_requires_verified_email(client):
    # dev-bypass user is verified, but the point is the endpoint uses get_current_user now.
    r = client.post("/api/skus", json={"title": "Mug"})
    assert r.status_code == 201
