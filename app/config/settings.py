"""
Application configuration.

All configuration is loaded from environment variables (see .env.example).
A single, cached `Settings` instance is used across the whole application via
`get_settings()`, so configuration is read once and reused everywhere
(simple dependency-injection pattern without a heavy DI framework).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Load .env as early as possible (no-op in prod if the file is absent, since
# real deployments like Northflank inject env vars directly).
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_int_list(name: str) -> List[int]:
    raw = os.getenv(name, "")
    result: List[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            result.append(int(chunk))
        except ValueError:
            continue
    return result


@dataclass(frozen=True)
class Settings:
    """Strongly-typed application configuration."""

    # --- Telegram ---
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    admin_ids: List[int] = field(default_factory=lambda: _get_int_list("ADMIN_IDS"))
    group_id: int = field(default_factory=lambda: _get_int("GROUP_ID", 0))

    # --- Networking / webhook ---
    use_webhook: bool = field(default_factory=lambda: _get_bool("USE_WEBHOOK", True))
    webhook_host: str = field(default_factory=lambda: os.getenv("WEBHOOK_HOST", ""))
    webhook_path: str = field(default_factory=lambda: os.getenv("WEBHOOK_PATH", "/webhook"))
    webhook_secret: str = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", ""))
    webapp_host: str = field(default_factory=lambda: os.getenv("WEBAPP_HOST", "0.0.0.0"))
    webapp_port: int = field(default_factory=lambda: _get_int("PORT", 8080))

    # --- Database ---
    db_path: str = field(
        default_factory=lambda: os.getenv("DB_PATH", str(BASE_DIR / "data" / "bot.db"))
    )

    # --- Verification behaviour (defaults; overridable at runtime via /config) ---
    verification_timeout: int = field(default_factory=lambda: _get_int("VERIFICATION_TIMEOUT", 60))
    max_attempts: int = field(default_factory=lambda: _get_int("MAX_ATTEMPTS", 3))
    default_challenge_type: str = field(
        default_factory=lambda: os.getenv("DEFAULT_CHALLENGE_TYPE", "random")
    )

    # --- Security / rate limiting ---
    rate_limit_window_seconds: float = field(
        default_factory=lambda: float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "1.0"))
    )

    # --- Misc ---
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    maintenance_mode: bool = field(default_factory=lambda: _get_bool("MAINTENANCE_MODE", False))
    bot_username: str = field(default_factory=lambda: os.getenv("BOT_USERNAME", ""))

    def webhook_url(self) -> str:
        host = self.webhook_host.rstrip("/")
        path = self.webhook_path if self.webhook_path.startswith("/") else f"/{self.webhook_path}"
        return f"{host}{path}"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
