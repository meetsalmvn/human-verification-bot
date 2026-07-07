"""Inline keyboards used during the verification flow."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.challenge_service import Challenge
from app.utils.security import build_callback_data

CALLBACK_PREFIX = "vrfy"


def build_challenge_keyboard(token: str, challenge: Challenge) -> InlineKeyboardMarkup:
    """Build a 2-column inline keyboard for a challenge's options."""
    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=build_callback_data(CALLBACK_PREFIX, token, payload),
        )
        for label, payload in challenge.options
    ]

    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_start_verification_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Deep-link button used in the group-request notice / fallback message."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Begin Verification",
                    url=f"https://t.me/{bot_username}?start=verify",
                )
            ]
        ]
    )
