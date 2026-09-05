"""Shared read-only position source for all exercises.

See ``repository.py``: puzzles.db -> repository -> exercise generator.
This package intentionally has no exercise logic.
"""

from app.modules.positions.repository import (
    FALLBACK_FENS,
    count_positions,
    fetch_random_fen,
    is_valid_fen,
    random_position_fen,
    resolve_source_path,
)

__all__ = [
    "FALLBACK_FENS",
    "count_positions",
    "fetch_random_fen",
    "is_valid_fen",
    "random_position_fen",
    "resolve_source_path",
]
