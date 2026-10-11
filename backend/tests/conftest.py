"""Shared pytest fixtures for backend testing."""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.db.connection import Database, get_database
from app.db.schema import init_db
from app.main import create_app


@pytest.fixture(autouse=True)
async def setup_test_environment(tmp_path: Path, monkeypatch):
    """Ensure every test runs against an isolated, initialized temporary database."""
    temp_data = tmp_path / "aria_data"
    temp_data.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("ARIA_DATA_DIR", str(temp_data))
    monkeypatch.setenv("ARIA_ENV", "testing")
    monkeypatch.setenv("ARIA_SECRET_KEY", "test-secret-key-for-unit-testing")
    get_settings.cache_clear()

    # Initialize SQLite schema in this temporary directory
    db = get_database()
    async with db.get_connection() as conn:
        await init_db(conn)

    # Ensure emergency kill switch is always reset for isolated test execution
    from app.agent.kill_switch import kill_switch

    kill_switch.reset()

    yield

    kill_switch.reset()
    get_settings.cache_clear()


@pytest.fixture
def initialized_db() -> Database:
    """Fixture providing initialized Database instance."""
    return get_database()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async test client bound to the FastAPI application."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
