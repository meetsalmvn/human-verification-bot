"""Fallback handlers: non-admin attempts at admin commands, generic replies."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.utils import texts

router = Router(name="common")

_ADMIN_COMMANDS = ("stats", "config", "logs", "export", "whitelist", "unwhitelist", "blacklist", "unblacklist")


@router.message(Command(commands=_ADMIN_COMMANDS))
async def admin_command_denied(message: Message) -> None:
    # Reached only if the admin router's IsAdmin filter already rejected
    # the message, i.e. a non-admin tried to use an admin-only command.
    await message.answer(texts.not_admin())


@router.message()
async def fallback_message(message: Message) -> None:
    # Anything else in a private chat that isn't part of the verification
    # flow — keep it low-noise and point the user at /help.
    if message.chat.type == "private":
        await message.answer(
            "I didn't understand that. Send /start to begin verification, "
            "or /help if you're an administrator."
        )
