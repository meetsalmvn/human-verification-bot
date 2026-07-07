"""
Catches and logs unhandled exceptions raised inside handlers so a single bad
update can never crash the polling/webhook loop. Telegram API errors,
database errors, and any other exception are logged with full context.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class ErrorLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:  # noqa: BLE001 - intentionally broad, this is the safety net
            logger.exception("Unhandled exception while processing update: %s", event)
            return None
