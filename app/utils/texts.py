"""
Central place for all user-facing text.

Messages use Telegram HTML parse mode with a consistent "dark" visual style
(bold section headers, monospace tokens, emoji markers) so the bot has a
coherent look across every message. Keeping strings here also makes future
localization straightforward: swap this module for a locale-aware loader
without touching handler logic.
"""

from __future__ import annotations

DIVIDER = "\u2500" * 24  # ─────────────────────


def welcome_no_pending() -> str:
    return (
        "👋 <b>Welcome!</b>\n\n"
        "I don't see a pending join request from you right now.\n"
        "Send a join request to the group first, then press <b>Start</b> "
        "again from the link I send you."
    )


def welcome_start_verification(group_title: str = "the group") -> str:
    return (
        "🛡 <b>Welcome!</b>\n"
        f"{DIVIDER}\n"
        f"Before joining <b>{group_title}</b>, please complete a quick human "
        "verification. This helps keep the community free of bots and spam.\n\n"
        "Tap <b>Begin Verification</b> below to continue."
    )


def challenge_prompt(question: str, attempts_left: int, timeout: int) -> str:
    return (
        "🧩 <b>Human Verification</b>\n"
        f"{DIVIDER}\n"
        f"{question}\n\n"
        f"⏱ You have <b>{timeout} seconds</b>.\n"
        f"🔁 Attempts remaining: <b>{attempts_left}</b>"
    )


def verification_success() -> str:
    return (
        "✅ <b>Verification successful.</b>\n"
        "Welcome! Your join request has been approved. 🎉"
    )


def verification_wrong(attempts_left: int) -> str:
    if attempts_left > 0:
        return f"❌ <b>Incorrect.</b> Attempts remaining: <b>{attempts_left}</b>"
    return "❌ <b>Incorrect.</b> No attempts remaining."


def verification_failed() -> str:
    return (
        "🚫 <b>Verification failed.</b>\n"
        "You've used all your attempts and your join request has been declined.\n"
        "You may send a new join request to try again."
    )


def verification_timeout() -> str:
    return (
        "⌛ <b>Time's up.</b>\n"
        "You didn't complete verification in time, so your join request has "
        "been declined. Feel free to request to join again."
    )


def verification_expired_session() -> str:
    return "⚠️ This verification session is no longer valid. Please request to join again."


def already_verified() -> str:
    return "✅ You're already verified. No action needed."


def blacklisted() -> str:
    return "🚫 You are not permitted to join this group."


def maintenance_mode_notice() -> str:
    return "🛠 Verification is temporarily under maintenance. Please try again shortly."


def not_admin() -> str:
    return "⛔ This command is restricted to administrators."


def help_text() -> str:
    return (
        "🤖 <b>Human Verification Bot — Admin Help</b>\n"
        f"{DIVIDER}\n"
        "<b>/stats</b> — verification statistics\n"
        "<b>/config</b> — interactive settings menu\n"
        "<b>/logs</b> — recent verification activity\n"
        "<b>/export</b> — export all logs as a file\n"
        "<b>/whitelist &lt;user_id&gt;</b> — always auto-approve a user\n"
        "<b>/unwhitelist &lt;user_id&gt;</b> — remove from whitelist\n"
        "<b>/blacklist &lt;user_id&gt;</b> — always auto-decline a user\n"
        "<b>/unblacklist &lt;user_id&gt;</b> — remove from blacklist\n"
        "<b>/help</b> — show this message"
    )


def stats_text(
    verified: int,
    rejected: int,
    pending: int,
    total_requests: int,
) -> str:
    return (
        "📊 <b>Verification Statistics</b>\n"
        f"{DIVIDER}\n"
        f"✅ Verified users: <b>{verified}</b>\n"
        f"❌ Rejected users: <b>{rejected}</b>\n"
        f"⏳ Pending users: <b>{pending}</b>\n"
        f"📥 Total join requests: <b>{total_requests}</b>"
    )


def logs_header() -> str:
    return f"🗒 <b>Recent Activity</b>\n{DIVIDER}"


def log_line(created_at: str, event_type: str, message: str) -> str:
    return f"<code>{created_at}</code> · <b>{event_type}</b> · {message}"


def config_menu_text(settings: dict[str, str]) -> str:
    enabled = "🟢 Enabled" if settings.get("verification_enabled") == "1" else "🔴 Disabled"
    maintenance = "🟢 On" if settings.get("maintenance_mode") == "1" else "⚪️ Off"
    return (
        "⚙️ <b>Bot Configuration</b>\n"
        f"{DIVIDER}\n"
        f"Verification: <b>{enabled}</b>\n"
        f"Timeout: <b>{settings.get('verification_timeout', '60')}s</b>\n"
        f"Max attempts: <b>{settings.get('max_attempts', '3')}</b>\n"
        f"Challenge type: <b>{settings.get('challenge_type', 'random')}</b>\n"
        f"Maintenance mode: <b>{maintenance}</b>\n\n"
        "Use the buttons below to change a setting."
    )


def cannot_dm_user_notice(deep_link: str) -> str:
    return (
        "ℹ️ I couldn't message this user directly — they haven't started a "
        f"private chat with me yet. They'll need to open {deep_link} and "
        "press <b>Start</b> to begin verification."
    )
