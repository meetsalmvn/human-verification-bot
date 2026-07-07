"""
Security helpers.

Handles verification-token generation and constant-time comparisons so that
callback data cannot be trivially forged or replayed against a different
session.
"""

from __future__ import annotations

import hmac
import secrets


def generate_token(length: int = 16) -> str:
    """Generate a URL-safe random token used to identify a verification session.

    Using `secrets.token_urlsafe` (CSPRNG) instead of `uuid4` or predictable
    counters prevents an attacker from guessing valid session tokens and
    replaying stale callback data against a different / expired session.
    """
    return secrets.token_urlsafe(length)


def tokens_match(token_a: str, token_b: str) -> bool:
    """Constant-time string comparison to avoid timing attacks."""
    return hmac.compare_digest(token_a, token_b)


def build_callback_data(prefix: str, token: str, payload: str) -> str:
    """Build compact callback_data, staying under Telegram's 64-byte limit."""
    data = f"{prefix}:{token}:{payload}"
    if len(data.encode("utf-8")) > 64:
        raise ValueError("callback_data exceeds Telegram's 64 byte limit")
    return data


def parse_callback_data(data: str) -> tuple[str, str, str]:
    """Parse callback_data of the form 'prefix:token:payload'."""
    parts = data.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"Malformed callback data: {data!r}")
    return parts[0], parts[1], parts[2]
