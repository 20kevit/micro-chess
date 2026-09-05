"""Shared read-only position source (Lichess puzzles.db + fallback).

Conceptual flow for every exercise that needs real board positions::

    puzzles.db (shared, read-only)
        -> positions.repository (this module: data access only)
        -> exercise-specific generator (e.g. piece_recognition.generator)
        -> exercise validator / API

This module knows NOTHING about exercises, questions, or answers. It only
hands out validated FEN strings. Future exercises reuse the same functions.

``puzzles.db`` schema (Lichess dump; only FEN is used here)::

    CREATE TABLE "puzzles" ("Puzzleld" TEXT, "FEN" TEXT, "Rating" INTEGER,
                            "Themes" TEXT, "Moves" TEXT);

The file is optional local data and is never committed (see .gitignore):
- Path resolution: ``PUZZLES_DB_PATH`` env var, else ``puzzles.db`` next to
  the repo/backend working directory.
- When the file is missing/unreadable, or a row is invalid, callers get a
  curated fallback FEN instead of an exception. Invalid rows are skipped
  (up to ``max_attempts`` tries) and never break the exercise.
- Only one row is fetched per call (indexed rowid probing); the
  whole table is never loaded into memory.
"""

from __future__ import annotations

import os
import random
import sqlite3
from pathlib import Path

import chess

SOURCE_ENV_VAR = "PUZZLES_DB_PATH"
SOURCE_FILENAME = "puzzles.db"

# Hand-checked realistic positions (queens/knights/minors missing in several
# of them so zero-target questions occur naturally). Used when puzzles.db is
# absent and covered by tests.
FALLBACK_FENS: tuple[str, ...] = (
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r1b2rk1/pp1n1ppp/2p1p3/3pP3/3P4/2NB1N2/PP3PPP/R4RK1 w - - 0 12",
    "r1bqk2r/ppp2ppp/2p1p3/3p4/2PP4/2P1P3/PP3PPP/R1BQK2R w KQkq - 0 1",
    "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1",
    "6k1/5ppp/3b4/8/8/5N2/5PPP/6K1 w - - 0 1",
    "rnbq1rk1/pp3ppp/4p3/2ppP3/3P4/2N2N2/PPP2PPP/R1BQ1RK1 w - - 0 7",
    "rnb1kbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1",
    "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 0 1",
    "r1bq1rk1/pp1n1ppp/2p1pn2/3p4/2PP4/2N1PN2/PP3PPP/R1BQK2R w KQ - 0 1",
    "8/5pk1/5p1p/8/8/5P1P/5PK1/8 w - - 0 1",
    "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 0 1",
)


def resolve_source_path(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """Locate puzzles.db. Returns None when no usable file exists.

    A pinned path (explicit argument or ``PUZZLES_DB_PATH``) is
    authoritative: when it does not point at a file, None is returned and
    no further discovery happens, so callers deterministically fall back.
    Without a pinned path, the working-directory candidates are searched.
    """
    if explicit is not None:
        candidate = Path(explicit)
        try:
            return candidate if candidate.is_file() else None
        except OSError:
            return None
    env_path = os.environ.get(SOURCE_ENV_VAR)
    if env_path:
        candidate = Path(env_path)
        try:
            return candidate if candidate.is_file() else None
        except OSError:
            return None
    candidates = [
        Path.cwd() / SOURCE_FILENAME,
        Path.cwd() / "backend" / SOURCE_FILENAME,
        Path(__file__).resolve().parent.parent.parent.parent / SOURCE_FILENAME,
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def is_valid_fen(fen: str) -> bool:
    """Server-side FEN validation: must parse with python-chess."""
    if not isinstance(fen, str) or not fen.strip():
        return False
    try:
        chess.Board(fen.strip())
    except ValueError:
        return False
    return True


def fetch_random_fen(
    source: str | os.PathLike[str],
    rng: random.Random | None = None,
    probes: int = 50,
) -> str | None:
    """Fetch one random FEN from puzzles.db (read-only, single row).

    Uses indexed rowid probing (``MAX(rowid)`` + ``WHERE rowid >= ?``), so
    even multi-million-row dumps answer in milliseconds without loading the
    table. Returns None when the file/table is unusable or no valid row is
    found within ``probes`` tries; the caller decides whether to retry or
    fall back. Never raises for data problems.
    """
    rng = rng if rng is not None else random
    try:
        conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        try:
            row = conn.execute("SELECT MAX(rowid) FROM puzzles").fetchone()
        except sqlite3.Error:
            return None
        top = int(row[0]) if row and row[0] else 0
        if top <= 0:
            return None
        for _ in range(max(1, probes)):
            hit = (
                conn.execute(
                    "SELECT FEN FROM puzzles WHERE rowid >= ? ORDER BY rowid LIMIT 1",
                    (rng.randint(1, top),),
                ).fetchone()
            )
            if not hit or not hit[0]:
                continue
            fen = str(hit[0]).strip()
            if is_valid_fen(fen):
                return fen
        return None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def count_positions(source: str | os.PathLike[str]) -> int:
    """Row count of the shared source (0 when unusable). Diagnostic only."""
    try:
        conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    except sqlite3.Error:
        return 0
    try:
        try:
            row = conn.execute("SELECT COUNT(*) FROM puzzles").fetchone()
        except sqlite3.Error:
            return 0
        return int(row[0]) if row else 0
    finally:
        conn.close()


def random_position_fen(
    rng: random.Random | None = None,
    explicit_path: str | os.PathLike[str] | None = None,
    max_attempts: int = 25,
) -> tuple[str, str]:
    """Return ``(fen, source)`` where source is ``"puzzles.db"`` or ``"fallback"``.

    Tries the shared database first (skipping invalid rows), then falls back
    to a random curated FEN. Never raises for missing/invalid data.
    """
    rng = rng if rng is not None else random
    path = resolve_source_path(explicit_path)
    if path is not None:
        for _ in range(max_attempts):
            fen = fetch_random_fen(path)
            if fen is not None:
                return fen, "puzzles.db"
    return rng.choice(FALLBACK_FENS), "fallback"
