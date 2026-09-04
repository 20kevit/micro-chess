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
