"""Thin python-chess wrapper. Standard chess only; custom rules live elsewhere."""

import chess

from app.modules.chess_engine import board as _b  # noqa: F401

__all__ = ["board"]
