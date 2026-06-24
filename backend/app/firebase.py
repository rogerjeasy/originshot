"""Firebase Admin SDK initialization (Firestore client).

`firebase-admin` is an optional dependency (install with `pip install -e ".[firebase]"`).
In dev with AUTH_DEV_BYPASS + no FIREBASE_PROJECT_ID, the app never touches Firebase and
falls back to the in-memory repository (see repo.py).
"""
from __future__ import annotations

import threading

from .config import get_settings

_lock = threading.Lock()
_db = None


def _initialize() -> None:
    global _db
    import firebase_admin
    from firebase_admin import credentials, firestore

    settings = get_settings()
    if not firebase_admin._apps:
        if settings.google_application_credentials:
            cred = credentials.Certificate(settings.google_application_credentials)
            firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})
        else:
            # Uses Application Default Credentials (e.g. GOOGLE_APPLICATION_CREDENTIALS env)
            firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
    _db = firestore.client()


def get_db():
    """Return a lazily-initialized Firestore client (thread-safe)."""
    global _db
    if _db is None:
        with _lock:
            if _db is None:
                _initialize()
    return _db


def is_configured() -> bool:
    return get_settings().firebase_configured
