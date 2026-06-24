"""FastAPI application entrypoint.

Run (dev):  uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from .api import api_router
from .config import get_settings
from .security import SecurityHeadersMiddleware, limiter

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())
log = logging.getLogger("listsnap")

app = FastAPI(
    title="ListSnap API",
    version="0.1.0",
    description="Turn one photo into a marketplace-ready, provenance-verified product pack.",
)

# Rate limiting (slowapi)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda r, e: _rate_limited())

# Security headers on every response
app.add_middleware(SecurityHeadersMiddleware)

# CORS — strict allowlist (no wildcard origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix="/api")


def _rate_limited():
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


@app.get("/healthz", tags=["meta"])
def healthz():
    from .generation import generation_mode

    return {
        "status": "ok",
        "env": settings.app_env,
        "firebase": settings.firebase_configured,
        "b2": settings.b2_configured,
        "generation": generation_mode(),  # "genblaze" | "mock"
        "job_queue": settings.job_queue,
        "auth_dev_bypass": settings.auth_dev_bypass and settings.is_dev,
    }


# Dev only: serve locally-stored media (when B2 isn't configured).
if settings.is_dev and not settings.b2_configured:
    media_dir = Path(__file__).resolve().parent.parent / ".devdata" / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")
    log.warning("DEV MODE: serving local media from /media (configure B2 for production).")
