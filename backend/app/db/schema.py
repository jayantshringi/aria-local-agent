"""Database schema definitions and migration initializers."""

import aiosqlite

SCHEMA_SQL = """
-- 1. Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    summary TEXT,
    device_id TEXT
);

-- 2. Messages table
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tokens INTEGER DEFAULT 0,
    meta_json TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- 3. FTS5 Virtual table for full-text search over message content
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    message_id UNINDEXED,
    session_id UNINDEXED,
    content,
    tokenize='porter unicode61'
);

-- 4. Triggers to maintain messages_fts synchronization
CREATE TRIGGER IF NOT EXISTS trg_messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(message_id, session_id, content)
    VALUES (new.id, new.session_id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS trg_messages_ad AFTER DELETE ON messages BEGIN
    DELETE FROM messages_fts WHERE message_id = old.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_messages_au AFTER UPDATE ON messages BEGIN
    DELETE FROM messages_fts WHERE message_id = old.id;
    INSERT INTO messages_fts(message_id, session_id, content)
    VALUES (new.id, new.session_id, new.content);
END;

-- 5. Devices table (single user, device tokens)
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    revoked INTEGER DEFAULT 0
);

-- 6. Settings table (key-value configuration)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_devices_token_hash ON devices(token_hash);
"""


async def init_db(conn: aiosqlite.Connection) -> None:
    """Initialize database tables, indexes, and triggers."""
    await conn.executescript(SCHEMA_SQL)
    await conn.commit()
