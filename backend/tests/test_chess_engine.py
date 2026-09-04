"""Standard chess behavior stays in chess_engine (python-chess wrapper)."""

from app.modules.chess_engine import board

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_startpos_has_20_legal_moves():
    assert len(board.legal_moves_uci(STARTPOS)) == 20


def test_e2e4_is_legal_and_e2e5_is_not():
    assert board.is_legal_uci(STARTPOS, "e2e4") is True
    assert board.is_legal_uci(STARTPOS, "e2e5") is False


def test_piece_at():
    assert board.piece_at(STARTPOS, "e2") == "P"
    assert board.piece_at(STARTPOS, "e4") is None
