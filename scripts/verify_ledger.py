#!/usr/bin/env python3
"""Independently verify OriginShot's transparency log.

This script talks only to the public, unauthenticated `/api/ledger` endpoints and recomputes
everything locally. It never asks the server whether the log is valid — it downloads the raw
entries and the published checkpoint and replays the chain itself. That is the whole point:
a log verified only by the party who wrote it is not evidence.

    # Is the published log internally consistent?
    python scripts/verify_ledger.py --api https://originshot-api.onrender.com

    # Is one specific file in it?
    python scripts/verify_ledger.py --sha <sha256-of-a-file-you-hold>

    # Did the log only ever grow between two runs? (append-only, the real claim)
    python scripts/verify_ledger.py --save yesterday.json      # ... later ...
    python scripts/verify_ledger.py --against yesterday.json

Only dependency is `httpx`. The chain logic is vendored below rather than imported from the
backend, so this file can be handed to a sceptic on its own — reading 40 lines of hashing is
a far lower bar than trusting an installed package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys

GENESIS_HASH = "0" * 64
COMMITTED_FIELDS = ("seq", "prev_hash", "subject_sha256", "manifest_hash", "kind",
                    "recorded_at")

# The OriginShot signing public key, committed here on purpose: a checkpoint's Ed25519
# signature is verified against THIS value — obtained from the source repository, independent
# of the API server that produced the signature. That independence is the whole point; a key
# fetched from the same server as the signature would prove nothing. A rotation is a visible,
# dated change to this constant in git history.
PUBLIC_KEY_HEX = "8d9ef557d70d7637580aceed82a1c396a1984ed18f1d4dd2551f854ff039e355"

OK, BAD, INFO = "  OK  ", " FAIL ", "  ..  "


def verify_signature(digest_hex: str, signature: dict | None) -> bool | None:
    """Verify an Ed25519 signature over `digest_hex` against the committed public key.

    Returns True/False, or None when a signature can't be checked here (none present, or no
    Ed25519 implementation installed). Signature checking is the one thing that needs more
    than httpx, so it degrades to a note rather than a hard dependency: the chain-consistency
    checks — the historical core of this script — still run with httpx alone.
    """
    if not signature or not signature.get("signature"):
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return None
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX)).verify(
            bytes.fromhex(signature["signature"]), digest_hex.encode("ascii")
        )
        return True
    except Exception:  # noqa: BLE001 — any failure is an invalid signature
        return False


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def entry_hash(entry: dict) -> str:
    return hashlib.sha256(canonical({k: entry[k] for k in COMMITTED_FIELDS})).hexdigest()


def checkpoint_hash(cp: dict) -> str:
    body = {k: cp.get(k) for k in ("size", "head", "issued_at", "log_id")}
    return hashlib.sha256(canonical(body)).hexdigest()


def replay(entries: list[dict]) -> tuple[bool, str, str | None]:
    """Walk the chain. Returns (ok, head, reason)."""
    prev = head = GENESIS_HASH
    for i, e in enumerate(entries):
        if e.get("seq") != i:
            return False, head, f"entry {i}: sequence is {e.get('seq')!r}, expected {i}"
        if e.get("prev_hash") != prev:
            return False, head, f"entry {i}: prev_hash does not match the previous entry"
        recomputed = entry_hash(e)
        if recomputed != e.get("entry_hash"):
            return False, head, f"entry {i}: contents do not match its own entry_hash"
        prev = head = recomputed
    return True, head, None


def fetch_all(client, api: str, *, expected: int | None = None) -> list[dict]:
    """Page through the whole log.

    Guarded against a server that ignores `start`: this script is meant to be pointed at
    endpoints you do not trust, and a verifier that hangs on a hostile response is a
    verifier nobody runs twice. Stops as soon as a page fails to advance the sequence.
    """
    entries: list[dict] = []
    while True:
        page = client.get(f"{api}/api/ledger/entries",
                          params={"start": len(entries), "limit": 500}).json()
        if not page:
            return entries
        # The first row of each page must be the next entry we asked for.
        if int(page[0].get("seq", -1)) != len(entries):
            print(f"{BAD} server ignored pagination: asked for entry {len(entries)}, "
                  f"got {page[0].get('seq')!r} — refusing to keep fetching")
            return entries + page if not entries else entries
        entries.extend(page)
        if expected is not None and len(entries) >= expected:
            return entries[:expected]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="https://originshot-api.onrender.com",
                    help="API base URL")
    ap.add_argument("--sha", help="verify inclusion of one asset hash")
    ap.add_argument("--save", metavar="FILE", help="save the current checkpoint for later")
    ap.add_argument("--against", metavar="FILE",
                    help="check the log still reproduces a checkpoint saved earlier")
    args = ap.parse_args()

    try:
        import httpx
    except ImportError:
        print("this script needs httpx:  pip install httpx")
        return 2

    api = args.api.rstrip("/")
    failures = 0
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        print(f"\nOriginShot transparency log — {api}\n")

        status = client.get(f"{api}/api/ledger").json()
        print(f"{INFO} log {status['log_id']}  size={status['size']}  "
              f"head={status['head'][:16]}…")
        if status.get("checkpoint_lag"):
            print(f"{INFO} {status['checkpoint_lag']} entr"
                  f"{'y' if status['checkpoint_lag'] == 1 else 'ies'} appended since the "
                  "last checkpoint (in the log, not yet committed to by a published head)")

        # 1. The chain itself.
        entries = fetch_all(client, api, expected=int(status.get("size") or 0) or None)
        ok, head, reason = replay(entries)
        print(f"{OK if ok else BAD} chain replays over {len(entries)} entries"
              + ("" if ok else f" — {reason}"))
        failures += 0 if ok else 1

        # 2. The published checkpoint, and whether the log still produces it.
        cp = client.get(f"{api}/api/ledger/checkpoint")
        if cp.status_code == 404:
            print(f"{INFO} no checkpoint published yet")
            cp = None
        else:
            cp = cp.json()
            self_ok = checkpoint_hash(cp) == cp.get("checkpoint_hash")
            print(f"{OK if self_ok else BAD} checkpoint hash matches its own contents "
                  f"(size={cp['size']}, {cp['checkpoint_hash'][:16]}…)")
            failures += 0 if self_ok else 1

            prefix_ok, prefix_head, _ = replay(entries[: int(cp["size"])])
            matches = prefix_ok and prefix_head == cp["head"]
            print(f"{OK if matches else BAD} replaying the first {cp['size']} entries "
                  f"reproduces the published head")
            failures += 0 if matches else 1
            if cp.get("b2_key"):
                print(f"{INFO} checkpoint published to B2 at {cp['b2_key']}")

            # The signature: is this checkpoint signed by the key committed in this repo?
            sig_ok = verify_signature(cp.get("checkpoint_hash", ""), cp.get("signature"))
            if sig_ok is True:
                print(f"{OK} checkpoint signature verifies against the repo public key "
                      f"{PUBLIC_KEY_HEX[:16]}… — issued by this instance, not merely by "
                      "someone with bucket write access")
            elif sig_ok is False:
                print(f"{BAD} checkpoint carries a signature that does NOT verify against the "
                      "repo public key")
                failures += 1
            elif cp.get("signature"):
                print(f"{INFO} checkpoint is signed, but no Ed25519 library is installed to "
                      "check it (pip install cryptography to verify authorship)")
            else:
                print(f"{INFO} checkpoint is not signed (no issuing key configured)")

            if cp.get("retained_until"):
                print(f"{INFO} checkpoint is immutable under B2 Object Lock until "
                      f"{cp['retained_until']}")

        # 3. Inclusion of one asset.
        if args.sha:
            r = client.get(f"{api}/api/ledger/proof/{args.sha.strip().lower()}")
            if r.status_code == 404:
                print(f"{INFO} {args.sha[:16]}… is not in the log "
                      "(appends are best-effort, so this alone proves nothing)")
            else:
                proof = r.json()
                chain = [proof["entry"], *proof["following"]]
                inc_ok, inc_head, inc_reason = replay(chain)
                target = proof["checkpoint"]["head"]
                good = inc_ok and inc_head == target
                print(f"{OK if good else BAD} {args.sha[:16]}… included at seq "
                      f"{proof['entry']['seq']}"
                      + ("" if good else f" — {inc_reason or 'head mismatch'}"))
                failures += 0 if good else 1

        # 4. Append-only across time — the claim that actually matters.
        if args.against:
            old = json.loads(open(args.against, encoding="utf-8").read())
            print(f"\n{INFO} comparing against {args.against} "
                  f"(size={old['size']}, saved {old['issued_at']})")
            if int(old["size"]) > len(entries):
                print(f"{BAD} the log SHRANK: was {old['size']} entries, now {len(entries)}")
                failures += 1
            else:
                p_ok, p_head, _ = replay(entries[: int(old["size"])])
                same = p_ok and p_head == old["head"]
                print(f"{OK if same else BAD} history before entry {old['size']} is "
                      f"unchanged" + ("" if same else " — EARLIER ENTRIES WERE REWRITTEN"))
                failures += 0 if same else 1

        if args.save and cp:
            with open(args.save, "w", encoding="utf-8") as fh:
                json.dump(cp, fh, indent=2)
            print(f"\n{INFO} checkpoint saved to {args.save} — re-run later with "
                  f"--against {args.save} to prove the log only grew")

    print()
    if failures:
        print(f"{failures} check(s) FAILED\n")
        return 1
    print("All checks passed.\n")
    print("What this does and does not establish: the published log is internally "
          "consistent,\nreproduces its checkpoint, and (when signed) was issued by the holder "
          "of the private key\nmatching the public key committed in this script — so a "
          "checkpoint can no longer be forged\nby anyone with mere write access to the "
          "bucket. What a single signing key still cannot do\nis rule out a split view: a "
          "dishonest operator could sign two different chains and show them\nto different "
          "people. That needs independent witnesses; saving a checkpoint and re-checking\n"
          "later (--save / --against) remains the strongest guarantee available without "
          "them.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
