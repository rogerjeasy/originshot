"""Authentication: verify Firebase ID tokens server-side on every protected request.

The authenticated `uid` is derived ONLY from the verified token — never from client input.
See ../docs/SECURITY.md §3.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import firebase
from .config import get_settings

log = logging.getLogger("originshot.auth")

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    uid: str
    email: str | None = None
    email_verified: bool = False
    is_dev: bool = False


async def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    settings = get_settings()

    # Dev-only shortcut: a fake, verified user so the app runs without Firebase.
    if settings.auth_dev_bypass and settings.is_dev:
        return CurrentUser(uid="dev-user", email="dev@originshot.local", email_verified=True, is_dev=True)

    if cred is None or not cred.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    if not firebase.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth is not configured")

    # Importing and initializing the Admin SDK are *configuration* concerns, not credential
    # ones: a missing `[firebase]` extra or an unmountable service-account file is a 503
    # (our fault, retryable), never a 500. Letting either raise previously surfaced in
    # browsers as an opaque CORS error, because Starlette's 500 handler runs outside
    # CORSMiddleware and so emits no Access-Control-Allow-Origin header.
    try:
        from firebase_admin import auth as fb_auth

        firebase.get_db()  # ensure the Admin app is initialized
    except Exception as exc:  # noqa: BLE001
        log.error("Firebase Admin unavailable — check install/credentials: %s: %s",
                  type(exc).__name__, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Auth backend unavailable"
        ) from exc

    try:
        decoded = fb_auth.verify_id_token(cred.credentials, check_revoked=True)
    except Exception:  # noqa: BLE001 — never leak verification details to the client
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    return CurrentUser(
        uid=decoded["uid"],
        email=decoded.get("email"),
        email_verified=bool(decoded.get("email_verified", False)),
    )
