"""
Simple in-memory rate-limiting middleware.

Prevents a user from spamming callback-query answers or commands faster than
`rate_limit_window_seconds`, which mitigates brute-forcing verification
answers and general abuse. For a multi-process deployment this in-memory
store should be swapped for Redis; documented as a future improvement.
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit_seconds: float = 1.0) -> None:
        self.rate_limit_seconds = rate_limit_seconds
        self._last_seen: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user_id = event.from_user.id

        if user_id is not None:
            now = time.monotonic()
            last = self._last_seen.get(user_id, 0.0)
            if now - last < self.rate_limit_seconds:
                if isinstance(event, CallbackQuery):
                    await event.answer("Please slow down a little.", show_alert=False)
                return None
            self._last_seen[user_id] = now

        return await handler(event, data)
