"""Data access layer.

Two implementations behind one interface:
  * InMemoryRepo  — dev/tests; zero external dependencies.
  * FirestoreRepo — production; owner-scoped documents under sellers/{uid}/...

`get_repo()` picks Firestore when Firebase is configured, otherwise in-memory.
Every method takes the authenticated `uid` and scopes data to it (no cross-user access).
See ../docs/SECURITY.md §4.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from .config import get_settings
from .models import JobStatus, utcnow


def _new_id() -> str:
    return uuid.uuid4().hex


def _today_key(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).strftime("%Y-%m-%d")


def _ledger_order(entry: dict) -> tuple:
    """Sort key for ledger rows: timestamp first, then the per-user sequence.

    The sequence is the tie-breaker that makes ordering correct. Windows' system clock has
    ~15ms granularity, so several ledger writes in one request routinely share a
    `created_at` — sorting on the timestamp alone let rows come back in an order where the
    running balance appeared to move backwards.
    """
    return (entry.get("created_at"), int(entry.get("seq") or 0))


class Repo(Protocol):
    def create_sku(self, uid: str, data: dict) -> dict: ...
    def get_sku(self, uid: str, sku_id: str) -> dict | None: ...
    def list_skus(self, uid: str) -> list[dict]: ...
    def set_sku_original(self, uid: str, sku_id: str, sha256: str) -> None: ...

    def update_sku(self, uid: str, sku_id: str, patch: dict) -> dict | None: ...
    # Delete a SKU and its assets (+ global sha/phash index entries). Returns the removed
    # asset docs so the caller can clean up B2 media. Ledger entries are append-only and are
    # NEVER touched — a deleted asset's provenance record staying in the log is correct: the
    # log records that it was made, and deletion does not unmake that history.
    def delete_sku(self, uid: str, sku_id: str) -> list[dict]: ...
    # Global resolve by id (admin moderation only). Returns (owner_uid, sku) or None.
    def find_sku_by_id(self, sku_id: str) -> tuple[str, dict] | None: ...

    def add_asset(self, uid: str, asset: dict) -> dict: ...
    def list_assets(self, uid: str, sku_id: str) -> list[dict]: ...
    def list_assets_for_user(self, uid: str) -> list[dict]: ...  # cross-SKU library view
    def find_asset_by_sha(self, sha256: str) -> dict | None: ...  # public verify (global)
    # Verify in the Wild: nearest generated asset by perceptual hash, or None. Global, for the
    # public verifier — a buyer checking a re-encoded listing photo has no account.
    def find_similar_by_phash(self, phash: str, max_distance: int) -> dict | None: ...

    def create_job(self, uid: str, job: dict) -> dict: ...
    def get_job(self, uid: str, job_id: str) -> dict | None: ...
    def list_jobs(self, uid: str, limit: int = 200) -> list[dict]: ...
    def update_job(self, uid: str, job_id: str, patch: dict) -> dict | None: ...

    def count_generations_today(self, uid: str) -> int: ...

    # Catalog batches — a run across many SKUs at once.
    def create_batch(self, uid: str, batch: dict) -> dict: ...
    def get_batch(self, uid: str, batch_id: str) -> dict | None: ...
    def list_batches(self, uid: str, limit: int = 50) -> list[dict]: ...
    def update_batch(self, uid: str, batch_id: str, patch: dict) -> dict | None: ...

    def get_brand_kit(self, uid: str) -> dict | None: ...
    def set_brand_kit(self, uid: str, data: dict) -> dict: ...

    def get_user(self, uid: str) -> dict | None: ...
    def set_user(self, uid: str, data: dict) -> dict: ...  # upsert-merge; returns stored doc

    # Credits — `adjust_credits` MUST be atomic (concurrent jobs debit the same balance).
    # Returns (new_balance, seq) where `seq` is a per-user monotonic counter used to order
    # ledger rows written within the same clock tick.
    def adjust_credits(self, uid: str, delta: float, *, granted_delta: float = 0.0,
                       spent_delta: float = 0.0,
                       held_delta: float = 0.0) -> tuple[float, int]: ...
    # Atomically set `signup_grant_at` iff unset; True means this caller won and owes the
    # user their welcome credit. MUST be atomic — the grant endpoints race on first load.
    def claim_signup_grant(self, uid: str) -> bool: ...
    def add_ledger_entry(self, uid: str, entry: dict) -> dict: ...
    def list_ledger(self, uid: str, limit: int = 50) -> list[dict]: ...

    # Platform-wide operator settings (single document, admin-writable).
    def get_platform_config(self) -> dict: ...
    def set_platform_config(self, patch: dict) -> dict: ...

    # Transparency log — global, append-only, not per-seller. `append_transparency_entry`
    # MUST be atomic: two concurrent appends that both read the same head would produce two
    # entries claiming the same predecessor, which silently forks the chain.
    def append_transparency_entry(self, body: dict) -> dict: ...
    def list_transparency_entries(self, *, start: int = 0,
                                  limit: int | None = None) -> list[dict]: ...
    def transparency_size(self) -> int: ...
    def find_transparency_entry(self, subject_sha256: str) -> dict | None: ...
    def save_checkpoint(self, checkpoint: dict) -> dict: ...
    def latest_checkpoint(self) -> dict | None: ...

    # Dispute evidence reports. Deliberately NOT under sellers/{uid}: a report is issued to
    # whoever ran the check — usually a buyer or a marketplace with no account here — and its
    # entire purpose is being resolvable by a third party from the id printed on the PDF.
    def add_dispute_report(self, report: dict) -> dict: ...
    def get_dispute_report(self, report_id: str) -> dict | None: ...
    def update_dispute_report(self, report_id: str, patch: dict) -> dict | None: ...

    # Admin — cross-user reads. Only ever called behind require_admin.
    def list_users(self) -> list[dict]: ...
    def list_all_jobs(self, limit: int = 200) -> list[dict]: ...
    def list_all_assets(self) -> list[dict]: ...
    def list_all_skus(self) -> list[dict]: ...
    def list_all_ledger(self, limit: int = 100) -> list[dict]: ...


# ── In-memory (dev/tests) ─────────────────────────────────────────────
class InMemoryRepo:
    def __init__(self) -> None:
        self._skus: dict[str, dict] = {}
        self._assets: dict[str, dict] = {}
        self._jobs: dict[str, dict] = {}
        self._brand: dict[str, dict] = {}
        self._users: dict[str, dict] = {}
        self._ledger: list[dict] = []
        self._platform: dict = {}
        self._reports: dict[str, dict] = {}
        self._batches: dict[str, dict] = {}
        self._log: list[dict] = []
        self._checkpoints: list[dict] = []
        # Serializes the read-head/append cycle, mirroring the Firestore transaction.
        self._log_lock = threading.Lock()
        # Serializes read-modify-write on balances, mirroring the Firestore transaction.
        self._credit_lock = threading.Lock()

    def create_sku(self, uid: str, data: dict) -> dict:
        sku = {"id": _new_id(), "owner_uid": uid, "original_sha256": None,
               "created_at": utcnow(), **data}
        self._skus[sku["id"]] = sku
        return sku

    def get_sku(self, uid: str, sku_id: str) -> dict | None:
        sku = self._skus.get(sku_id)
        return sku if sku and sku["owner_uid"] == uid else None

    def list_skus(self, uid: str) -> list[dict]:
        return sorted(
            [s for s in self._skus.values() if s["owner_uid"] == uid],
            key=lambda s: s["created_at"], reverse=True,
        )

    def set_sku_original(self, uid: str, sku_id: str, sha256: str) -> None:
        sku = self.get_sku(uid, sku_id)
        if sku:
            sku["original_sha256"] = sha256

    def update_sku(self, uid: str, sku_id: str, patch: dict) -> dict | None:
        sku = self.get_sku(uid, sku_id)
        if sku:
            sku.update(patch)
        return sku

    def delete_sku(self, uid: str, sku_id: str) -> list[dict]:
        if not self.get_sku(uid, sku_id):
            return []
        removed = [a for a in self._assets.values()
                   if a["owner_uid"] == uid and a.get("sku_id") == sku_id]
        for a in removed:
            self._assets.pop(a["id"], None)
        self._skus.pop(sku_id, None)
        return removed

    def find_sku_by_id(self, sku_id: str) -> tuple[str, dict] | None:
        sku = self._skus.get(sku_id)
        return (sku["owner_uid"], sku) if sku else None

    def add_asset(self, uid: str, asset: dict) -> dict:
        doc = {"id": _new_id(), "owner_uid": uid, "created_at": utcnow(), **asset}
        self._assets[doc["id"]] = doc
        return doc

    def list_assets(self, uid: str, sku_id: str) -> list[dict]:
        return sorted(
            [a for a in self._assets.values() if a["owner_uid"] == uid and a["sku_id"] == sku_id],
            key=lambda a: a["created_at"],
        )

    def list_assets_for_user(self, uid: str) -> list[dict]:
        return sorted(
            [a for a in self._assets.values() if a["owner_uid"] == uid],
            key=lambda a: a["created_at"], reverse=True,
        )

    def find_asset_by_sha(self, sha256: str) -> dict | None:
        for a in self._assets.values():
            if a["sha256"] == sha256:
                return a
        return None

    def find_similar_by_phash(self, phash: str, max_distance: int) -> dict | None:
        from originshot_pipelines.perceptual import hamming

        best: dict | None = None
        best_dist = max_distance + 1
        for a in self._assets.values():
            d = hamming(phash, a.get("phash"))
            if d is not None and d < best_dist:
                best, best_dist = a, d
        if best is None:
            return None
        return {**best, "phash_distance": best_dist}

    def create_job(self, uid: str, job: dict) -> dict:
        doc = {"id": _new_id(), "owner_uid": uid, "status": JobStatus.queued.value,
               "asset_ids": [], "created_at": utcnow(), "finished_at": None, **job}
        self._jobs[doc["id"]] = doc
        return doc

    def get_job(self, uid: str, job_id: str) -> dict | None:
        job = self._jobs.get(job_id)
        return job if job and job["owner_uid"] == uid else None

    def list_jobs(self, uid: str, limit: int = 200) -> list[dict]:
        rows = [j for j in self._jobs.values() if j["owner_uid"] == uid]
        return sorted(rows, key=lambda j: j["created_at"], reverse=True)[:limit]

    def update_job(self, uid: str, job_id: str, patch: dict) -> dict | None:
        job = self.get_job(uid, job_id)
        if job:
            job.update(patch)
        return job

    def count_generations_today(self, uid: str) -> int:
        today = _today_key()
        return sum(
            1 for j in self._jobs.values()
            if j["owner_uid"] == uid and _today_key(j["created_at"]) == today
        )

    # ── Batches ───────────────────────────────────────────────────────
    def create_batch(self, uid: str, batch: dict) -> dict:
        doc = {"id": _new_id(), "owner_uid": uid, "created_at": utcnow(), **batch}
        self._batches[doc["id"]] = doc
        return doc

    def get_batch(self, uid: str, batch_id: str) -> dict | None:
        batch = self._batches.get(batch_id)
        return batch if batch and batch["owner_uid"] == uid else None

    def list_batches(self, uid: str, limit: int = 50) -> list[dict]:
        rows = [b for b in self._batches.values() if b["owner_uid"] == uid]
        return sorted(rows, key=lambda b: b["created_at"], reverse=True)[:limit]

    def update_batch(self, uid: str, batch_id: str, patch: dict) -> dict | None:
        batch = self.get_batch(uid, batch_id)
        if batch:
            batch.update(patch)
        return batch

    def get_brand_kit(self, uid: str) -> dict | None:
        return self._brand.get(uid)

    def set_brand_kit(self, uid: str, data: dict) -> dict:
        self._brand[uid] = data
        return data

    def get_user(self, uid: str) -> dict | None:
        return self._users.get(uid)

    def set_user(self, uid: str, data: dict) -> dict:
        doc = {**self._users.get(uid, {}), **data, "uid": uid}
        self._users[uid] = doc
        return doc

    # ── Credits ───────────────────────────────────────────────────────
    def adjust_credits(self, uid: str, delta: float, *, granted_delta: float = 0.0,
                       spent_delta: float = 0.0,
                       held_delta: float = 0.0) -> tuple[float, int]:
        with self._credit_lock:
            user = self._users.setdefault(uid, {"uid": uid})
            balance = round(float(user.get("credits_balance") or 0.0) + delta, 4)
            user["credits_balance"] = balance
            user["credits_granted_total"] = round(
                float(user.get("credits_granted_total") or 0.0) + granted_delta, 4)
            user["credits_spent_total"] = round(
                float(user.get("credits_spent_total") or 0.0) + spent_delta, 4)
            # Clamped: a double-settle must not drive the outstanding hold negative.
            user["credits_held"] = max(
                0.0, round(float(user.get("credits_held") or 0.0) + held_delta, 4))
            seq = int(user.get("ledger_seq") or 0) + 1
            user["ledger_seq"] = seq
            return balance, seq

    def claim_signup_grant(self, uid: str) -> bool:
        with self._credit_lock:
            user = self._users.setdefault(uid, {"uid": uid})
            if user.get("signup_grant_at"):
                return False
            user["signup_grant_at"] = utcnow()
            return True

    def add_ledger_entry(self, uid: str, entry: dict) -> dict:
        doc = {"id": _new_id(), **entry}
        self._ledger.append(doc)
        return doc

    def list_ledger(self, uid: str, limit: int = 50) -> list[dict]:
        rows = [e for e in self._ledger if e.get("uid") == uid]
        return sorted(rows, key=_ledger_order, reverse=True)[:limit]

    # ── Platform config ───────────────────────────────────────────────
    def get_platform_config(self) -> dict:
        return dict(self._platform)

    def set_platform_config(self, patch: dict) -> dict:
        self._platform.update(patch)
        return dict(self._platform)

    # ── Transparency log ──────────────────────────────────────────────
    def append_transparency_entry(self, body: dict) -> dict:
        from originshot_pipelines import transparency

        with self._log_lock:
            prev = self._log[-1]["entry_hash"] if self._log else transparency.GENESIS_HASH
            entry = transparency.make_entry(seq=len(self._log), prev_hash=prev, **body)
            self._log.append(entry)
            return entry

    def list_transparency_entries(self, *, start: int = 0,
                                  limit: int | None = None) -> list[dict]:
        rows = self._log[start:]
        return rows[:limit] if limit is not None else rows

    def transparency_size(self) -> int:
        return len(self._log)

    def find_transparency_entry(self, subject_sha256: str) -> dict | None:
        return next((e for e in self._log if e["subject_sha256"] == subject_sha256), None)

    def save_checkpoint(self, checkpoint: dict) -> dict:
        self._checkpoints.append(checkpoint)
        return checkpoint

    def latest_checkpoint(self) -> dict | None:
        return self._checkpoints[-1] if self._checkpoints else None

    # ── Dispute reports ───────────────────────────────────────────────
    def add_dispute_report(self, report: dict) -> dict:
        doc = {"id": _new_id(), "created_at": utcnow(), **report}
        self._reports[doc["id"]] = doc
        return doc

    def get_dispute_report(self, report_id: str) -> dict | None:
        return self._reports.get(report_id)

    def update_dispute_report(self, report_id: str, patch: dict) -> dict | None:
        report = self._reports.get(report_id)
        if report:
            report.update(patch)
        return report

    # ── Admin ─────────────────────────────────────────────────────────
    def list_users(self) -> list[dict]:
        return list(self._users.values())

    def list_all_jobs(self, limit: int = 200) -> list[dict]:
        return sorted(self._jobs.values(), key=lambda j: j["created_at"], reverse=True)[:limit]

    def list_all_assets(self) -> list[dict]:
        return list(self._assets.values())

    def list_all_skus(self) -> list[dict]:
        return list(self._skus.values())

    def list_all_ledger(self, limit: int = 100) -> list[dict]:
        return sorted(self._ledger, key=_ledger_order, reverse=True)[:limit]


# ── Firestore (production) ────────────────────────────────────────────
class FirestoreRepo:
    """sellers/{uid}/skus/{skuId}/assets/{assetId} and sellers/{uid}/jobs/{jobId}."""

    def __init__(self) -> None:
        from . import firebase

        self._db = firebase.get_db()
        # Small TTL cache of the pHash index, so a burst of public /verify calls scans
        # Firestore at most once per window instead of once per request. See
        # find_similar_by_phash for why a scan is the right shape at this scale.
        self._phash_cache: list[dict] | None = None
        self._phash_cache_at: float = 0.0

    def _seller(self, uid: str):
        return self._db.collection("sellers").document(uid)

    def create_sku(self, uid: str, data: dict) -> dict:
        ref = self._seller(uid).collection("skus").document()
        doc = {"id": ref.id, "owner_uid": uid, "original_sha256": None,
               "created_at": utcnow(), **data}
        ref.set(doc)
        return doc

    def get_sku(self, uid: str, sku_id: str) -> dict | None:
        snap = self._seller(uid).collection("skus").document(sku_id).get()
        return snap.to_dict() if snap.exists else None

    def list_skus(self, uid: str) -> list[dict]:
        col = self._seller(uid).collection("skus")
        return [d.to_dict() for d in col.stream()]

    def set_sku_original(self, uid: str, sku_id: str, sha256: str) -> None:
        self._seller(uid).collection("skus").document(sku_id).update({"original_sha256": sha256})

    def update_sku(self, uid: str, sku_id: str, patch: dict) -> dict | None:
        ref = self._seller(uid).collection("skus").document(sku_id)
        if not ref.get().exists:
            return None
        ref.update(patch)
        snap = ref.get()
        return snap.to_dict() if snap.exists else None

    def delete_sku(self, uid: str, sku_id: str) -> list[dict]:
        sku_ref = self._seller(uid).collection("skus").document(sku_id)
        if not sku_ref.get().exists:
            return []
        assets_col = sku_ref.collection("assets")
        removed: list[dict] = []
        refs = []
        for snap in assets_col.stream():
            removed.append(snap.to_dict())
            refs.append(snap.reference)
        # Delete the asset docs and the SKU doc first, so the survivor scan below cannot see
        # them (the just-deleted assets must not count as survivors of their own hash).
        for ref in refs:
            ref.delete()
        sku_ref.delete()

        # Reconcile the global sha/pHash indexes. These are one-entry-per-hash and
        # content-addressable, so the same bytes — most commonly the SAME uploaded photo on
        # several SKUs — are shared. If a removed asset OWNED a hash's index entry, the entry
        # must be **re-pointed** to a surviving asset that shares the hash, not deleted:
        # deleting it would orphan that survivor (find_asset_by_sha would return None for a
        # file that still exists, breaking verify-by-hash and Resolve's anchor lookup). Only
        # when nothing survives with the hash is the entry actually removed.
        surviving_by_sha: dict[str, dict] = {}
        for a in self.list_assets_for_user(uid):   # excludes the SKU just deleted above
            s = a.get("sha256")
            if s and s not in surviving_by_sha:
                surviving_by_sha[s] = a
        for a in removed:
            sha = a.get("sha256")
            if not sha:
                continue
            for coll in ("asset_index", "phash_index"):
                idx = self._db.collection(coll).document(sha)
                doc = idx.get()
                if not (doc.exists and doc.to_dict().get("asset_id") == a.get("id")):
                    continue                        # this asset didn't own the entry — leave it
                survivor = surviving_by_sha.get(sha)
                # phash_index is only meaningful for an asset that carries a pHash (generated
                # images); a shared hash is almost always an authentic original, which has
                # none, so that branch simply deletes.
                if survivor and (coll != "phash_index" or survivor.get("phash")):
                    payload = {"uid": survivor["owner_uid"], "sku_id": survivor["sku_id"],
                               "asset_id": survivor["id"]}
                    if coll == "phash_index":
                        payload |= {"phash": survivor["phash"], "sha256": sha}
                    idx.set(payload)                 # re-point, don't orphan
                else:
                    idx.delete()
        return removed

    def find_sku_by_id(self, sku_id: str) -> tuple[str, dict] | None:
        # Unfiltered collection-group stream — the same index-free shape list_all_skus uses.
        # SKU ids are globally unique (Firestore auto-ids), so the first match is the only one.
        for snap in self._db.collection_group("skus").stream():
            doc = snap.to_dict()
            if doc.get("id") == sku_id:
                return doc.get("owner_uid"), doc
        return None

    def add_asset(self, uid: str, asset: dict) -> dict:
        sku_id = asset["sku_id"]
        ref = self._seller(uid).collection("skus").document(sku_id).collection("assets").document()
        doc = {"id": ref.id, "owner_uid": uid, "created_at": utcnow(), **asset}
        ref.set(doc)
        # also index by sha for global verify lookups
        self._db.collection("asset_index").document(asset["sha256"]).set(
            {"uid": uid, "sku_id": sku_id, "asset_id": ref.id}
        )
        # Perceptual-hash index for Verify in the Wild. A separate flat collection (rather than
        # a field on the asset) so the public verifier can scan just the pHashes without
        # touching per-seller subcollections or reading any private asset data. Keyed by sha so
        # a regenerated-then-re-embedded asset overwrites cleanly.
        if asset.get("phash"):
            self._db.collection("phash_index").document(asset["sha256"]).set({
                "phash": asset["phash"],
                "sha256": asset["sha256"],
                "uid": uid,
                "sku_id": sku_id,
                "asset_id": ref.id,
            })
        return doc

    def list_assets(self, uid: str, sku_id: str) -> list[dict]:
        col = self._seller(uid).collection("skus").document(sku_id).collection("assets")
        return [d.to_dict() for d in col.stream()]

    def list_assets_for_user(self, uid: str) -> list[dict]:
        # Iterating the user's SKUs rather than a filtered collection-group query is
        # deliberate: a `collection_group("assets").where("owner_uid"==uid)` needs a
        # collection-group-scoped index that a fresh Firestore project doesn't have, and a
        # missing index fails at request time in production. SKU count is bounded (the
        # catalog cap is 100), so N subcollection reads is the safe shape.
        out: list[dict] = []
        for sku in self.list_skus(uid):
            out.extend(self.list_assets(uid, sku["id"]))
        epoch = datetime.min.replace(tzinfo=timezone.utc)
        return sorted(out, key=lambda a: a.get("created_at") or epoch, reverse=True)

    def find_asset_by_sha(self, sha256: str) -> dict | None:
        idx = self._db.collection("asset_index").document(sha256).get()
        if not idx.exists:
            return None
        ref = idx.to_dict()
        snap = (self._seller(ref["uid"]).collection("skus").document(ref["sku_id"])
                .collection("assets").document(ref["asset_id"]).get())
        return snap.to_dict() if snap.exists else None

    # Refresh the pHash index at most this often (seconds). New assets appear a window late in
    # the verifier, which is fine — Verify in the Wild matches images the marketplace has
    # already published, so nothing being checked is ever seconds old.
    _PHASH_CACHE_TTL = 120

    def _phash_index(self) -> list[dict]:
        import time

        now = time.time()
        if self._phash_cache is not None and now - self._phash_cache_at < self._PHASH_CACHE_TTL:
            return self._phash_cache
        rows = [d.to_dict() for d in self._db.collection("phash_index").stream()]
        self._phash_cache, self._phash_cache_at = rows, now
        return rows

    def find_similar_by_phash(self, phash: str, max_distance: int) -> dict | None:
        """Nearest generated asset within `max_distance` bits, or None.

        This is a linear scan over the pHash index, deliberately. Sub-linear perceptual
        nearest-neighbour (a BK-tree, or multi-index hashing over hash bands) is real and
        well-understood, but it earns its complexity at millions of hashes; at this app's
        scale a scan behind a TTL cache is both simpler and honest about its cost — the same
        stance the transparency log takes on its O(n-k) inclusion proofs. The full-asset read
        happens only for the single winning candidate, never for the whole library.
        """
        from originshot_pipelines.perceptual import hamming

        best: dict | None = None
        best_dist = max_distance + 1
        for row in self._phash_index():
            d = hamming(phash, row.get("phash"))
            if d is not None and d < best_dist:
                best, best_dist = row, d
        if best is None:
            return None
        asset = self.find_asset_by_sha(best["sha256"])
        if not asset:
            return None
        return {**asset, "phash_distance": best_dist}

    def create_job(self, uid: str, job: dict) -> dict:
        ref = self._seller(uid).collection("jobs").document()
        doc = {"id": ref.id, "owner_uid": uid, "status": JobStatus.queued.value,
               "asset_ids": [], "created_at": utcnow(), "finished_at": None, **job}
        ref.set(doc)
        return doc

    def get_job(self, uid: str, job_id: str) -> dict | None:
        snap = self._seller(uid).collection("jobs").document(job_id).get()
        return snap.to_dict() if snap.exists else None

    def list_jobs(self, uid: str, limit: int = 200) -> list[dict]:
        rows = [d.to_dict() for d in self._seller(uid).collection("jobs").stream()]
        return sorted(rows, key=lambda j: j["created_at"], reverse=True)[:limit]

    def update_job(self, uid: str, job_id: str, patch: dict) -> dict | None:
        ref = self._seller(uid).collection("jobs").document(job_id)
        ref.update(patch)
        snap = ref.get()
        return snap.to_dict() if snap.exists else None

    def count_generations_today(self, uid: str) -> int:
        # Lightweight; for scale, store a per-day counter document instead.
        jobs = self._seller(uid).collection("jobs").stream()
        today = _today_key()
        return sum(1 for j in jobs if _today_key(j.to_dict().get("created_at")) == today)

    # ── Batches ───────────────────────────────────────────────────────
    def create_batch(self, uid: str, batch: dict) -> dict:
        ref = self._seller(uid).collection("batches").document()
        doc = {"id": ref.id, "owner_uid": uid, "created_at": utcnow(), **batch}
        ref.set(doc)
        return doc

    def get_batch(self, uid: str, batch_id: str) -> dict | None:
        snap = self._seller(uid).collection("batches").document(batch_id).get()
        return snap.to_dict() if snap.exists else None

    def list_batches(self, uid: str, limit: int = 50) -> list[dict]:
        rows = [d.to_dict() for d in self._seller(uid).collection("batches").stream()]
        return sorted(rows, key=lambda b: b["created_at"], reverse=True)[:limit]

    def update_batch(self, uid: str, batch_id: str, patch: dict) -> dict | None:
        ref = self._seller(uid).collection("batches").document(batch_id)
        if not ref.get().exists:
            return None
        ref.update(patch)
        snap = ref.get()
        return snap.to_dict() if snap.exists else None

    def get_brand_kit(self, uid: str) -> dict | None:
        snap = self._seller(uid).get()
        return (snap.to_dict() or {}).get("brand_kit") if snap.exists else None

    def set_brand_kit(self, uid: str, data: dict) -> dict:
        self._seller(uid).set({"brand_kit": data}, merge=True)
        return data

    def get_user(self, uid: str) -> dict | None:
        snap = self._db.collection("users").document(uid).get()
        return snap.to_dict() if snap.exists else None

    def set_user(self, uid: str, data: dict) -> dict:
        ref = self._db.collection("users").document(uid)
        ref.set({**data, "uid": uid}, merge=True)   # upsert; never clobbers unset fields
        return ref.get().to_dict()

    # ── Credits ───────────────────────────────────────────────────────
    def adjust_credits(self, uid: str, delta: float, *, granted_delta: float = 0.0,
                       spent_delta: float = 0.0,
                       held_delta: float = 0.0) -> tuple[float, int]:
        """Atomic read-modify-write on the balance.

        A plain `get()` then `update()` would drop a debit whenever two jobs settle at once,
        which is exactly the bug that makes a credit system untrustworthy. Firestore's
        transaction retries the read on contention.

        The ledger sequence is incremented in the same transaction, so it stays gap-free and
        strictly ordered even under concurrent writers.
        """
        from google.cloud import firestore  # type: ignore[attr-defined]

        ref = self._db.collection("users").document(uid)

        @firestore.transactional
        def _apply(txn) -> tuple[float, int]:
            snap = ref.get(transaction=txn)
            cur = snap.to_dict() if snap.exists else {}
            balance = round(float(cur.get("credits_balance") or 0.0) + delta, 4)
            seq = int(cur.get("ledger_seq") or 0) + 1
            txn.set(ref, {
                "uid": uid,
                "credits_balance": balance,
                "credits_granted_total": round(
                    float(cur.get("credits_granted_total") or 0.0) + granted_delta, 4),
                "credits_spent_total": round(
                    float(cur.get("credits_spent_total") or 0.0) + spent_delta, 4),
                "credits_held": max(
                    0.0, round(float(cur.get("credits_held") or 0.0) + held_delta, 4)),
                "ledger_seq": seq,
            }, merge=True)
            return balance, seq

        return _apply(self._db.transaction())

    def claim_signup_grant(self, uid: str) -> bool:
        """Transactional check-and-set on the marker.

        The read and the write share one transaction, so of N concurrent first requests
        exactly one sees the marker unset — a plain get() → set() here is how the same
        account ends up with three welcome credits.
        """
        from google.cloud import firestore  # type: ignore[attr-defined]

        ref = self._db.collection("users").document(uid)

        @firestore.transactional
        def _claim(txn) -> bool:
            snap = ref.get(transaction=txn)
            cur = snap.to_dict() if snap.exists else {}
            if cur.get("signup_grant_at"):
                return False
            txn.set(ref, {"uid": uid, "signup_grant_at": utcnow()}, merge=True)
            return True

        return _claim(self._db.transaction())

    def add_ledger_entry(self, uid: str, entry: dict) -> dict:
        ref = self._seller(uid).collection("ledger").document()
        doc = {"id": ref.id, **entry}
        ref.set(doc)
        return doc

    def list_ledger(self, uid: str, limit: int = 50) -> list[dict]:
        col = self._seller(uid).collection("ledger")
        rows = [d.to_dict() for d in col.stream()]
        return sorted(rows, key=_ledger_order, reverse=True)[:limit]

    # ── Platform config ───────────────────────────────────────────────
    def get_platform_config(self) -> dict:
        snap = self._db.collection("platform").document("config").get()
        return snap.to_dict() if snap.exists else {}

    def set_platform_config(self, patch: dict) -> dict:
        ref = self._db.collection("platform").document("config")
        ref.set(patch, merge=True)
        return ref.get().to_dict() or {}

    # ── Transparency log ──────────────────────────────────────────────
    def append_transparency_entry(self, body: dict) -> dict:
        """Atomically extend the chain.

        The head read and the entry write happen in one transaction. A plain read-then-write
        would let two concurrent generations both see head N and both write entry N+1 with
        the same `prev_hash` — forking the chain into two competing histories, which is
        precisely the failure an append-only log exists to make impossible. Firestore retries
        the transaction on contention.

        Entries are keyed by zero-padded sequence so `stream()` returns them in log order
        without a sort: replay depends on order, and ordering by a timestamp would be wrong
        the first time two entries shared a millisecond.
        """
        from google.cloud import firestore  # type: ignore[attr-defined]

        from originshot_pipelines import transparency

        head_ref = self._db.collection("transparency").document("head")
        entries = self._db.collection("transparency").document("head").collection("entries")

        @firestore.transactional
        def _append(txn) -> dict:
            snap = head_ref.get(transaction=txn)
            cur = snap.to_dict() if snap.exists else {}
            seq = int(cur.get("size") or 0)
            prev = cur.get("head") or transparency.GENESIS_HASH
            entry = transparency.make_entry(seq=seq, prev_hash=prev, **body)
            txn.set(entries.document(f"{seq:012d}"), entry)
            txn.set(head_ref, {"size": seq + 1, "head": entry["entry_hash"],
                               "updated_at": utcnow()}, merge=True)
            return entry

        return _append(self._db.transaction())

    def _entries_col(self):
        return self._db.collection("transparency").document("head").collection("entries")

    def list_transparency_entries(self, *, start: int = 0,
                                  limit: int | None = None) -> list[dict]:
        query = self._entries_col().order_by("seq").offset(start)
        if limit is not None:
            query = query.limit(limit)
        return [d.to_dict() for d in query.stream()]

    def transparency_size(self) -> int:
        snap = self._db.collection("transparency").document("head").get()
        return int((snap.to_dict() or {}).get("size") or 0) if snap.exists else 0

    def find_transparency_entry(self, subject_sha256: str) -> dict | None:
        rows = list(self._entries_col()
                    .where("subject_sha256", "==", subject_sha256).limit(1).stream())
        return rows[0].to_dict() if rows else None

    def save_checkpoint(self, checkpoint: dict) -> dict:
        (self._db.collection("transparency").document("head")
         .collection("checkpoints").document(f"{int(checkpoint['size']):012d}")
         .set(checkpoint))
        return checkpoint

    def latest_checkpoint(self) -> dict | None:
        rows = list(self._db.collection("transparency").document("head")
                    .collection("checkpoints")
                    .order_by("size", direction="DESCENDING").limit(1).stream())
        return rows[0].to_dict() if rows else None

    # ── Dispute reports ───────────────────────────────────────────────
    def add_dispute_report(self, report: dict) -> dict:
        ref = self._db.collection("dispute_reports").document()
        doc = {"id": ref.id, "created_at": utcnow(), **report}
        ref.set(doc)
        return doc

    def get_dispute_report(self, report_id: str) -> dict | None:
        snap = self._db.collection("dispute_reports").document(report_id).get()
        return snap.to_dict() if snap.exists else None

    def update_dispute_report(self, report_id: str, patch: dict) -> dict | None:
        ref = self._db.collection("dispute_reports").document(report_id)
        if not ref.get().exists:
            return None
        ref.update(patch)
        snap = ref.get()
        return snap.to_dict() if snap.exists else None

    # ── Admin ─────────────────────────────────────────────────────────
    # Cross-user reads via collection-group queries. These scan; at real scale they'd be
    # replaced by maintained rollup documents, but they are correct and honest here.
    def list_users(self) -> list[dict]:
        return [d.to_dict() for d in self._db.collection("users").stream()]

    def list_all_jobs(self, limit: int = 200) -> list[dict]:
        rows = [d.to_dict() for d in self._db.collection_group("jobs").stream()]
        return sorted(rows, key=lambda j: j["created_at"], reverse=True)[:limit]

    def list_all_assets(self) -> list[dict]:
        return [d.to_dict() for d in self._db.collection_group("assets").stream()]

    def list_all_skus(self) -> list[dict]:
        return [d.to_dict() for d in self._db.collection_group("skus").stream()]

    def list_all_ledger(self, limit: int = 100) -> list[dict]:
        rows = [d.to_dict() for d in self._db.collection_group("ledger").stream()]
        return sorted(rows, key=_ledger_order, reverse=True)[:limit]


_repo: Any = None


def get_repo() -> Repo:
    global _repo
    if _repo is None:
        _repo = FirestoreRepo() if get_settings().firebase_configured else InMemoryRepo()
    return _repo
