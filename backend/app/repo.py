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

    def add_asset(self, uid: str, asset: dict) -> dict: ...
    def list_assets(self, uid: str, sku_id: str) -> list[dict]: ...
    def find_asset_by_sha(self, sha256: str) -> dict | None: ...  # public verify (global)

    def create_job(self, uid: str, job: dict) -> dict: ...
    def get_job(self, uid: str, job_id: str) -> dict | None: ...
    def update_job(self, uid: str, job_id: str, patch: dict) -> dict | None: ...

    def count_generations_today(self, uid: str) -> int: ...

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
    def add_ledger_entry(self, uid: str, entry: dict) -> dict: ...
    def list_ledger(self, uid: str, limit: int = 50) -> list[dict]: ...

    # Platform-wide operator settings (single document, admin-writable).
    def get_platform_config(self) -> dict: ...
    def set_platform_config(self, patch: dict) -> dict: ...

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

    def add_asset(self, uid: str, asset: dict) -> dict:
        doc = {"id": _new_id(), "owner_uid": uid, "created_at": utcnow(), **asset}
        self._assets[doc["id"]] = doc
        return doc

    def list_assets(self, uid: str, sku_id: str) -> list[dict]:
        return sorted(
            [a for a in self._assets.values() if a["owner_uid"] == uid and a["sku_id"] == sku_id],
            key=lambda a: a["created_at"],
        )

    def find_asset_by_sha(self, sha256: str) -> dict | None:
        for a in self._assets.values():
            if a["sha256"] == sha256:
                return a
        return None

    def create_job(self, uid: str, job: dict) -> dict:
        doc = {"id": _new_id(), "owner_uid": uid, "status": JobStatus.queued.value,
               "asset_ids": [], "created_at": utcnow(), "finished_at": None, **job}
        self._jobs[doc["id"]] = doc
        return doc

    def get_job(self, uid: str, job_id: str) -> dict | None:
        job = self._jobs.get(job_id)
        return job if job and job["owner_uid"] == uid else None

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

    def add_asset(self, uid: str, asset: dict) -> dict:
        sku_id = asset["sku_id"]
        ref = self._seller(uid).collection("skus").document(sku_id).collection("assets").document()
        doc = {"id": ref.id, "owner_uid": uid, "created_at": utcnow(), **asset}
        ref.set(doc)
        # also index by sha for global verify lookups
        self._db.collection("asset_index").document(asset["sha256"]).set(
            {"uid": uid, "sku_id": sku_id, "asset_id": ref.id}
        )
        return doc

    def list_assets(self, uid: str, sku_id: str) -> list[dict]:
        col = self._seller(uid).collection("skus").document(sku_id).collection("assets")
        return [d.to_dict() for d in col.stream()]

    def find_asset_by_sha(self, sha256: str) -> dict | None:
        idx = self._db.collection("asset_index").document(sha256).get()
        if not idx.exists:
            return None
        ref = idx.to_dict()
        snap = (self._seller(ref["uid"]).collection("skus").document(ref["sku_id"])
                .collection("assets").document(ref["asset_id"]).get())
        return snap.to_dict() if snap.exists else None

    def create_job(self, uid: str, job: dict) -> dict:
        ref = self._seller(uid).collection("jobs").document()
        doc = {"id": ref.id, "owner_uid": uid, "status": JobStatus.queued.value,
               "asset_ids": [], "created_at": utcnow(), "finished_at": None, **job}
        ref.set(doc)
        return doc

    def get_job(self, uid: str, job_id: str) -> dict | None:
        snap = self._seller(uid).collection("jobs").document(job_id).get()
        return snap.to_dict() if snap.exists else None

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
