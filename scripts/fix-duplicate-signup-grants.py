#!/usr/bin/env python
"""Correct accounts hit by the signup-grant race — append-only, never by deleting rows.

Before `claim_signup_grant` existed, `ensure_signup_grant` checked the `signup_grant_at`
marker and only set it *after* granting. A fresh account's first page load calls several
granting endpoints concurrently, so more than one could pass the check and the same user
ended up with two or three "Welcome credit" rows (observed live: 3 × $5.00).

This script finds every affected account and appends ONE compensating `adjust` entry per
account for the excess, bringing `credits_balance` and `credits_granted_total` back to a
single welcome credit. The duplicate grant rows are left in place: the ledger is the
audit trail, and the honest record of a bug is a correction entry, not a rewrite.

Idempotent: prior corrections (matched on the note prefix) are netted out before deciding
whether anything is still owed, so re-running is safe.

Usage (from the repo root, backend venv active, .env populated):

    python scripts/fix-duplicate-signup-grants.py            # report only
    python scripts/fix-duplicate-signup-grants.py --apply    # write the corrections
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent

WELCOME_NOTE = "Welcome credit"
CORRECTION_PREFIX = "Correction: duplicate welcome credit"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the corrections (default: report only)")
    args = ap.parse_args()

    load_dotenv(REPO / ".env")
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if cred_path and not os.path.isabs(cred_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(REPO / cred_path)
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        sys.exit("GOOGLE_APPLICATION_CREDENTIALS is not set — populate .env first.")

    import firebase_admin
    from firebase_admin import credentials, firestore

    firebase_admin.initialize_app(
        credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]))
    db = firestore.client()

    touched = 0
    for user_snap in db.collection("users").stream():
        uid = user_snap.id
        profile = user_snap.to_dict() or {}
        rows = [d.to_dict() for d in
                db.collection("sellers").document(uid).collection("ledger").stream()]

        welcomes = [r for r in rows
                    if r.get("kind") == "grant" and r.get("note") == WELCOME_NOTE]
        if len(welcomes) <= 1:
            continue

        corrected = sum(-float(r.get("amount_usd") or 0.0) for r in rows
                        if r.get("kind") == "adjust"
                        and str(r.get("note", "")).startswith(CORRECTION_PREFIX))
        total = sum(float(r.get("amount_usd") or 0.0) for r in welcomes)
        keep = float(welcomes[0].get("amount_usd") or 0.0)  # one legitimate grant stays
        excess = round(total - keep - corrected, 4)

        label = profile.get("email") or profile.get("username") or uid
        print(f"{label}: {len(welcomes)} welcome credits totalling ${total:.2f}, "
              f"already corrected ${corrected:.2f}, excess ${excess:.2f}")
        if excess <= 0:
            print("  nothing owed — skipping")
            continue

        touched += 1
        if not args.apply:
            print(f"  would append adjust of -${excess:.2f} (dry run)")
            continue

        user_ref = db.collection("users").document(uid)

        @firestore.transactional
        def _correct(txn, ref=user_ref, amount=excess):
            snap = ref.get(transaction=txn)
            cur = snap.to_dict() if snap.exists else {}
            balance = round(float(cur.get("credits_balance") or 0.0) - amount, 4)
            seq = int(cur.get("ledger_seq") or 0) + 1
            txn.set(ref, {
                "uid": ref.id,
                "credits_balance": balance,
                "credits_granted_total": round(
                    float(cur.get("credits_granted_total") or 0.0) - amount, 4),
                "ledger_seq": seq,
            }, merge=True)
            return balance, seq

        balance, seq = _correct(db.transaction())
        ledger_ref = db.collection("sellers").document(uid).collection("ledger").document()
        ledger_ref.set({
            "id": ledger_ref.id,
            "uid": uid,
            "kind": "adjust",
            "amount_usd": round(-excess, 4),
            "balance_after": balance,
            "seq": seq,
            "created_at": utcnow(),
            "note": (f"{CORRECTION_PREFIX} — the signup race granted "
                     f"{len(welcomes)}× instead of once"),
            "actor_uid": "system",
        })
        print(f"  corrected: -${excess:.2f} -> balance ${balance:.2f}")
        if balance < 0:
            print("  WARNING: balance went negative — the phantom credit was already spent")

    verb = "corrected" if args.apply else "needing correction"
    print(f"\n{touched} account(s) {verb}")


if __name__ == "__main__":
    main()
