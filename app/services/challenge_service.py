"""
Generates human-verification challenges.

Each challenge produces:
    - a human-readable question
    - a shuffled list of (label, payload) button options
    - the correct payload that must be returned via callback

Supported types: math, emoji, button, word. "random" picks one of the four
uniformly at random.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

CHALLENGE_TYPES = ("math", "emoji", "button", "word")

_EMOJIS = ["🍎", "🚗", "🎧", "⚽️", "🌙", "🐢", "🎈", "🔥", "🍕", "🎸", "🌈", "⭐️"]

_WORDS = [
    "PURPLE",
    "GRANITE",
    "VELVET",
    "COMPASS",
    "LANTERN",
    "MERIDIAN",
    "WHISPER",
    "GLACIER",
    "ORCHARD",
    "SAPPHIRE",
]


@dataclass(slots=True)
class Challenge:
    challenge_type: str
    question: str
    options: list[tuple[str, str]]  # (button label, callback payload)
    correct_payload: str


def _make_math_challenge() -> Challenge:
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    op = random.choice(["+", "-", "×"])
    if op == "+":
        answer = a + b
    elif op == "-":
        # Ensure a non-negative result for a friendlier challenge.
        a, b = max(a, b), min(a, b)
        answer = a - b
    else:
        a, b = random.randint(2, 9), random.randint(2, 9)
        answer = a * b

    question = f"What is <b>{a} {op} {b}</b>?"

    distractors = set()
    while len(distractors) < 3:
        delta = random.choice([-3, -2, -1, 1, 2, 3])
        candidate = answer + delta
        if candidate != answer and candidate >= 0:
            distractors.add(candidate)

    values = [answer, *distractors]
    random.shuffle(values)
    options = [(str(v), str(v)) for v in values]
    return Challenge("math", question, options, str(answer))


def _make_emoji_challenge() -> Challenge:
    chosen = random.sample(_EMOJIS, 4)
    target = random.choice(chosen)
    question = f"Tap the {target} emoji below."
    options = [(emoji, emoji) for emoji in chosen]
    random.shuffle(options)
    return Challenge("emoji", question, options, target)


def _make_button_challenge() -> Challenge:
    # Simple "prove you're not a bot" single-button captcha with decoys.
    token_suffix = "".join(random.choices(string.ascii_uppercase, k=3))
    question = "Tap the <b>correct</b> button to confirm you're human."
    correct_label = f"✅ I'm human ({token_suffix})"
    decoys = ["🤖 Bot", "❌ Skip", "🚫 Not me"]
    options = [(correct_label, "correct")]
    for d in decoys:
        options.append((d, f"decoy_{d}"))
    random.shuffle(options)
    return Challenge("button", question, options, "correct")


def _make_word_challenge() -> Challenge:
    chosen = random.sample(_WORDS, 4)
    target = random.choice(chosen)
    question = f"Select the word <b>{target}</b> from the list below."
    options = [(word, word) for word in chosen]
    random.shuffle(options)
    return Challenge("word", question, options, target)


_GENERATORS = {
    "math": _make_math_challenge,
    "emoji": _make_emoji_challenge,
    "button": _make_button_challenge,
    "word": _make_word_challenge,
}


def generate_challenge(challenge_type: str = "random") -> Challenge:
    """Generate a challenge of the requested type ('random' picks any)."""
    if challenge_type not in _GENERATORS:
        challenge_type = random.choice(CHALLENGE_TYPES)
    return _GENERATORS[challenge_type]()
