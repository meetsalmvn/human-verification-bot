"""
Async SQLite database layer.

A single aiosqlite connection is shared across the application, guarded by an
asyncio.Lock for write safety. This keeps the project dependency-light (no
ORM) while still being fully async and safe under aiogram's event loop.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional, Sequence

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY,
    username        TEXT,
    first_name      TEXT,
    last_name       TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    is_whitelisted  INTEGER NOT NULL DEFAULT 0,
    is_blacklisted  INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    verified_at     TEXT
);

CREATE TABLE IF NOT EXISTS pending_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    chat_id     INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'awaiting_start',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pending_requests_user
    ON pending_requests (user_id, status);

CREATE TABLE IF NOT EXISTS verification_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    token               TEXT NOT NULL UNIQUE,
    user_id             INTEGER NOT NULL,
    chat_id             INTEGER NOT NULL,
    challenge_type      TEXT NOT NULL,
    challenge_question  TEXT NOT NULL,
    correct_answer      TEXT NOT NULL,
    attempts            INTEGER NOT NULL DEFAULT 0,
    max_attempts        INTEGER NOT NULL DEFAULT 3,
    status              TEXT NOT NULL DEFAULT 'active',
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON verification_sessions (token);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON verification_sessions (user_id, status);

CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    chat_id     INTEGER,
    event_type  TEXT NOT NULL,
    message     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_logs_created ON logs (created_at);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "verification_enabled": "1",
    "verification_timeout": "60",
    "max_attempts": "3",
    "challenge_type": "random",  # random | math | emoji | button | word
    "maintenance_mode": "0",
}


class Database:
    """Thin async wrapper around a single SQLite connection."""

    def __init__(self, db_path: str, initial_settings: Optional[dict[str, str]] = None) -> None:
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        # Allows the caller (main.py, driven by env-var Settings) to seed the
        # settings table with values from the environment on first run,
        # falling back to DEFAULT_SETTINGS for anything not provided.
        self._initial_settings = {**DEFAULT_SETTINGS, **(initial_settings or {})}

    async def connect(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        async with self._lock:
            await self._conn.executescript(SCHEMA)
            await self._conn.commit()
        await self._seed_default_settings()
        logger.info("Database connected at %s", self._db_path)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            logger.info("Database connection closed")

    async def _seed_default_settings(self) -> None:
        for key, value in self._initial_settings.items():
            await self._conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        await self._conn.commit()

    # ------------------------------------------------------------------
    # Low level helpers
    # ------------------------------------------------------------------
    async def _execute(self, query: str, params: Sequence[Any] = ()) -> int:
        assert self._conn is not None, "Database not connected"
        async with self._lock:
            cursor = await self._conn.execute(query, params)
            await self._conn.commit()
            return cursor.lastrowid

    async def _fetchone(self, query: str, params: Sequence[Any] = ()) -> Optional[aiosqlite.Row]:
        assert self._conn is not None, "Database not connected"
        async with self._lock:
            cursor = await self._conn.execute(query, params)
            row = await cursor.fetchone()
            return row

    async def _fetchall(self, query: str, params: Sequence[Any] = ()) -> list[aiosqlite.Row]:
        assert self._conn is not None, "Database not connected"
        async with self._lock:
            cursor = await self._conn.execute(query, params)
            rows = await cursor.fetchall()
            return list(rows)

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------
    async def upsert_user(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> None:
        await self._execute(
            """
            INSERT INTO users (user_id, username, first_name, last_name, status)
            VALUES (?, ?, ?, ?, 'pending')
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name
            """,
            (user_id, username, first_name, last_name),
        )

    async def get_user(self, user_id: int) -> Optional[aiosqlite.Row]:
        return await self._fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))

    async def set_user_status(self, user_id: int, status: str) -> None:
        verified_at_clause = ", verified_at = datetime('now')" if status == "verified" else ""
        await self._execute(
            f"UPDATE users SET status = ? {verified_at_clause} WHERE user_id = ?",
            (status, user_id),
        )

    async def set_whitelist(self, user_id: int, value: bool) -> None:
        await self._execute(
            "UPDATE users SET is_whitelisted = ? WHERE user_id = ?", (int(value), user_id)
        )

    async def set_blacklist(self, user_id: int, value: bool) -> None:
        await self._execute(
            "UPDATE users SET is_blacklisted = ? WHERE user_id = ?", (int(value), user_id)
        )

    async def is_whitelisted(self, user_id: int) -> bool:
        row = await self._fetchone("SELECT is_whitelisted FROM users WHERE user_id = ?", (user_id,))
        return bool(row["is_whitelisted"]) if row else False

    async def is_blacklisted(self, user_id: int) -> bool:
        row = await self._fetchone("SELECT is_blacklisted FROM users WHERE user_id = ?", (user_id,))
        return bool(row["is_blacklisted"]) if row else False

    async def count_users_by_status(self, status: str) -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) AS c FROM users WHERE status = ?", (status,)
        )
        return row["c"] if row else 0

    async def count_all_users(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS c FROM users")
        return row["c"] if row else 0

    # ------------------------------------------------------------------
    # Pending join requests
    # ------------------------------------------------------------------
    async def create_pending_request(self, user_id: int, chat_id: int) -> int:
        return await self._execute(
            "INSERT INTO pending_requests (user_id, chat_id, status) VALUES (?, ?, 'awaiting_start')",
            (user_id, chat_id),
        )

    async def get_active_pending_request(self, user_id: int) -> Optional[aiosqlite.Row]:
        """Most recent request still awaiting action for this user."""
        return await self._fetchone(
            """
            SELECT * FROM pending_requests
            WHERE user_id = ? AND status IN ('awaiting_start', 'in_progress')
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id,),
        )

    async def update_pending_request_status(self, request_id: int, status: str) -> None:
        await self._execute(
            "UPDATE pending_requests SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, request_id),
        )

    async def count_pending_requests_by_status(self, status: str) -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) AS c FROM pending_requests WHERE status = ?", (status,)
        )
        return row["c"] if row else 0

    async def count_all_pending_requests(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS c FROM pending_requests")
        return row["c"] if row else 0

    # ------------------------------------------------------------------
    # Verification sessions
    # ------------------------------------------------------------------
    async def create_session(
        self,
        token: str,
        user_id: int,
        chat_id: int,
        challenge_type: str,
        challenge_question: str,
        correct_answer: str,
        max_attempts: int,
        expires_at: str,
    ) -> int:
        return await self._execute(
            """
            INSERT INTO verification_sessions
                (token, user_id, chat_id, challenge_type, challenge_question,
                 correct_answer, max_attempts, expires_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                token,
                user_id,
                chat_id,
                challenge_type,
                challenge_question,
                correct_answer,
                max_attempts,
                expires_at,
            ),
        )

    async def get_session_by_token(self, token: str) -> Optional[aiosqlite.Row]:
        return await self._fetchone(
            "SELECT * FROM verification_sessions WHERE token = ?", (token,)
        )

    async def get_active_session_for_user(self, user_id: int) -> Optional[aiosqlite.Row]:
        return await self._fetchone(
            """
            SELECT * FROM verification_sessions
            WHERE user_id = ? AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id,),
        )

    async def increment_session_attempts(self, session_id: int) -> None:
        await self._execute(
            "UPDATE verification_sessions SET attempts = attempts + 1 WHERE id = ?",
            (session_id,),
        )

    async def set_session_status(self, session_id: int, status: str) -> None:
        await self._execute(
            "UPDATE verification_sessions SET status = ? WHERE id = ?", (status, session_id)
        )

    async def update_session_question(self, session_id: int, question: str, correct_answer: str) -> None:
        await self._execute(
            "UPDATE verification_sessions SET challenge_question = ?, correct_answer = ? WHERE id = ?",
            (question, correct_answer, session_id),
        )

    async def get_active_sessions(self) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT * FROM verification_sessions WHERE status = 'active'")

    async def expire_stale_sessions(self) -> list[aiosqlite.Row]:
        """Return and mark as expired any sessions past their expiry time."""
        rows = await self._fetchall(
            "SELECT * FROM verification_sessions WHERE status = 'active' AND expires_at <= datetime('now')"
        )
        if rows:
            async with self._lock:
                await self._conn.execute(
                    "UPDATE verification_sessions SET status = 'expired' "
                    "WHERE status = 'active' AND expires_at <= datetime('now')"
                )
                await self._conn.commit()
        return rows

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------
    async def add_log(
        self,
        event_type: str,
        message: str,
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
    ) -> None:
        await self._execute(
            "INSERT INTO logs (user_id, chat_id, event_type, message) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, event_type, message),
        )

    async def get_recent_logs(self, limit: int = 20) -> list[aiosqlite.Row]:
        return await self._fetchall(
            "SELECT * FROM logs ORDER BY created_at DESC LIMIT ?", (limit,)
        )

    async def get_all_logs(self) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT * FROM logs ORDER BY created_at DESC")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    async def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = await self._fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self._execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    async def get_all_settings(self) -> dict[str, str]:
        rows = await self._fetchall("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in rows}
