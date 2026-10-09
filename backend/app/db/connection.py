"""SQLite database connection manager with WAL mode and sqlite-vec extension support."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.config import get_settings

logger = logging.getLogger("aria.db")


class Database:
    """Manages asynchronous SQLite connections, pragmas, and extension loading."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._custom_db_path = db_path

    @property
    def db_path(self) -> Path:
        if self._custom_db_path is not None:
            return self._custom_db_path
        return get_settings().db_path

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Provide an aiosqlite connection with WAL mode and sqlite-vec enabled."""
        conn = await aiosqlite.connect(str(self.db_path))
        conn.row_factory = aiosqlite.Row
        try:
            # Pragmas for concurrency and durability
            await conn.execute("PRAGMA journal_mode = WAL;")
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute("PRAGMA busy_timeout = 5000;")
            await conn.execute("PRAGMA synchronous = NORMAL;")

            # Load sqlite-vec extension for dense vector similarity
            try:
                import sqlite_vec

                await conn.enable_load_extension(True)
                await conn.load_extension(sqlite_vec.loadable_path())
            except Exception as e:
                logger.warning(f"Could not load sqlite-vec extension: {e}")

            yield conn
        finally:
            await conn.close()


def get_database(db_path: Path | None = None) -> Database:
    """Get Database instance bound to custom path or current settings db_path."""
    if db_path is not None:
        return Database(db_path)
    return Database(get_settings().db_path)
