"""Credits — balance, ledger, and the pre-flight cost quote for a proposed run."""
from fastapi import APIRouter, Depends, Query

from .. import credits, pricing
from ..auth import CurrentUser, get_current_user
from ..models import CostEstimateOut, CreditSummaryOut, LedgerEntryOut, Style

router = APIRouter(tags=["credits"])


@router.get("/credits", response_model=CreditSummaryOut)
def credit_summary(user: CurrentUser = Depends(get_current_user)):
    """Balance, lifetime totals, and today's quota usage."""
    credits.ensure_signup_grant(user.uid)
    return credits.summary(user.uid)


@router.get("/credits/ledger", response_model=list[LedgerEntryOut])
def ledger(limit: int = Query(default=50, ge=1, le=200),
           user: CurrentUser = Depends(get_current_user)):
    """This user's transaction history, newest first. Every balance change is here."""
    from ..repo import get_repo

    return get_repo().list_ledger(user.uid, limit=limit)


@router.get("/credits/estimate", response_model=CostEstimateOut)
def estimate(styles: list[Style] = Query(default=[Style.studio, Style.lifestyle]),
             user: CurrentUser = Depends(get_current_user)):
    """Quote a pack before running it, so the cost is visible at the moment of choosing.

    The quote is the ceiling the run will be held against — see pricing.py.
    """
    credits.ensure_signup_grant(user.uid)
    total = pricing.estimate_styles(styles)
    balance = credits.get_balance(user.uid)
    return CostEstimateOut(
        styles=pricing.breakdown(styles),
        total_estimate_usd=total,
        eta_seconds=pricing.eta_seconds(styles),
        balance_usd=balance,
        affordable=balance >= total,
        basis=pricing.ESTIMATE_ONLY,
    )
