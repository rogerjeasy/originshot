"""User profile endpoints — persist the signed-in user into the `users` collection.

The client creates the account with Firebase Auth (password never touches this backend),
then calls POST /users with a username. We key the profile by the token-verified uid and
default new users to roles=["customer"]. Existing users are never downgraded.
"""
from fastapi import APIRouter, Depends

from ..auth import CurrentUser, get_current_user
from ..models import DEFAULT_ROLES, UserOut, UserRegister, utcnow
from ..repo import get_repo

router = APIRouter(tags=["users"])


def _ensure_user(user: CurrentUser, *, username: str | None = None) -> dict:
    """Create the user's record on first sight; keep roles/username intact on later calls.

    - New user  → {email, username, roles: ["customer"], created_at, updated_at}.
    - Existing  → refresh email + updated_at, and fill username only if it wasn't set.
      Roles are never touched here (grant/revoke is a separate, privileged concern).
    """
    repo = get_repo()
    existing = repo.get_user(user.uid)
    if existing is None:
        derived = username or (user.email.split("@")[0] if user.email else None)
        return repo.set_user(user.uid, {
            "email": user.email,
            "username": derived,
            "roles": [r.value for r in DEFAULT_ROLES],
            "created_at": utcnow(),
            "updated_at": utcnow(),
        })
    patch: dict = {"updated_at": utcnow()}
    if user.email and existing.get("email") != user.email:
        patch["email"] = user.email
    if username and not existing.get("username"):
        patch["username"] = username
    return repo.set_user(user.uid, patch)


@router.post("/users", response_model=UserOut)
def register_user(body: UserRegister, user: CurrentUser = Depends(get_current_user)):
    """Idempotent: called right after sign-up (and safe to re-call on every sign-in)."""
    return _ensure_user(user, username=body.username)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user)):
    """Current user's profile, created with defaults on first read if it doesn't exist."""
    return _ensure_user(user)
