"""Pytest fixtures."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Use isolated in-memory DB for tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MOCK_CHUTES_WHEN_NO_KEY", "true")
os.environ.setdefault("CHUTES_API_KEY", "")

from app.core.config import get_settings
from app.core.db import dispose_db, init_db
from app.main import app


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client():
    await dispose_db()
    get_settings.cache_clear()
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await dispose_db()
