"""Credit ledger: hold/settle accounting, refunds, and the pre-flight affordability gate."""
import pytest

from app.credits import InsufficientCredit, ensure_signup_grant, get_balance, grant, hold, settle
from app.models import LedgerKind


@pytest.fixture
def repo(client):
    """The in-memory repo backing `client`, already reset by the client fixture."""
    from app.repo import get_repo

    return get_repo()


UID = "dev-user"  # conftest's AUTH_DEV_BYPASS identity


def test_signup_grant_is_issued_once(client, repo):
    first = client.get("/api/credits").json()
    assert first["balance_usd"] == pytest.approx(5.0)
    assert first["granted_total_usd"] == pytest.approx(5.0)

    # Re-reading must not re-grant — the marker, not the balance, decides.
    again = client.get("/api/credits").json()
    assert again["balance_usd"] == pytest.approx(5.0)
    assert again["granted_total_usd"] == pytest.approx(5.0)


def test_signup_grant_not_reissued_after_spending_to_zero(client, repo):
    client.get("/api/credits")
    grant(UID, -5.0, actor_uid="test", note="drain")
    assert get_balance(UID) == pytest.approx(0.0)

    client.get("/api/credits")  # would re-grant if the check were `balance == 0`
    assert get_balance(UID) == pytest.approx(0.0)


def test_signup_grant_survives_a_concurrent_first_load(client, repo):
    """A fresh account's first page load hits several granting endpoints at once;
    exactly one may win the welcome credit — three did, before the atomic claim."""
    import threading

    uid = "race-user"
    barrier = threading.Barrier(6)

    def first_request() -> None:
        barrier.wait()
        ensure_signup_grant(uid)

    threads = [threading.Thread(target=first_request) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    grants = [e for e in repo.list_ledger(uid) if e["kind"] == LedgerKind.grant.value]
    assert len(grants) == 1
    assert get_balance(uid) == pytest.approx(5.0)
    assert repo.get_user(uid)["credits_granted_total"] == pytest.approx(5.0)


def test_hold_then_settle_under_estimate_refunds_difference(client, repo):
    client.get("/api/credits")
    hold(UID, job_id="j1", sku_id="s1", amount=0.08)
    assert get_balance(UID) == pytest.approx(4.92)

    settle(UID, job_id="j1", sku_id="s1", held=0.08, actual=0.03)
    # 5.00 - 0.03 actually spent
    assert get_balance(UID) == pytest.approx(4.97)

    user = repo.get_user(UID)
    assert user["credits_spent_total"] == pytest.approx(0.03)
    assert user["credits_held"] == pytest.approx(0.0)

    kinds = [e["kind"] for e in repo.list_ledger(UID)]
    assert LedgerKind.refund.value in kinds
    assert LedgerKind.hold.value in kinds


def test_settle_over_estimate_charges_the_overage(client, repo):
    client.get("/api/credits")
    hold(UID, job_id="j2", sku_id="s1", amount=0.08)
    settle(UID, job_id="j2", sku_id="s1", held=0.08, actual=0.20)

    assert get_balance(UID) == pytest.approx(4.80)
    assert repo.get_user(UID)["credits_spent_total"] == pytest.approx(0.20)


def test_failed_job_refunds_the_entire_hold(client, repo):
    client.get("/api/credits")
    hold(UID, job_id="j3", sku_id="s1", amount=0.50)
    settle(UID, job_id="j3", sku_id="s1", held=0.50, actual=None)

    assert get_balance(UID) == pytest.approx(5.0)
    assert repo.get_user(UID)["credits_spent_total"] == pytest.approx(0.0)


def test_hold_rejects_when_balance_is_short(client, repo):
    client.get("/api/credits")
    with pytest.raises(InsufficientCredit):
        hold(UID, job_id="j4", sku_id="s1", amount=99.0)
    assert get_balance(UID) == pytest.approx(5.0)  # nothing was taken


def test_ledger_balance_after_tracks_the_running_balance(client, repo):
    client.get("/api/credits")
    grant(UID, 2.0, actor_uid="admin", note="top-up")
    hold(UID, job_id="j5", sku_id="s1", amount=1.0)

    rows = repo.list_ledger(UID)  # newest first
    assert rows[0]["balance_after"] == pytest.approx(6.0)
    assert rows[1]["balance_after"] == pytest.approx(7.0)


def test_generate_is_rejected_when_credit_is_exhausted(client, png_bytes):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes(), "image/png")})
    client.get("/api/credits")
    grant(UID, -5.0, actor_uid="test", note="drain")

    res = client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio"]})
    assert res.status_code == 402
    assert "Insufficient credit" in res.json()["detail"]


def test_generation_settles_the_hold_and_leaves_none_outstanding(client, png_bytes, repo):
    sku = client.post("/api/skus", json={"title": "Mug"}).json()
    client.post(f"/api/skus/{sku['id']}/upload",
                files={"file": ("p.png", png_bytes(), "image/png")})
    client.post(f"/api/skus/{sku['id']}/generate", json={"styles": ["studio", "lifestyle"]})

    user = repo.get_user(UID)
    assert user["credits_held"] == pytest.approx(0.0)
    # The mock reports no provider cost, so the full hold comes back.
    assert user["credits_balance"] == pytest.approx(5.0)


def test_estimate_quotes_the_pack_before_running_it(client):
    res = client.get("/api/credits/estimate", params={"styles": ["studio", "video"]})
    assert res.status_code == 200
    body = res.json()
    # studio (1 image) + video (1 clip) — video dominates the quote.
    assert body["total_estimate_usd"] == pytest.approx(0.54)
    assert body["affordable"] is True
    assert body["eta_seconds"] > 0
    assert len(body["styles"]) == 2
