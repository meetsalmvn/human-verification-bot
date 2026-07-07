"""Handles /start (verification entry point) and challenge button taps."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.database.db import Database
from app.keyboards.verification_kb import CALLBACK_PREFIX
from app.services.verification_service import VerificationService
from app.utils import texts

logger = logging.getLogger(__name__)
router = Router(name="verification")


@router.message(CommandStart())
async def on_start(message: Message, verification_service: VerificationService, db: Database) -> None:
    user = message.from_user
    await db.upsert_user(user.id, user.username, user.first_name, user.last_name)

    if await db.is_blacklisted(user.id):
        await message.answer(texts.blacklisted())
        return

    existing_user = await db.get_user(user.id)
    if existing_user and existing_user["status"] == "verified":
        pending = await db.get_active_pending_request(user.id)
        if pending is None:
            await message.answer(texts.already_verified())
            return

    started = await verification_service.start_verification_for_user(user.id)
    if not started:
        await message.answer(texts.welcome_no_pending())


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}:"))
async def on_verification_answer(
    callback: CallbackQuery, verification_service: VerificationService
) -> None:
    await verification_service.handle_callback(callback)
