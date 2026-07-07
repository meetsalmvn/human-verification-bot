"""
Core orchestration for the human-verification flow.

Responsible for:
    - reacting to chat join requests
    - starting verification once a user presses /start
    - grading answers submitted via inline keyboard callbacks
    - approving / declining join requests
    - scheduling and recovering timeouts
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import CallbackQuery

from app.config.settings import Settings
from app.database.db import Database
from app.keyboards.verification_kb import build_challenge_keyboard, build_start_verification_keyboard
from app.services.challenge_service import generate_challenge
from app.utils import texts
from app.utils.security import generate_token, parse_callback_data, tokens_match

logger = logging.getLogger(__name__)


class VerificationService:
    def __init__(self, bot: Bot, db: Database, settings: Settings) -> None:
        self.bot = bot
        self.db = db
        self.settings = settings
        # token -> asyncio.Task, so timeouts can be cancelled once a session
        # resolves (correct answer / failure / manual decline).
        self._timeout_tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Settings helpers (live-configurable via /config)
    # ------------------------------------------------------------------
    async def _current_settings(self) -> dict[str, str]:
        return await self.db.get_all_settings()

    # ------------------------------------------------------------------
    # Step 1: Join request received
    # ------------------------------------------------------------------
    async def handle_join_request(self, user_id: int, chat_id: int, username, first_name, last_name) -> None:
        await self.db.upsert_user(user_id, username, first_name, last_name)

        if await self.db.is_blacklisted(user_id):
            try:
                await self.bot.decline_chat_join_request(chat_id, user_id)
            except TelegramAPIError as exc:
                logger.warning("Failed to decline blacklisted user %s: %s", user_id, exc)
            await self.db.add_log("blacklist_decline", "Blacklisted user auto-declined", user_id, chat_id)
            return

        if await self.db.is_whitelisted(user_id):
            try:
                await self.bot.approve_chat_join_request(chat_id, user_id)
                await self.db.set_user_status(user_id, "verified")
                await self.db.add_log("whitelist_approve", "Whitelisted user auto-approved", user_id, chat_id)
            except TelegramAPIError as exc:
                logger.warning("Failed to approve whitelisted user %s: %s", user_id, exc)
            return

        settings = await self._current_settings()
        if settings.get("maintenance_mode") == "1":
            await self.db.add_log("maintenance_skip", "Join request received during maintenance", user_id, chat_id)
            # Leave the request pending in Telegram; do not auto-approve or decline.
            return

        if settings.get("verification_enabled") != "1":
            try:
                await self.bot.approve_chat_join_request(chat_id, user_id)
                await self.db.set_user_status(user_id, "verified")
                await self.db.add_log("auto_approve", "Verification disabled, auto-approved", user_id, chat_id)
            except TelegramAPIError as exc:
                logger.warning("Failed to auto-approve %s: %s", user_id, exc)
            return

        await self.db.create_pending_request(user_id, chat_id)
        await self.db.add_log("join_request", "Join request received", user_id, chat_id)

        # Try to proactively DM the user. This only succeeds if they have
        # already started a private chat with the bot at some point.
        try:
            await self.bot.send_message(
                user_id,
                texts.welcome_start_verification(),
            )
            await self.start_verification_for_user(user_id)
        except TelegramForbiddenError:
            logger.info("Cannot DM user %s yet (bot not started)", user_id)
        except TelegramAPIError as exc:
            logger.warning("Unexpected error DMing user %s: %s", user_id, exc)

    # ------------------------------------------------------------------
    # Step 2: /start command -> begin (or resume) verification
    # ------------------------------------------------------------------
    async def start_verification_for_user(self, user_id: int) -> bool:
        """Returns True if a verification challenge was sent, else False."""
        pending = await self.db.get_active_pending_request(user_id)
        if pending is None:
            return False

        existing_session = await self.db.get_active_session_for_user(user_id)
        if existing_session is not None:
            # Resend the same, still-valid challenge instead of creating a
            # new one (prevents a user from spamming /start to reset a timer
            # or generate unlimited attempts).
            await self._send_challenge_message(existing_session, pending["chat_id"])
            return True

        if await self.db.is_blacklisted(user_id):
            await self.bot.send_message(user_id, texts.blacklisted())
            return True

        settings = await self._current_settings()
        if settings.get("maintenance_mode") == "1":
            await self.bot.send_message(user_id, texts.maintenance_mode_notice())
            return True

        timeout_seconds = int(settings.get("verification_timeout", self.settings.verification_timeout))
        max_attempts = int(settings.get("max_attempts", self.settings.max_attempts))
        challenge_type = settings.get("challenge_type", "random")

        challenge = generate_challenge(challenge_type)
        token = generate_token()
        expires_at = (datetime.utcnow() + timedelta(seconds=timeout_seconds)).strftime("%Y-%m-%d %H:%M:%S")

        session_id = await self.db.create_session(
            token=token,
            user_id=user_id,
            chat_id=pending["chat_id"],
            challenge_type=challenge.challenge_type,
            challenge_question=challenge.question,
            correct_answer=challenge.correct_payload,
            max_attempts=max_attempts,
            expires_at=expires_at,
        )
        await self.db.update_pending_request_status(pending["id"], "in_progress")
        await self.db.add_log(
            "challenge_sent", f"Challenge type={challenge.challenge_type}", user_id, pending["chat_id"]
        )

        session_row = await self.db.get_session_by_token(token)
        await self._send_challenge_message(session_row, pending["chat_id"], challenge=challenge)

        self._schedule_timeout(token, timeout_seconds, session_id=session_id)
        return True

    async def _send_challenge_message(self, session_row, chat_id: int, challenge=None) -> None:
        attempts_left = session_row["max_attempts"] - session_row["attempts"]
        settings = await self._current_settings()
        timeout_seconds = int(settings.get("verification_timeout", self.settings.verification_timeout))

        if challenge is None:
            # The original button layout isn't persisted (only the question
            # and correct answer are), so when resending an existing session
            # we regenerate fresh decoy options of the same challenge type
            # and overwrite the stored question/answer to match exactly.
            challenge = generate_challenge(session_row["challenge_type"])
            await self.db.update_session_question(
                session_row["id"], challenge.question, challenge.correct_payload
            )
            session_row = await self.db.get_session_by_token(session_row["token"])

        keyboard = build_challenge_keyboard(session_row["token"], challenge)
        text = texts.challenge_prompt(session_row["challenge_question"], attempts_left, timeout_seconds)
        await self.bot.send_message(session_row["user_id"], text, reply_markup=keyboard)

    # ------------------------------------------------------------------
    # Step 3: user taps an answer button
    # ------------------------------------------------------------------
    async def handle_callback(self, callback: CallbackQuery) -> None:
        try:
            _prefix, token, payload = parse_callback_data(callback.data)
        except ValueError:
            await callback.answer("Invalid action.", show_alert=True)
            return

        session = await self.db.get_session_by_token(token)
        if session is None or session["status"] != "active":
            await callback.answer()
            await callback.message.edit_text(texts.verification_expired_session())
            return

        if session["user_id"] != callback.from_user.id:
            # Someone else tapping a button meant for another user.
            await callback.answer("This isn't your verification challenge.", show_alert=True)
            return

        is_correct = tokens_match(payload, session["correct_answer"])

        if is_correct:
            await callback.answer("✅ Correct!")
            await self.db.set_session_status(session["id"], "passed")
            self._cancel_timeout(token)
            await self._approve(session)
            await callback.message.edit_text(texts.verification_success())
            return

        await self.db.increment_session_attempts(session["id"])
        session = await self.db.get_session_by_token(token)  # refresh attempts count
        attempts_left = session["max_attempts"] - session["attempts"]

        if attempts_left <= 0:
            await callback.answer("❌ Incorrect.")
            await self.db.set_session_status(session["id"], "failed")
            self._cancel_timeout(token)
            await self._decline(session, reason="max_attempts_exceeded")
            await callback.message.edit_text(texts.verification_failed())
            return

        await callback.answer("❌ Incorrect, try again.")
        # Serve a fresh challenge of the same type for the retry, reusing
        # the same token/session row so the timeout keeps counting down.
        settings = await self._current_settings()
        new_challenge = generate_challenge(session["challenge_type"])
        await self.db.update_session_question(session["id"], new_challenge.question, new_challenge.correct_payload)
        keyboard = build_challenge_keyboard(token, new_challenge)
        timeout_seconds = int(settings.get("verification_timeout", self.settings.verification_timeout))
        text = texts.challenge_prompt(new_challenge.question, attempts_left, timeout_seconds)
        await callback.message.edit_text(text, reply_markup=keyboard)

    # ------------------------------------------------------------------
    # Approve / decline
    # ------------------------------------------------------------------
    async def _approve(self, session) -> None:
        user_id, chat_id = session["user_id"], session["chat_id"]
        try:
            await self.bot.approve_chat_join_request(chat_id, user_id)
        except TelegramAPIError as exc:
            logger.warning("Approve failed for %s in %s: %s", user_id, chat_id, exc)
        await self.db.set_user_status(user_id, "verified")
        pending = await self.db.get_active_pending_request(user_id)
        if pending:
            await self.db.update_pending_request_status(pending["id"], "approved")
        await self.db.add_log("approved", "User passed verification", user_id, chat_id)

    async def _decline(self, session, reason: str) -> None:
        user_id, chat_id = session["user_id"], session["chat_id"]
        try:
            await self.bot.decline_chat_join_request(chat_id, user_id)
        except TelegramAPIError as exc:
            logger.warning("Decline failed for %s in %s: %s", user_id, chat_id, exc)
        await self.db.set_user_status(user_id, "rejected")
        pending = await self.db.get_active_pending_request(user_id)
        if pending:
            await self.db.update_pending_request_status(pending["id"], "declined")
        await self.db.add_log("declined", f"reason={reason}", user_id, chat_id)

    # ------------------------------------------------------------------
    # Timeout scheduling / recovery
    # ------------------------------------------------------------------
    def _schedule_timeout(self, token: str, timeout_seconds: int, session_id: int) -> None:
        task = asyncio.create_task(self._timeout_worker(token, timeout_seconds))
        self._timeout_tasks[token] = task

    def _cancel_timeout(self, token: str) -> None:
        task = self._timeout_tasks.pop(token, None)
        if task and not task.done():
            task.cancel()

    async def _timeout_worker(self, token: str, delay_seconds: float) -> None:
        try:
            await asyncio.sleep(delay_seconds)
        except asyncio.CancelledError:
            return

        session = await self.db.get_session_by_token(token)
        if session is None or session["status"] != "active":
            return  # already resolved

        await self.db.set_session_status(session["id"], "expired")
        await self._decline(session, reason="timeout")
        try:
            await self.bot.send_message(session["user_id"], texts.verification_timeout())
        except TelegramAPIError:
            pass
        self._timeout_tasks.pop(token, None)

    async def resume_pending_sessions(self) -> None:
        """Called on startup to recover timeouts lost on process restart."""
        expired = await self.db.expire_stale_sessions()
        for row in expired:
            await self._decline(row, reason="timeout_recovery")
            try:
                await self.bot.send_message(row["user_id"], texts.verification_timeout())
            except TelegramAPIError:
                pass

        # Reschedule remaining time for sessions that are still active.
        settings = await self._current_settings()
        default_timeout = int(settings.get("verification_timeout", self.settings.verification_timeout))
        rows = await self.db.get_active_sessions()
        for row in rows:
            try:
                expires_at = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
                remaining = (expires_at - datetime.utcnow()).total_seconds()
            except (ValueError, TypeError):
                remaining = default_timeout
            remaining = max(remaining, 1)
            self._schedule_timeout(row["token"], remaining, session_id=row["id"])
        if rows:
            logger.info("Resumed %d in-flight verification session(s) after restart", len(rows))
