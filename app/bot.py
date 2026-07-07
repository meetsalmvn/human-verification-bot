"""Builds the configured Bot and Dispatcher instances."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config.settings import Settings
from app.database.db import Database
from app.handlers import get_root_router
from app.middlewares.error_logging import ErrorLoggingMiddleware
from app.middlewares.throttling import ThrottlingMiddleware
from app.services.verification_service import VerificationService


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings, db: Database, verification_service: VerificationService) -> Dispatcher:
    dp = Dispatcher()

    # Middlewares (order matters: error logging wraps everything, then throttling).
    dp.update.outer_middleware(ErrorLoggingMiddleware())
    dp.message.middleware(ThrottlingMiddleware(settings.rate_limit_window_seconds))
    dp.callback_query.middleware(ThrottlingMiddleware(settings.rate_limit_window_seconds))

    # Dependency injection: these become available as handler kwargs.
    dp["settings"] = settings
    dp["db"] = db
    dp["verification_service"] = verification_service

    dp.include_router(get_root_router())
    return dp
