"""Unit tests for the Lichess puzzle CSV parser/validator.

Pure-function coverage: official sample rows must validate, and every
malformed shape must be reported with a stable error code instead of
raising.
"""

import chess

from app.tools.lichess_puzzles import parser

# Official sample rows from https://database.lichess.org/ (puzzle section).
SAMPLE_MATE_IN_2 = (
    "00sHx,q3k1nr/1pp1nQpp/3p4/1P2p3/4P3/B1PP1b2/B5PP/5K2 b k - 0 17,"
    "e8d7 a2e6 d7d8 f7f8,1760,80,83,72,"
    "mate mateIn2 middlegame short,https://lichess.org/yyznGmXs/black#34,"
    "Italian_Game Italian_Game_Classical_Variation,"
)

SAMPLE_LONG = (
    "00sJ9,r3r1k1/p4ppp/2p2n2/1p6/3P1qb1/2NQR3/PPB2PP1/R1B3K1 w - - 5 18,"
    "e3g3 e8e1 g1h2 e1c1 a1c1 f4h6 h2g1 h6c1,2671,105,87,325,"
    "advantage attraction fork middlegame sacrifice veryLong,https://lichess.org/gyFeQsOE#35,"
    "French_Defense French_Defense_Exchange_Variation,1607774862751"
)

SAMPLE_NO_OPENING = (
    "00sO1,1k1r4/pp3pp1/2p1p3/4b3/P3n1P1/8/KPP2PN1/3rBR1R b - - 2 31,"
    "b8c7 e1a5 b7b6 f1d1,998,85,94,293,"
    "advantage discoveredAttack master middlegame short,https://lichess.org/vsfFkG0s/black#62,,"
)


def _cells(line: str) -> list[str]:
    import csv
    import io

    return next(csv.reader(io.StringIO(line)))


def test_official_mate_in_2_row_validates():
    normalized, error = parser.parse_row(_cells(SAMPLE_MATE_IN_2))
    assert error is None, error
    assert normalized["puzzle_id"] == "00sHx"
    assert normalized["rating"] == 1760
    assert normalized["rating_deviation"] == 80
    assert normalized["popularity"] == 83
    assert normalized["nb_plays"] == 72
    assert normalized["themes"] == ["mate", "mateIn2", "middlegame", "short"]
    assert normalized["opponent_move_uci"] == "e8d7"
    assert normalized["solution_uci"] == ["a2e6", "d7d8", "f7f8"]
    assert normalized["daily_date_ms"] is None
    assert normalized["opening_tags"] == ["Italian_Game", "Italian_Game_Classical_Variation"]
    assert normalized["source"] == "lichess"
    assert normalized["source_reference"] == "00sHx"
    # Presented FEN = initial FEN with the opponent move applied.
    board = chess.Board(normalized["fen_initial"])
    board.push(chess.Move.from_uci("e8d7"))
    assert normalized["fen_presented"] == board.fen()


def test_official_long_row_with_daily_date_validates():
    normalized, error = parser.parse_row(_cells(SAMPLE_LONG))
    assert error is None, error
    assert normalized["daily_date_ms"] == 1607774862751
    assert len(normalized["solution_uci"]) == 7
    assert normalized["themes"][0] == "advantage"


def test_official_row_without_opening_tags_validates():
    normalized, error = parser.parse_row(_cells(SAMPLE_NO_OPENING))
    assert error is None, error
    assert normalized["opening_tags"] == []
    assert normalized["daily_date_ms"] is None


def test_header_row_detection():
    assert parser.is_header_row(list(parser.HEADER_FIELDS))
    assert not parser.is_header_row(_cells(SAMPLE_MATE_IN_2))


def test_bad_column_count_reported():
    normalized, error = parser.parse_row(["only", "two"])
    assert normalized is None
    assert error["code"] == "bad_column_count"


def test_unparseable_fen_reported():
    cells = _cells(SAMPLE_MATE_IN_2)
    cells[1] = "not-a-fen"
    normalized, error = parser.parse_row(cells)
    assert normalized is None
    assert error["code"] == "bad_fen"


def test_illegal_move_line_reported():
    cells = _cells(SAMPLE_MATE_IN_2)
    cells[2] = "e8d7 a2a8"  # second move is illegal in sequence
    normalized, error = parser.parse_row(cells)
    assert normalized is None
    assert error["code"] == "bad_moves"


def test_non_uci_move_reported():
    cells = _cells(SAMPLE_MATE_IN_2)
    cells[2] = "e8d7 O-O-O-O"
    normalized, error = parser.parse_row(cells)
    assert normalized is None
    assert error["code"] == "bad_moves"


def test_empty_moves_reported():
    cells = _cells(SAMPLE_MATE_IN_2)
    cells[2] = "  "
    normalized, error = parser.parse_row(cells)
    assert normalized is None
    assert error["code"] == "bad_moves"


def test_rating_out_of_range_reported():
    cells = _cells(SAMPLE_MATE_IN_2)
    cells[3] = "9999"
    normalized, error = parser.parse_row(cells)
    assert normalized is None
    assert error["code"] == "bad_numeric_field"


def test_popularity_out_of_range_reported():
    cells = _cells(SAMPLE_MATE_IN_2)
    cells[5] = "101"
    normalized, error = parser.parse_row(cells)
    assert normalized is None
    assert error["code"] == "bad_numeric_field"


def test_empty_themes_reported():
    cells = _cells(SAMPLE_MATE_IN_2)
    cells[7] = "   "
    normalized, error = parser.parse_row(cells)
    assert normalized is None
    assert error["code"] == "bad_themes"


def test_non_lichess_game_url_reported():
    cells = _cells(SAMPLE_MATE_IN_2)
    cells[8] = "https://example.com/game"
    normalized, error = parser.parse_row(cells)
    assert normalized is None
    assert error["code"] == "bad_game_url"


def test_bad_daily_date_reported():
    cells = _cells(SAMPLE_LONG)
    cells[10] = "not-a-timestamp"
    normalized, error = parser.parse_row(cells)
    assert normalized is None
    assert error["code"] == "bad_daily_date"


def test_empty_puzzle_id_reported():
    cells = _cells(SAMPLE_MATE_IN_2)
    cells[0] = "  "
    normalized, error = parser.parse_row(cells)
    assert normalized is None
    assert error["code"] == "bad_puzzle_id"


def test_split_tags_handles_extra_whitespace():
    assert parser.split_tags("  mate   short ") == ["mate", "short"]
    assert parser.split_tags("") == []
