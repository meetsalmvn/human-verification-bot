"""
Plain dataclasses representing database rows.

These are intentionally simple (no ORM) since the project uses raw SQL via
aiosqlite for transparency and minimal dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class User:
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    status: str  # pending | verified | rejected | banned
    is_whitelisted: bool
    is_blacklisted: bool
    created_at: str
    verified_at: Optional[str]


@dataclass(slots=True)
class PendingRequest:
    id: int
    user_id: int
    chat_id: int
    status: str  # awaiting_start | in_progress | approved | declined | expired
    created_at: str
    updated_at: str


@dataclass(slots=True)
class VerificationSession:
    id: int
    token: str
    user_id: int
    chat_id: int
    challenge_type: str
    challenge_question: str
    correct_answer: str
    attempts: int
    max_attempts: int
    status: str  # active | passed | failed | expired
    created_at: str
    expires_at: str


@dataclass(slots=True)
class LogEntry:
    id: int
    user_id: Optional[int]
    chat_id: Optional[int]
    event_type: str
    message: str
    created_at: str
