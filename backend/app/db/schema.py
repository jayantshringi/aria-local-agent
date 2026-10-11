"""Database schema definitions, tables, vector indexes, and triggers."""

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

-- 3. FTS5 Virtual table for full-text keyword search over message content
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

-- 7. Memory Chunks (Phase 2)
CREATE TABLE IF NOT EXISTS memory_chunks (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 8. Memory Vectors (Phase 2: sqlite-vec 768-dim embeddings for nomic-embed-text)
CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(
    chunk_id text,
    embedding float[768]
);

-- 9. Profile Facts (Phase 2: User profile memory with owner approval gate)
CREATE TABLE IF NOT EXISTS profile_facts (
    id TEXT PRIMARY KEY,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 10. Pairing Codes (Phase 3: Multi-device enrollment without master password exposure)
CREATE TABLE IF NOT EXISTS pairing_codes (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    created_by_device_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    claimed_at TEXT,
    claimed_by_device_id TEXT,
    FOREIGN KEY (created_by_device_id) REFERENCES devices(id),
    FOREIGN KEY (claimed_by_device_id) REFERENCES devices(id)
);

-- 11. Audit Log (Phase 4: Agent safety, tool execution audit trail)
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    tool TEXT NOT NULL,
    args_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL,
    approved_by TEXT,
    result_json TEXT,
    error TEXT
);

-- 12. Pending Actions (Phase 4: Approval queue for medium & high risk actions)
CREATE TABLE IF NOT EXISTS pending_actions (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    tool TEXT NOT NULL,
    args_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_at TEXT,
    resolved_by TEXT
);

-- 13. Notes Table (Phase 4: Personal notes tool)
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 14. Reminders Table (Phase 4: Personal reminders tool)
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    due_at TEXT NOT NULL,
    repeat_rule TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_devices_token_hash ON devices(token_hash);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_source ON memory_chunks(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_profile_facts_status ON profile_facts(status);
CREATE INDEX IF NOT EXISTS idx_pairing_codes_code ON pairing_codes(code);
CREATE INDEX IF NOT EXISTS idx_pairing_codes_expires_at ON pairing_codes(expires_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_tool ON audit_log(tool);
CREATE INDEX IF NOT EXISTS idx_pending_actions_status ON pending_actions(status);
CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_reminders_due_at ON reminders(due_at ASC);
"""


async def init_db(conn: aiosqlite.Connection) -> None:
    """Initialize database tables, indexes, triggers, and vector tables."""
    await conn.executescript(SCHEMA_SQL)
    await conn.commit()
