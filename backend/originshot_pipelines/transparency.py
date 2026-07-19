"""The transparency log — an append-only record of every manifest this instance issued.

OriginShot can already prove, from a file's own bytes, *how* it was made. It cannot yet
prove anything about **what else was made**. A seller who regenerated a product photo twelve
times until the scratch disappeared leaves no trace in a per-file manifest: each individual
file is honest, and the history is invisible. That gap is what a transparency log closes.

The structure is a hash chain, borrowed from Certificate Transparency. Every entry commits
to its predecessor:

    entry_hash[n] = SHA256(canonical_json({
        seq, prev_hash, subject_sha256, manifest_hash, kind, recorded_at
    }))

so an entry cannot be altered, reordered or removed without changing every hash after it.
Periodically the head of the chain is published to B2 as an immutable **checkpoint**. Once a
checkpoint is out, the history it commits to is fixed: producing a different past that still
matches that checkpoint would require finding a SHA-256 collision.

**What this proves, stated precisely.** Between two checkpoints the log is verifiably
append-only — the earlier head must be reachable by replaying entries forward to the later
one. An entry present in the log, plus a checkpoint covering it, is verifiable inclusion.
Both checks run offline against published data, with no trust in our servers, which is the
same standard the rest of this project holds itself to.

**What it does not prove, equally precisely.**

  * **No signatures.** There is no issuing keypair, so a checkpoint proves integrity against
    a published record, not authorship. Anyone who can write to the bucket could publish a
    checkpoint. Real CT logs sign their heads; that is the obvious next step and is not
    claimed here.
  * **No witnesses, so a split view is undetectable.** A dishonest operator could maintain
    two chains and show different checkpoints to different people. CT solves this with
    gossip between independent auditors. A single-operator log cannot, and saying otherwise
    would be the exact species of unearned claim this project exists to argue against.
  * **Absence proves little.** An asset missing from the log may never have been logged (the
    append is best-effort so a ledger outage cannot fail a paid generation). Presence plus a
    consistent chain is the load-bearing claim; absence is not evidence of anything.
  * **Inclusion proofs are O(n-k), not O(log n).** This is a chain, not a Merkle tree: to
    verify entry k you replay every entry after it. Correct, and honest about its cost. A
    Merkle tree is the right structure at scale and is the documented next step.

Everything here is a pure function of its inputs — no I/O, no config — so the standalone
verifier in `scripts/verify_ledger.py` runs the identical code a third party would.
"""
from __future__ import annotations

import hashlib
import json

# The chain's anchor. Entry 0 commits to this, so the log has a defined start rather than a
# nullable predecessor that verification code has to special-case in two places.
GENESIS_HASH = "0" * 64

# Fields covered by an entry's hash. Anything outside this set is presentation, not evidence;
# keeping the list explicit stops a later field from silently becoming load-bearing.
COMMITTED_FIELDS = ("seq", "prev_hash", "subject_sha256", "manifest_hash", "kind",
                    "recorded_at")


def canonical_bytes(payload: dict) -> bytes:
    """Deterministic JSON for hashing.

    Sorted keys and no incidental whitespace, so an entry hashes identically whichever
    implementation recomputes it — the property that makes third-party verification possible
    at all.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def entry_payload(*, seq: int, prev_hash: str, subject_sha256: str,
                  manifest_hash: str | None, kind: str, recorded_at: str) -> dict:
    """The exact object an entry's hash is taken over.

    `manifest_hash` is normalised to "" rather than left null: an authentic original has no
    manifest, and a JSON null hashes differently across implementations that distinguish
    absent from null.
    """
    return {
        "seq": int(seq),
        "prev_hash": prev_hash,
        "subject_sha256": subject_sha256,
        "manifest_hash": manifest_hash or "",
        "kind": kind,
        "recorded_at": recorded_at,
    }


def compute_entry_hash(payload: dict) -> str:
    """SHA-256 over the canonical form of an entry's committed fields."""
    trimmed = {k: payload[k] for k in COMMITTED_FIELDS}
    return hashlib.sha256(canonical_bytes(trimmed)).hexdigest()


def make_entry(*, seq: int, prev_hash: str, subject_sha256: str,
               manifest_hash: str | None, kind: str, recorded_at: str) -> dict:
    """Build a complete, self-describing log entry (payload plus its own hash)."""
    payload = entry_payload(
        seq=seq, prev_hash=prev_hash, subject_sha256=subject_sha256,
        manifest_hash=manifest_hash, kind=kind, recorded_at=recorded_at,
    )
    return {**payload, "entry_hash": compute_entry_hash(payload)}


