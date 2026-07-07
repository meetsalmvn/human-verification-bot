"""Admin-only commands: /stats, /config, /logs, /export, /help, list management."""

from __future__ import annotations

import io
import logging
from typing import Any, Dict

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, Filter
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.config.settings import Settings
from app.database.db import Database
from app.keyboards.admin_kb import (
    CONFIG_PREFIX,
    build_attempts_menu,
    build_challenge_type_menu,
    build_config_menu,
    build_timeout_menu,
)
from app.services.stats_service import collect_stats
from app.utils import texts

logger = logging.getLogger(__name__)
router = Router(name="admin")


class IsAdmin(Filter):
    """Restricts a handler to user IDs listed in ADMIN_IDS."""

    async def __call__(self, event: Message | CallbackQuery, settings: Settings) -> bool:
        user = event.from_user
        return bool(user) and user.id in settings.admin_ids


router.message.filter(IsAdmin())
# Callback queries with the config prefix are also admin-only; enforced
# per-handler below since callback_query filters run for every callback.


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.help_text())


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database) -> None:
    stats = await collect_stats(db)
    await message.answer(
        texts.stats_text(stats.verified, stats.rejected, stats.pending, stats.total_requests)
    )


@router.message(Command("config"))
async def cmd_config(message: Message, db: Database) -> None:
    settings = await db.get_all_settings()
    await message.answer(texts.config_menu_text(settings), reply_markup=build_config_menu(settings))


@router.message(Command("logs"))
async def cmd_logs(message: Message, db: Database) -> None:
    rows = await db.get_recent_logs(limit=20)
    if not rows:
        await message.answer(f"{texts.logs_header()}\n<i>No activity yet.</i>")
        return
    lines = [texts.logs_header()]
    lines.extend(texts.log_line(r["created_at"], r["event_type"], r["message"]) for r in rows)
    await message.answer("\n".join(lines))


@router.message(Command("export"))
async def cmd_export(message: Message, db: Database) -> None:
    rows = await db.get_all_logs()
    buffer = io.StringIO()
    buffer.write("created_at,user_id,chat_id,event_type,message\n")
    for r in rows:
        buffer.write(
            f'{r["created_at"]},{r["user_id"]},{r["chat_id"]},{r["event_type"]},"{r["message"]}"\n'
        )
    data = buffer.getvalue().encode("utf-8")
    file = BufferedInputFile(data, filename="verification_logs.csv")
    await message.answer_document(file, caption=f"📤 Exported {len(rows)} log entries.")


def _parse_target_user_id(command: CommandObject, message: Message) -> int | None:
    if command.args and command.args.strip().isdigit():
        return int(command.args.strip())
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    return None


@router.message(Command("whitelist"))
async def cmd_whitelist(message: Message, command: CommandObject, db: Database) -> None:
    user_id = _parse_target_user_id(command, message)
    if user_id is None:
        await message.answer("Usage: <code>/whitelist &lt;user_id&gt;</code> (or reply to a user's message).")
        return
    await db.upsert_user(user_id, None, None, None)
    await db.set_whitelist(user_id, True)
    await db.add_log("whitelisted", "Added to whitelist by admin", user_id)
    await message.answer(f"✅ User <code>{user_id}</code> whitelisted.")


@router.message(Command("unwhitelist"))
async def cmd_unwhitelist(message: Message, command: CommandObject, db: Database) -> None:
    user_id = _parse_target_user_id(command, message)
    if user_id is None:
        await message.answer("Usage: <code>/unwhitelist &lt;user_id&gt;</code>")
        return
    await db.set_whitelist(user_id, False)
    await db.add_log("unwhitelisted", "Removed from whitelist by admin", user_id)
    await message.answer(f"✅ User <code>{user_id}</code> removed from whitelist.")


@router.message(Command("blacklist"))
async def cmd_blacklist(message: Message, command: CommandObject, db: Database) -> None:
    user_id = _parse_target_user_id(command, message)
    if user_id is None:
        await message.answer("Usage: <code>/blacklist &lt;user_id&gt;</code> (or reply to a user's message).")
        return
    await db.upsert_user(user_id, None, None, None)
    await db.set_blacklist(user_id, True)
    await db.add_log("blacklisted", "Added to blacklist by admin", user_id)
    await message.answer(f"🚫 User <code>{user_id}</code> blacklisted.")


@router.message(Command("unblacklist"))
async def cmd_unblacklist(message: Message, command: CommandObject, db: Database) -> None:
    user_id = _parse_target_user_id(command, message)
    if user_id is None:
        await message.answer("Usage: <code>/unblacklist &lt;user_id&gt;</code>")
        return
    await db.set_blacklist(user_id, False)
    await db.add_log("unblacklisted", "Removed from blacklist by admin", user_id)
    await message.answer(f"✅ User <code>{user_id}</code> removed from blacklist.")


# ----------------------------------------------------------------------
# /config interactive menu callbacks
# ----------------------------------------------------------------------
@router.callback_query(F.data.startswith(f"{CONFIG_PREFIX}:"))
async def on_config_callback(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if not callback.from_user or callback.from_user.id not in settings.admin_ids:
        await callback.answer("Admins only.", show_alert=True)
        return

    _, action, *rest = callback.data.split(":")

    if action == "toggle_verification":
        current = await db.get_setting("verification_enabled", "1")
        await db.set_setting("verification_enabled", "0" if current == "1" else "1")

    elif action == "toggle_maintenance":
        current = await db.get_setting("maintenance_mode", "0")
        await db.set_setting("maintenance_mode", "0" if current == "1" else "1")

    elif action == "timeout_menu":
        await callback.message.edit_text(
            "⏱ Choose a verification timeout:", reply_markup=build_timeout_menu()
        )
        await callback.answer()
        return

    elif action == "attempts_menu":
        await callback.message.edit_text(
            "🔁 Choose the maximum number of attempts:", reply_markup=build_attempts_menu()
        )
        await callback.answer()
        return

    elif action == "challenge_menu":
        await callback.message.edit_text(
            "🧩 Choose the challenge type:", reply_markup=build_challenge_type_menu()
        )
        await callback.answer()
        return

    elif action == "set_timeout" and rest:
        await db.set_setting("verification_timeout", rest[0])

    elif action == "set_attempts" and rest:
        await db.set_setting("max_attempts", rest[0])

    elif action == "set_challenge" and rest:
        await db.set_setting("challenge_type", rest[0])

    elif action == "close":
        await callback.message.delete()
        await callback.answer()
        return

    # "back" and any settings-changing action fall through to redraw the
    # main menu with fresh values.
    updated_settings = await db.get_all_settings()
    await callback.message.edit_text(
        texts.config_menu_text(updated_settings), reply_markup=build_config_menu(updated_settings)
    )
    await callback.answer("Updated ✅" if action not in {"back", "close"} else None)
