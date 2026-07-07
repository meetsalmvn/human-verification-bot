"""
Application entrypoint.

Run with:
    python -m app.main

Behaviour is controlled by the USE_WEBHOOK environment variable:
    - USE_WEBHOOK=true  -> starts an aiohttp web server, registers the
      Telegram webhook, and exposes a /health endpoint (recommended for
      Northflank / any container platform).
    - USE_WEBHOOK=false -> uses long polling (convenient for local dev).
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.bot import create_bot, create_dispatcher
from app.config.settings import get_settings
from app.database.db import Database
from app.services.verification_service import VerificationService
from app.utils.logger import setup_logging

logger = logging.getLogger(__name__)


async def _on_startup_webhook(bot: Bot, settings, verification_service: VerificationService) -> None:
    await verification_service.resume_pending_sessions()
    webhook_url = settings.webhook_url()
    current = await bot.get_webhook_info()
    if current.url != webhook_url:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret or None,
            drop_pending_updates=False,
        )
    logger.info("Webhook set to %s", webhook_url)


async def _on_shutdown(bot: Bot, db: Database) -> None:
    logger.info("Shutting down...")
    await db.close()
    await bot.session.close()


async def _health_check(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def build_aiohttp_app(bot: Bot, dp: Dispatcher, settings, verification_service: VerificationService, db: Database) -> web.Application:
    app = web.Application()
    app.router.add_get("/health", _health_check)
    app.router.add_get("/", _health_check)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret or None,
    )
    webhook_handler.register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)

    async def on_startup(_: web.Application) -> None:
        await db.connect()
        await _on_startup_webhook(bot, settings, verification_service)

    async def on_cleanup(_: web.Application) -> None:
        await _on_shutdown(bot, db)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


async def run_polling(bot: Bot, dp: Dispatcher, verification_service: VerificationService, db: Database) -> None:
    await db.connect()
    await bot.delete_webhook(drop_pending_updates=False)
    await verification_service.resume_pending_sessions()
    try:
        await dp.start_polling(bot)
    finally:
        await _on_shutdown(bot, db)


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN environment variable is required.")

    db = Database(
        settings.db_path,
        initial_settings={
            "verification_timeout": str(settings.verification_timeout),
            "max_attempts": str(settings.max_attempts),
            "challenge_type": settings.default_challenge_type,
            "maintenance_mode": "1" if settings.maintenance_mode else "0",
        },
    )
    bot = create_bot(settings)
    verification_service = VerificationService(bot, db, settings)
    dp = create_dispatcher(settings, db, verification_service)

    if settings.use_webhook:
        if not settings.webhook_host:
            raise RuntimeError("WEBHOOK_HOST must be set when USE_WEBHOOK=true.")
        app = build_aiohttp_app(bot, dp, settings, verification_service, db)
        web.run_app(app, host=settings.webapp_host, port=settings.webapp_port)
    else:
        asyncio.run(run_polling(bot, dp, verification_service, db))


if __name__ == "__main__":
    main()
