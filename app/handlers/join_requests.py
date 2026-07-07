"""Handles incoming chat join requests."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ChatJoinRequest

from app.services.verification_service import VerificationService

logger = logging.getLogger(__name__)
router = Router(name="join_requests")


@router.chat_join_request()
async def on_chat_join_request(
    event: ChatJoinRequest, verification_service: VerificationService
) -> None:
    logger.info(
        "Join request: user=%s chat=%s", event.from_user.id, event.chat.id
    )
    await verification_service.handle_join_request(
        user_id=event.from_user.id,
        chat_id=event.chat.id,
        username=event.from_user.username,
        first_name=event.from_user.first_name,
        last_name=event.from_user.last_name,
    )
