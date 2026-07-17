"""Test configuration: force a hermetic, zero-cost dev environment.

The suite must NEVER touch real Firebase, Backblaze B2, or any generation provider — not
even when a developer's `backend/.env` (or their shell) has real credentials set. So before
anything imports the app config, we pin the environment to an in-memory, mock-generation,
auth-bypassed mode and blank out every external credential. Concretely this forces:

  * get_repo()        → InMemoryRepo  (no `firebase_admin` import, no Firestore round-trips)
  * get_storage()     → LocalStorage  (no B2 network writes)
  * generation_mode() → "mock"        (no real GMI / OpenAI / etc. calls → $0, no
                                        denial-of-wallet risk from a test run)

This keeps `poetry run pytest` green *and* free regardless of what's in `.env` or the shell.
"""
import os

import pytest

# Force dev + auth bypass so protected routes resolve to a fake, verified user.
os.environ["APP_ENV"] = "dev"
os.environ["AUTH_DEV_BYPASS"] = "true"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

# Blank every external credential. Direct assignment (NOT setdefault) so a real value in the
# shell or in `.env` can't leak into the suite. An empty env var overrides the `.env` file in
# pydantic-settings, so `firebase_configured` / `b2_configured` / the provider keys all read
# falsy → in-memory repo, local storage, and mock generation.
for _k in (
    "FIREBASE_PROJECT_ID",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "B2_KEY_ID",
    "B2_APP_KEY",
    "B2_BUCKET",
    "GMI_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "LUMA_API_KEY",
    "ELEVENLABS_API_KEY",
):
    os.environ[_k] = ""


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    import app.repo as repo_mod
    import app.storage as storage_mod
    from app.config import get_settings

    get_settings.cache_clear()
    repo_mod._repo = None        # fresh in-memory repo per test
    storage_mod._storage = None

    from app.main import app as fastapi_app

    return TestClient(fastapi_app)


@pytest.fixture
def png_bytes():
    """Factory fixture returning small in-memory PNG bytes."""
    def _make(size=(48, 48), color=(200, 40, 40)) -> bytes:
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", size, color).save(buf, format="PNG")
        return buf.getvalue()

    return _make
