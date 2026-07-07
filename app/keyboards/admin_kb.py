"""Inline keyboards for the admin /config panel."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CONFIG_PREFIX = "cfg"


def build_config_menu(settings: dict[str, str]) -> InlineKeyboardMarkup:
    enabled = settings.get("verification_enabled") == "1"
    maintenance = settings.get("maintenance_mode") == "1"

    toggle_verification_label = (
        "🔴 Disable verification" if enabled else "🟢 Enable verification"
    )
    toggle_maintenance_label = (
        "⚪️ Turn off maintenance" if maintenance else "🛠 Turn on maintenance"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_verification_label, callback_data=f"{CONFIG_PREFIX}:toggle_verification")],
            [InlineKeyboardButton(text="⏱ Timeout", callback_data=f"{CONFIG_PREFIX}:timeout_menu")],
            [InlineKeyboardButton(text="🔁 Max attempts", callback_data=f"{CONFIG_PREFIX}:attempts_menu")],
            [InlineKeyboardButton(text="🧩 Challenge type", callback_data=f"{CONFIG_PREFIX}:challenge_menu")],
            [InlineKeyboardButton(text=toggle_maintenance_label, callback_data=f"{CONFIG_PREFIX}:toggle_maintenance")],
            [InlineKeyboardButton(text="✖️ Close", callback_data=f"{CONFIG_PREFIX}:close")],
        ]
    )


def build_timeout_menu() -> InlineKeyboardMarkup:
    options = [30, 60, 90, 120, 180]
    row = [
        InlineKeyboardButton(text=f"{o}s", callback_data=f"{CONFIG_PREFIX}:set_timeout:{o}")
        for o in options
    ]
    rows = [row[i : i + 3] for i in range(0, len(row), 3)]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data=f"{CONFIG_PREFIX}:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_attempts_menu() -> InlineKeyboardMarkup:
    options = [1, 2, 3, 4, 5]
    row = [
        InlineKeyboardButton(text=str(o), callback_data=f"{CONFIG_PREFIX}:set_attempts:{o}")
        for o in options
    ]
    rows = [row[i : i + 3] for i in range(0, len(row), 3)]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data=f"{CONFIG_PREFIX}:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_challenge_type_menu() -> InlineKeyboardMarkup:
    options = ["random", "math", "emoji", "button", "word"]
    rows = [
        [InlineKeyboardButton(text=o.title(), callback_data=f"{CONFIG_PREFIX}:set_challenge:{o}")]
        for o in options
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data=f"{CONFIG_PREFIX}:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
