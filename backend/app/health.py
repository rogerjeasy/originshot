"""Health reporting that tells the truth about dependencies.

The naive version of this endpoint reported `firebase: true` whenever FIREBASE_PROJECT_ID
was merely *set* — so a service whose Firebase credentials file was missing entirely still
looked green while every authenticated route 500'd. These checks exercise the dependency
instead of inspecting an env var.

Two depths:

  * **shallow** (default) — no network. Actually initializes the Firebase Admin SDK, which
    is what silently fails when the Render Secret File is missing, and constructs the B2
    client. Cheap enough for Render's periodic health check.
  * **deep** (`/healthz?deep=true`) — additionally round-trips to B2 (`head_bucket`). Not
    used by the platform health check; for humans and monitoring.

Failure *reasons* are reported as exception class names only (`FileNotFoundError`,
`ValueError`). That is the diagnostic signal — missing file vs. malformed key — without
leaking paths or credentials on a public endpoint. Full detail goes to the server log.
"""
from __future__ import annotations

import logging

from .config import get_settings

log = logging.getLogger("originshot.health")


def _fail(exc: Exception) -> dict:
    """Report the exception *type* only — enough to diagnose, safe to expose."""
    return {"ok": False, "error": type(exc).__name__}


def check_firebase() -> dict:
    """Initialize Firebase Admin for real. This is the check that was missing.

    `FileNotFoundError` ⇒ the credentials file isn't mounted (on Render, the Secret File
    was never uploaded — blueprints don't carry secret file contents).
    """
    settings = get_settings()
    if not settings.firebase_configured:
        return {"ok": False, "error": "not_configured"}
    try:
        from . import firebase

        firebase.get_db()  # cached after the first successful call
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        log.warning("health: firebase unavailable — %s: %s", type(exc).__name__, exc)
        return _fail(exc)


def check_b2(deep: bool = False) -> dict:
    """Confirm B2 is configured, and when `deep`, that the bucket is actually reachable."""
    settings = get_settings()
    if not settings.b2_configured:
        return {"ok": False, "error": "not_configured"}
    if not deep:
        return {"ok": True, "checked": "config"}
    try:
        from .storage import get_storage

        storage = get_storage()
        storage.client.head_bucket(Bucket=settings.b2_bucket)
        return {"ok": True, "checked": "bucket"}
    except Exception as exc:  # noqa: BLE001
        log.warning("health: B2 unreachable — %s: %s", type(exc).__name__, exc)
        return _fail(exc)


def check_object_lock() -> dict:
    """Whether the transparency ledger's immutability claim is actually backed.

    Reports one of: disabled (not configured), active (configured AND the key can write
    retentions), or misconfigured (retention days set but the key can't apply a lock — so
    checkpoints publish unlocked and nothing should claim otherwise). This exists so the app
    never advertises immutability it isn't delivering; the honesty is the point.
    """
    settings = get_settings()
    if not settings.b2_configured:
        return {"ok": True, "state": "disabled", "reason": "B2 not configured"}
    if not (settings.b2_object_lock_days and settings.b2_object_lock_days > 0):
        return {"ok": True, "state": "disabled"}
    try:
        from .storage import get_storage

        status = get_storage().object_lock_status()
        if status.get("capable"):
            return {"ok": True, "state": "active", "mode": settings.b2_object_lock_mode,
                    "retain_days": settings.b2_object_lock_days}
        return {"ok": False, "state": "misconfigured",
                "reason": status.get("reason", "key cannot write retentions")}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "state": "unknown", "error": type(exc).__name__}


def check_generation() -> dict:
    """Report generation capability without spending money.

    IMPORTANT: `configured` is not `funded`. Provider credit balance cannot be checked
    without submitting a billable request, so a configured provider can still fail at
    submit time with a 402. That caveat is stated explicitly rather than implied, because
    a green health check over an unfunded provider is exactly the lie this module exists
    to stop telling.

    `unconfigured` reports `ok: False`. It previously returned ok either way, which meant a
    deployment that could not generate at all still showed green — the same class of lie.
    """
    from .generation import generation_mode, missing_generation_requirements

    mode = generation_mode()
    status = {
        "ok": mode != "unconfigured",
        "mode": mode,
        "verified": "configuration only — provider credit balance not checked",
    }
    if mode == "unconfigured":
        status["error"] = "not_configured"
        status["missing"] = missing_generation_requirements()
    elif mode == "mock":
        # Should never appear outside the test suite; if it does, say so loudly.
        status["warning"] = "MOCK generation is enabled — assets are fabricated, not real"
    return status


def collect_health(deep: bool = False) -> dict:
    settings = get_settings()
    firebase_status = check_firebase()
    b2_status = check_b2(deep)
    generation_status = check_generation()

    checks = {
        "firebase": firebase_status,
        "b2": b2_status,
        "generation": generation_status,
    }
    # Signing is a cheap local check (does the private seed load and match the repo key), so
    # it can run on every probe.
    from . import signing

    checks["signing"] = signing.verify_configuration()
    # Object Lock verification makes a native B2 call, so it runs only on the deep check
    # (humans/monitoring), never on the platform's frequent shallow probe.
    if deep:
        checks["object_lock"] = check_object_lock()

    # The process is alive, so this endpoint stays 200 (a non-200 makes Render restart-loop
    # the service). Degradation is reported in the body instead.
    degraded = [name for name, status in checks.items() if not status["ok"]]

    return {
        "status": "degraded" if degraded else "ok",
        "degraded": degraded,
        "env": settings.app_env,
        "checks": checks,
        "job_queue": settings.job_queue,
        "auth_dev_bypass": settings.auth_dev_bypass and settings.is_dev,
        "depth": "deep" if deep else "shallow",
    }
