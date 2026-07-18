#!/usr/bin/env python
"""Seed the judge demo account — a signed-in first click that lands on real work.

Creates (idempotently) a Firebase Auth user for judges, grants it a small credit
balance through the normal ledger, and clones the showcase SKUs — including every
asset document — from a source account into the demo account.

Cloning copies *documents only*. The bucket is content-addressed, so the demo
account's assets point at the exact same B2 objects (and sidecar manifests) as the
originals: zero new storage, zero generation spend, and every hash still resolves
against /verify. The global `asset_index` is left untouched — it already maps each
sha to the source documents, which is all the public verifier needs.

Usage (from the repo root, backend venv active, .env populated):

    poetry run python ../scripts/seed-demo-account.py                # defaults
    poetry run python ../scripts/seed-demo-account.py --password X   # rotate password

Re-running is safe: the user is fetched-or-created, the grant happens once (keyed
off `signup_grant_at`), and SKUs already cloned (marker: `cloned_from`) are skipped.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent

DEFAULT_EMAIL = "judge@originshot.app"
DEFAULT_PASSWORD = "verify-the-pixels"
DEFAULT_CREDITS = 3.0     # enough to run a real pack or two, small enough to cap abuse
MIN_ASSETS_TO_CLONE = 5   # only showcase-grade SKUs, not test scraps


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", default=DEFAULT_EMAIL)
    ap.add_argument("--password", default=DEFAULT_PASSWORD)
    ap.add_argument("--credits", type=float, default=DEFAULT_CREDITS)
    ap.add_argument("--source-email", default=None,
                    help="account to clone SKUs from (default: the first admin)")
    args = ap.parse_args()

    load_dotenv(REPO / ".env")
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if cred_path and not os.path.isabs(cred_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(REPO / cred_path)
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        sys.exit("GOOGLE_APPLICATION_CREDENTIALS is not set — populate .env first.")

    import firebase_admin
    from firebase_admin import auth, credentials, firestore

    firebase_admin.initialize_app(
        credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]))
    db = firestore.client()

    # ── 1. Auth user ─────────────────────────────────────────────────────
    try:
        user = auth.get_user_by_email(args.email)
        auth.update_user(user.uid, password=args.password)
        print(f"auth: {args.email} exists ({user.uid}) — password refreshed")
    except auth.UserNotFoundError:
        user = auth.create_user(
            email=args.email, password=args.password, display_name="OriginShot Judge")
        print(f"auth: created {args.email} ({user.uid})")
    demo_uid = user.uid

    # ── 2. Profile + credit grant through the ledger ─────────────────────
    user_ref = db.collection("users").document(demo_uid)
    profile = user_ref.get().to_dict() or {}
    if profile.get("signup_grant_at"):
        print(f"credits: already granted (balance ${profile.get('credits_balance', 0):.2f})")
    else:
        seq = int(profile.get("ledger_seq") or 0) + 1
        balance = round(float(profile.get("credits_balance") or 0.0) + args.credits, 4)
        user_ref.set({
            "uid": demo_uid,
            "email": args.email,
            "username": "judge-demo",
            "roles": ["customer"],
            "credits_balance": balance,
            "credits_granted_total": round(
                float(profile.get("credits_granted_total") or 0.0) + args.credits, 4),
            "credits_spent_total": float(profile.get("credits_spent_total") or 0.0),
            "credits_held": 0.0,
            "ledger_seq": seq,
            "signup_grant_at": utcnow(),
            "created_at": profile.get("created_at") or utcnow(),
            "updated_at": utcnow(),
        }, merge=True)
        ledger_ref = db.collection("sellers").document(demo_uid).collection("ledger").document()
        ledger_ref.set({
            "id": ledger_ref.id,
            "uid": demo_uid,
            "kind": "grant",
            "amount_usd": round(args.credits, 4),
            "balance_after": balance,
            "seq": seq,
            "note": "Judge demo balance",
            "actor_uid": "seed-script",
            "created_at": utcnow(),
        })
        print(f"credits: granted ${args.credits:.2f} (balance ${balance:.2f})")

    # ── 3. Pick the source account ───────────────────────────────────────
    source_uid = None
    for u in db.collection("users").stream():
        d = u.to_dict()
        if args.source_email and d.get("email") == args.source_email:
            source_uid = u.id
            break
        if not args.source_email and "admin" in (d.get("roles") or []):
            source_uid = u.id
            break
    if not source_uid:
        sys.exit("No source account found — pass --source-email.")
    if source_uid == demo_uid:
        sys.exit("Source and demo account are the same user.")
    print(f"source: {source_uid}")

    # ── 4. Clone showcase SKUs (documents only — same B2 objects) ────────
    demo_skus = db.collection("sellers").document(demo_uid).collection("skus")
    already = {d.to_dict().get("cloned_from") for d in demo_skus.stream()}

    src_skus = db.collection("sellers").document(source_uid).collection("skus")
    for sku_snap in src_skus.stream():
        sku = sku_snap.to_dict()
        assets = [a.to_dict() for a in sku_snap.reference.collection("assets").stream()]
        if len(assets) < MIN_ASSETS_TO_CLONE:
            print(f"skip: {sku.get('title')!r} ({len(assets)} assets < {MIN_ASSETS_TO_CLONE})")
            continue
        if sku["id"] in already:
            print(f"skip: {sku.get('title')!r} already cloned from {sku['id']}")
            continue

        new_ref = demo_skus.document()
        new_ref.set({
            "id": new_ref.id,
            "owner_uid": demo_uid,
            "title": sku.get("title"),
            "category": sku.get("category"),
            "description": sku.get("description"),
            "original_sha256": sku.get("original_sha256"),
            "created_at": utcnow(),
            "cloned_from": sku["id"],
        })
        for asset in sorted(assets, key=lambda a: str(a.get("created_at"))):
            a_ref = new_ref.collection("assets").document()
            clone = {**asset, "id": a_ref.id, "owner_uid": demo_uid, "sku_id": new_ref.id}
            a_ref.set(clone)
        print(f"cloned: {sku.get('title')!r} — {len(assets)} assets -> sku {new_ref.id}")

    print("\nDemo account ready:")
    print(f"  email:    {args.email}")
    print(f"  password: {args.password}")


if __name__ == "__main__":
    main()
