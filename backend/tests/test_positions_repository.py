"""Shared positions repository: puzzles.db read-only access + fallback."""

import sqlite3
import time

import pytest

import chess

from app.modules.positions import repository as repo


def _make_source_db(path, rows):
    conn = sqlite3.connect(str(path))
    conn.execute(
        'CREATE TABLE "puzzles" ("Puzzleld" TEXT, "FEN" TEXT, "Rating" INTEGER, "Themes" TEXT, "Moves" TEXT)'
    )
    conn.execute("CREATE INDEX idx_rating ON puzzles(rating)")
    conn.execute("CREATE INDEX idx_themes ON puzzles(themes)")
    for fen in rows:
        conn.execute(
            "INSERT INTO puzzles (Puzzleld, FEN, Rating, Themes, Moves) VALUES (?, ?, ?, ?, ?)",
            ("id1", fen, 1500, "theme", "e2e4"),
        )
    conn.commit()
    conn.close()


def test_fallback_fens_all_valid():
    assert len(repo.FALLBACK_FENS) >= 10
    for fen in repo.FALLBACK_FENS:
        assert repo.is_valid_fen(fen), fen
        chess.Board(fen)  # raises on invalid


def test_invalid_fen_rejected():
    assert not repo.is_valid_fen("")
    assert not repo.is_valid_fen(None)
    assert not repo.is_valid_fen("not a fen")
    assert not repo.is_valid_fen("rnbqkbnr/pppppppp/9/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    # Bare placement parses under python-chess rules, so it counts as usable.
    assert repo.is_valid_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR")


def test_random_position_without_db_uses_fallback(monkeypatch):
    # Pinned-missing path is authoritative: no discovery elsewhere, even if
    # a real puzzles.db sits in the working directory.
    monkeypatch.delenv(repo.SOURCE_ENV_VAR, raising=False)
    fen, source = repo.random_position_fen(explicit_path="/nonexistent/puzzles.db")
    assert source == "fallback"
    assert repo.is_valid_fen(fen)


def test_fetch_random_from_real_db_file(tmp_path):
    path = tmp_path / "puzzles.db"
    good = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    _make_source_db(path, [good])
    assert repo.count_positions(path) == 1
    assert repo.fetch_random_fen(path) == good
    fen, source = repo.random_position_fen(explicit_path=path)
    assert (fen, source) == (good, "puzzles.db")


def test_invalid_rows_are_skipped(tmp_path):
    path = tmp_path / "puzzles.db"
    good = "8/5pk1/5p1p/8/8/5P1P/5PK1/8 w - - 0 1"
    _make_source_db(path, ["garbage-not-fen", "", good])
    seen = {repo.fetch_random_fen(path) for _ in range(10)}
    seen.discard(None)
    assert seen == {good}


def test_missing_file_returns_none_and_zero(tmp_path, monkeypatch):
    monkeypatch.delenv(repo.SOURCE_ENV_VAR, raising=False)
    missing = tmp_path / "nope.db"
    assert repo.fetch_random_fen(missing) is None
    assert repo.count_positions(missing) == 0
    assert repo.resolve_source_path(explicit=missing) is None


def test_pinned_missing_path_ignores_discovery(tmp_path, monkeypatch):
    # Even when a usable source exists, a pinned missing path yields None.
    real = tmp_path / "puzzles.db"
    _make_source_db(real, ["8/8/8/8/8/8/8/4K2k w - - 0 1"])
    monkeypatch.setenv(repo.SOURCE_ENV_VAR, str(tmp_path / "absent.db"))
    assert repo.resolve_source_path() is None
    fen, source = repo.random_position_fen()
    assert source == "fallback"


def test_resolve_prefers_env_var(tmp_path, monkeypatch):
    path = tmp_path / "puzzles.db"
    _make_source_db(path, ["8/8/8/8/8/8/8/4K2k w - - 0 1"])
    monkeypatch.setenv(repo.SOURCE_ENV_VAR, str(path))
    assert repo.resolve_source_path() == path


def test_real_puzzles_db_when_present(monkeypatch):
    """Production-data integration: runs only when a contributor-local
    puzzles.db exists (never committed); otherwise skipped."""
    monkeypatch.delenv(repo.SOURCE_ENV_VAR, raising=False)
    path = repo.resolve_source_path()
    if path is None:
        pytest.skip("no puzzles.db present; contributor-local data")
    assert repo.count_positions(path) > 0
    started = time.perf_counter()
    fen = repo.fetch_random_fen(path)
    elapsed = time.perf_counter() - started
    print(f"\nreal puzzles.db: count={repo.count_positions(path)} fetch_s={elapsed:.2f}")
    assert fen is not None and repo.is_valid_fen(fen)
    fen, source = repo.random_position_fen()
    assert source == "puzzles.db" and repo.is_valid_fen(fen)