def verify_chain(entries: list[dict], *, expect_head: str | None = None,
                 anchored: bool = True) -> dict:
    """Replay a chain and report whether it holds.

    Returns ``{consistent, size, head, broken_at, reason}``. `broken_at` is the sequence
    number of the first entry that fails, which is what makes a failure actionable rather
    than a bare False.

    `anchored=True` (a full log) requires the first entry to be seq 0 pointing at genesis.
    `anchored=False` verifies a *slice* starting mid-log, as an inclusion proof does: its
    first `prev_hash` is taken as given, since the preceding entries aren't in the proof.
    That is still sound — the slice's own hashes are recomputed, and each successor commits
    to its predecessor, so a forged first entry could not produce the real head that the
    genuine successors chain towards.
    """
    if not entries:
        head = GENESIS_HASH if anchored else (expect_head or GENESIS_HASH)
        return {"consistent": True, "size": 0, "head": head,
                "broken_at": None, "reason": None}

    base_seq = 0 if anchored else int(entries[0].get("seq") or 0)
    prev = GENESIS_HASH if anchored else str(entries[0].get("prev_hash") or GENESIS_HASH)
    head = prev

    for index, entry in enumerate(entries):
        expected_seq = base_seq + index
        seq = entry.get("seq")
        if seq != expected_seq:
            return _broken(expected_seq, head, f"expected seq {expected_seq}, found {seq!r} "
                                               "— entries are missing or out of order")
        if entry.get("prev_hash") != prev:
            return _broken(expected_seq, head, "prev_hash does not match the preceding entry "
                                               "— the chain has been reordered or spliced")
        recomputed = compute_entry_hash(entry)
        if recomputed != entry.get("entry_hash"):
            return _broken(expected_seq, head,
                           "entry_hash does not match the entry's own contents "
                           "— this entry was altered after it was written")
        prev = head = recomputed

    if expect_head is not None and head != expect_head:
        return {
            "consistent": False, "size": len(entries), "head": head,
            "broken_at": None,
            "reason": "the replayed head does not match the checkpoint — the log served "
                      "does not produce the head that was published",
        }
    return {"consistent": True, "size": len(entries), "head": head,
            "broken_at": None, "reason": None}


def _broken(seq: int, head: str, reason: str) -> dict:
    return {"consistent": False, "size": seq, "head": head, "broken_at": seq,
            "reason": reason}


def build_checkpoint(*, size: int, head: str, issued_at: str) -> dict:
    """A published commitment to the whole log up to `size` entries.

    Carries its own hash so a copy can be identified unambiguously, the same way every other
    artefact in this project is content-addressed.
    """
    body = {"size": int(size), "head": head, "issued_at": issued_at,
            "log_id": "originshot-transparency-v1"}
    return {**body, "checkpoint_hash": hashlib.sha256(canonical_bytes(body)).hexdigest()}


def verify_checkpoint(checkpoint: dict) -> bool:
    """Recompute a checkpoint's own hash — catches a tampered or truncated checkpoint file."""
    body = {k: checkpoint.get(k) for k in ("size", "head", "issued_at", "log_id")}
    expected = hashlib.sha256(canonical_bytes(body)).hexdigest()
    return expected == checkpoint.get("checkpoint_hash")


def verify_inclusion(entry: dict, following: list[dict], checkpoint: dict) -> dict:
    """Prove one entry sits in the log the checkpoint commits to.

    `following` is every entry after `entry`, in order. Replaying them forward must arrive at
    the checkpoint's head — which is only possible if `entry` is genuinely part of that
    history, since each successor commits to its predecessor's hash.
    """
    if not verify_checkpoint(checkpoint):
        return {"included": False, "reason": "the checkpoint's own hash does not match its "
                                             "contents"}
    # anchored=False: the proof starts at this entry, not at the log's beginning.
    chain = verify_chain([entry, *following], anchored=False)
    if not chain["consistent"]:
        return {"included": False, "reason": chain["reason"]}

    expected_size = int(entry.get("seq", 0)) + 1 + len(following)
    if expected_size != int(checkpoint.get("size", -1)):
        return {"included": False,
                "reason": f"proof covers {expected_size} entries but the checkpoint commits "
                          f"to {checkpoint.get('size')}"}
    if chain["head"] != checkpoint.get("head"):
        return {"included": False,
                "reason": "replaying the proof does not reproduce the published head"}
    return {"included": True, "reason": None}


def verify_consistency(earlier: dict, later: dict, entries: list[dict]) -> dict:
    """Prove the log only ever grew — the append-only property itself.

    `entries` is the full entry list covering `later`. The earlier checkpoint's head must be
    exactly the head produced by replaying the first `earlier.size` entries: if the operator
    had rewritten history before that point, the old head would no longer be reproducible.
    """
    if not (verify_checkpoint(earlier) and verify_checkpoint(later)):
        return {"consistent": False, "reason": "a checkpoint's own hash does not match"}
    if int(earlier["size"]) > int(later["size"]):
        return {"consistent": False, "reason": "the earlier checkpoint is larger than the "
                                               "later one — the log shrank"}

    prefix = verify_chain(entries[: int(earlier["size"])], expect_head=earlier["head"])
    if not prefix["consistent"]:
        return {"consistent": False,
                "reason": f"the log no longer reproduces the earlier checkpoint: "
                          f"{prefix['reason']}"}
    full = verify_chain(entries, expect_head=later["head"])
    if not full["consistent"]:
        return {"consistent": False, "reason": full["reason"]}
    return {"consistent": True, "reason": None}
