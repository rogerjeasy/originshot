"""Authentication: verify Firebase ID tokens server-side on every protected request.

The authenticated `uid` is derived ONLY from the verified token — never from client input.
See ../docs/SECURITY.md §3.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import firebase
from .config import get_settings

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
        return CurrentUser(uid="dev-user", email="dev@listsnap.local", email_verified=True, is_dev=True)

    if cred is None or not cred.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    if not firebase.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth is not configured")

    from firebase_admin import auth as fb_auth

    firebase.get_db()  # ensure the Admin app is initialized
    try:
        decoded = fb_auth.verify_id_token(cred.credentials, check_revoked=True)
    except Exception:  # noqa: BLE001 — never leak verification details to the client
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    return CurrentUser(
        uid=decoded["uid"],
        email=decoded.get("email"),
        email_verified=bool(decoded.get("email_verified", False)),
    )


def require_verified_email(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Dependency for mutating actions: require a verified email."""
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email not verified")
    return user
