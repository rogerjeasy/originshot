"""Credit ledger — hold/settle accounting over real provider cost.

Generation spends money at a provider the moment it runs, so "do you have enough credit?"
has to be answered *before* the call, while "how much did that actually cost?" is only known
*after*. A single debit can't honestly do both. So this module uses the same hold/settle
shape a payment processor uses:

  1. **hold** — at submit time we debit `pricing.estimate_styles(...)`, the ceiling quote.
     The money is gone from the user's spendable balance immediately, which is what makes
     the pre-flight check meaningful: two concurrent jobs can't both pass a balance check
     and then overspend, because the first one already moved the balance down.
  2. **settle** — when the job finishes we know the real `Step.cost_usd` total. We write a
     settle entry for the difference: refund when the run came in under the quote (the
     normal case, since the quote is a ceiling), extra debit when it came in over.
     A job that produced nothing refunds the entire hold — a user is never charged for a
     failure they didn't get assets from.

Every movement writes a ledger row with the resulting balance, so the balance is always
reconstructable from the ledger rather than being a mutable number nobody can audit.

Balance updates go through `repo.adjust_credits`, which is transactional on Firestore — a
read-modify-write here would lose debits under concurrent jobs.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, status

from .config import get_settings
from .models import LedgerKind, utcnow
from .repo import get_repo

log = logging.getLogger("originshot.credits")


class InsufficientCredit(HTTPException):
    """402 — the user cannot afford this run. Carries the numbers so the UI can explain."""

    def __init__(self, balance: float, required: float) -> None:
        super().__init__(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Insufficient credit: this pack needs ${required:.2f} but your balance is "
            f"${balance:.2f}. Ask an admin to top up.",
        )
        self.balance = balance
        self.required = required


def _record(uid: str, kind: LedgerKind, amount: float, balance_after: float,
            seq: int, **fields) -> dict:
    """Write one immutable ledger row. `amount` is signed: negative = money leaving.

    `seq` comes from the same atomic operation that moved the balance, and orders rows that
    share a `created_at` — see repo._ledger_order.
    """
    entry = {
        "uid": uid,
        "kind": kind.value,
        "amount_usd": round(amount, 4),
        "balance_after": round(balance_after, 4),
        "seq": seq,
        "created_at": utcnow(),
        **fields,
    }
    return get_repo().add_ledger_entry(uid, entry)


def get_balance(uid: str) -> float:
    user = get_repo().get_user(uid) or {}
    return round(float(user.get("credits_balance") or 0.0), 4)


def summary(uid: str) -> dict:
    """Everything the credits UI needs in one read."""
    settings = get_settings()
    repo = get_repo()
    user = repo.get_user(uid) or {}
    balance = round(float(user.get("credits_balance") or 0.0), 4)
    granted = round(float(user.get("credits_granted_total") or 0.0), 4)
    spent = round(float(user.get("credits_spent_total") or 0.0), 4)
    return {
        "balance_usd": balance,
        "granted_total_usd": granted,
        "spent_total_usd": spent,
        "held_usd": round(float(user.get("credits_held") or 0.0), 4),
        "daily_quota": settings.daily_generation_quota,
        "daily_used": repo.count_generations_today(uid),
        "low_balance": balance < settings.low_balance_threshold,
    }


def ensure_signup_grant(uid: str) -> None:
    """Give a brand-new user their starting credit, exactly once.

    Keyed off a `signup_grant_at` marker rather than "balance == 0", which would re-grant
    every time a user spent down to zero. The marker is *claimed atomically before* the
    money moves: a fresh account's first page load hits several endpoints that all call
    this, and a read-check here would let each of them grant. Claim-first also picks the
    safer crash mode — a process dying mid-way shorts the user one welcome credit an admin
    can re-issue, instead of minting duplicates nobody notices.
    """
    repo = get_repo()
    user = repo.get_user(uid) or {}
    if user.get("signup_grant_at"):
        return  # fast path: already granted, skip the transactional claim
    if not repo.claim_signup_grant(uid):
        return  # lost the race to a concurrent request that is doing the grant
    amount = get_settings().signup_credit_grant
    if amount <= 0:
        return
    balance, seq = repo.adjust_credits(uid, amount, granted_delta=amount)
    _record(uid, LedgerKind.grant, amount, balance, seq,
            note="Welcome credit", actor_uid="system")
    log.info("signup grant: %s +$%.2f", uid, amount)


def grant(uid: str, amount: float, *, actor_uid: str, note: str | None = None) -> dict:
    """Admin top-up (or negative correction). Returns the ledger row."""
    if amount == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Amount must be non-zero")
    kind = LedgerKind.grant if amount > 0 else LedgerKind.adjust
    balance, seq = get_repo().adjust_credits(
        uid, amount, granted_delta=amount if amount > 0 else 0.0
    )
    return _record(uid, kind, amount, balance, seq, note=note, actor_uid=actor_uid)


def hold(uid: str, *, job_id: str, sku_id: str, amount: float) -> float:
    """Debit the up-front quote. Raises InsufficientCredit when the user can't cover it.

    The check and the debit are both here so there's no window between them where a second
    request could pass the same check.
    """
    repo = get_repo()
    balance = get_balance(uid)
    if amount > balance:
        raise InsufficientCredit(balance, amount)
    new_balance, seq = repo.adjust_credits(uid, -amount, held_delta=amount)
    _record(
        uid, LedgerKind.hold, -amount, new_balance, seq,
        job_id=job_id, sku_id=sku_id, note="Estimated cost held for generation",
    )
    return new_balance


def settle(uid: str, *, job_id: str, sku_id: str, held: float, actual: float | None) -> float:
    """Reconcile a finished job against its hold.

    `actual=None` means the provider reported no cost at all (dev mock, or a run that failed
    before billing) — treated as zero, so the whole hold comes back.
    """
    repo = get_repo()
    actual = round(float(actual or 0.0), 4)
    delta = round(held - actual, 4)  # positive ⇒ refund owed to the user

    # Whatever happened, the hold is no longer outstanding and the actual is now real spend.
    balance, seq = repo.adjust_credits(
        uid, delta, held_delta=-held, spent_delta=actual
    )
    if delta > 0:
        _record(
            uid, LedgerKind.refund, delta, balance, seq, job_id=job_id, sku_id=sku_id,
            note=f"Refund: actual ${actual:.4f} under held ${held:.4f}",
        )
    elif delta < 0:
        _record(
            uid, LedgerKind.debit, delta, balance, seq, job_id=job_id, sku_id=sku_id,
            note=f"Overage: actual ${actual:.4f} over held ${held:.4f}",
        )
    else:
        _record(
            uid, LedgerKind.debit, 0.0, balance, seq, job_id=job_id, sku_id=sku_id,
            note=f"Settled at estimate (${actual:.4f})",
        )
    log.info("job %s settled: held $%.4f actual $%.4f", job_id, held, actual)
    return balance
