"""Admin authorization.

Two ways to be an admin, and the distinction matters:

  * **role** — `"admin"` in the user document's `roles` array. This is the source of truth
    and the only way to grant admin to someone else (via the admin API).
  * **bootstrap allowlist** — an email in `ADMIN_EMAILS`. This exists solely to mint the
    *first* admin: every role-granting endpoint requires an admin, so without a seed the
    system has no way to ever produce one. On first authenticated request the role is
    written back to the user document, after which the role check alone would suffice.

The allowlist is checked against the **token-verified** email, never a client-supplied one,
and only when Firebase reports it verified — an unverified email claim is attacker-chosen at
signup on some providers, and admin is not a decision to hand to it.

`require_admin` returns the CurrentUser so handlers can attribute actions (`actor_uid` on
ledger rows), which is what makes credit grants auditable rather than anonymous.
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status

from .auth import CurrentUser, get_current_user
from .config import get_settings
from .models import Role, utcnow
from .repo import get_repo

log = logging.getLogger("originshot.admin")


def _roles_of(user_doc: dict | None) -> set[str]:
    return {str(r) for r in (user_doc or {}).get("roles", [])}


def is_admin(user: CurrentUser) -> bool:
    """True when the user holds the admin role, seeding it from the allowlist if needed."""
    repo = get_repo()
    doc = repo.get_user(user.uid)
    if Role.admin.value in _roles_of(doc):
        return True

    email = (user.email or "").strip().lower()
    if not email or email not in get_settings().admin_email_set:
        return False
    # Bootstrap path. Require a verified email so the allowlist can't be claimed by an
    # unverified signup at a matching address.
    if not user.email_verified:
        log.warning("admin bootstrap refused for %s: email not verified", email)
        return False

    roles = sorted(_roles_of(doc) | {Role.admin.value, Role.customer.value})
    repo.set_user(user.uid, {"roles": roles, "updated_at": utcnow()})
    log.info("admin bootstrapped from ADMIN_EMAILS: %s", email)
    return True


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """FastAPI dependency guarding every /api/admin route."""
    if not is_admin(user):
        # 404-style opacity isn't worth it here: the caller is already authenticated, and a
        # clear 403 is what an operator needs to debug their own access.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
