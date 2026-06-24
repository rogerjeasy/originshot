"""Test configuration: force dev mode + auth bypass so the suite runs with no externals."""
import os

import pytest

os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("AUTH_DEV_BYPASS", "true")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")


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
