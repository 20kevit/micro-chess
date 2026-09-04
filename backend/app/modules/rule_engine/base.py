"""Shared validator contract. Exercise modules implement this; core flow only uses it."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AttemptResult(str, Enum):
    CORRECT = "correct"
    PARTIAL = "partial"
    WRONG = "wrong"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    ABANDONED = "abandoned"


class AttemptMode(str, Enum):
    RATED = "rated"
    PRACTICE = "practice"


@dataclass(frozen=True)
class ValidationResult:
    result: AttemptResult
    # i18n key for feedback; frontend maps it to Persian text.
    message_key: str = ""
    # Structured per-exercise detail (e.g. correct/missed/wrong squares).
    # Returned to the client but never trusted from the client.
    detail: dict[str, Any] = field(default_factory=dict)


_FILES = "abcdefgh"


def normalize_square(raw: Any) -> str | None:
    """Lowercase/validate a single square name. Returns None when malformed."""
    if not isinstance(raw, str):
        return None
    sq = raw.strip().lower()
    if len(sq) != 2 or sq[0] not in _FILES or sq[1] not in "12345678":
        return None
    return sq


def split_squares(raw: Any) -> tuple[set[str], list[str]]:
    """Split raw input into (valid squares, malformed entries).

    Malformed entries are returned as strings so callers can count them
    as incorrect selections without crashing.
    """
    items = raw if isinstance(raw, list) else []
    valid: set[str] = set()
    malformed: list[str] = []
    for entry in items:
        sq = normalize_square(entry)
        if sq is None:
            malformed.append(str(entry))
        else:
            valid.add(sq)
    return valid, malformed
