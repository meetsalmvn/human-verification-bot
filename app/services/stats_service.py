"""Aggregates verification statistics for the /stats admin command."""

from __future__ import annotations

from dataclasses import dataclass

from app.database.db import Database


@dataclass(slots=True)
class Stats:
    verified: int
    rejected: int
    pending: int
    total_requests: int


async def collect_stats(db: Database) -> Stats:
    verified = await db.count_users_by_status("verified")
    rejected = await db.count_users_by_status("rejected")
    pending = await db.count_pending_requests_by_status("awaiting_start") + \
        await db.count_pending_requests_by_status("in_progress")
    total_requests = await db.count_all_pending_requests()
    return Stats(verified=verified, rejected=rejected, pending=pending, total_requests=total_requests)
