"""Data access layer.

Two implementations behind one interface:
  * InMemoryRepo  — dev/tests; zero external dependencies.
  * FirestoreRepo — production; owner-scoped documents under sellers/{uid}/...

`get_repo()` picks Firestore when Firebase is configured, otherwise in-memory.
Every method takes the authenticated `uid` and scopes data to it (no cross-user access).
See ../docs/SECURITY.md §4.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from .config import get_settings
from .models import JobStatus, utcnow


def _new_id() -> str:
    return uuid.uuid4().hex


def _today_key(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).strftime("%Y-%m-%d")


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


# ── In-memory (dev/tests) ─────────────────────────────────────────────
class InMemoryRepo:
    def __init__(self) -> None:
        self._skus: dict[str, dict] = {}
        self._assets: dict[str, dict] = {}
        self._jobs: dict[str, dict] = {}
        self._brand: dict[str, dict] = {}

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


_repo: Any = None


def get_repo() -> Repo:
    global _repo
    if _repo is None:
        _repo = FirestoreRepo() if get_settings().firebase_configured else InMemoryRepo()
    return _repo
