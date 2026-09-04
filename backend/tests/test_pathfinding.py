"""Pathfinding: step rules, path replay, generator, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.pathfinding import seed as seed_mod
from app.modules.pathfinding.generator import TEMPLATES, generate_all, solve
from app.modules.pathfinding.validator import (
    SLUG,
    apply_step,
    iter_moves,
    mover_color,
    replay_path,
    validate,
)
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult

OPEN_KNIGHT = "k5r1/8/8/8/8/8/8/1N5K w - - 0 1"
OPEN_ROOK = "7k/8/8/8/8/8/8/R6K w - - 0 1"


def answer_for(fen: str, start: str, target: str) -> dict:
    return {"fen": fen, "from": start, "target": target}


# --- Movement per piece ---


def test_valid_knight_move():
    out = apply_step(OPEN_KNIGHT, chess.WHITE, "b1", "d2")
    assert out is not None and out["captured"] is None
    assert chess.Board(out["fen"]).piece_at(chess.parse_square("d2")).symbol() == "N"


def test_valid_pawn_moves():
    assert apply_step("k7/8/8/8/8/8/4P3/7K w - - 0 1", chess.WHITE, "e2", "e4") is not None
    assert apply_step("k7/8/8/8/8/8/4P3/7K w - - 0 1", chess.WHITE, "e2", "e3") is not None


def test_valid_bishop_rook_queen_king_moves():
    assert apply_step("k7/8/8/4p3/8/8/8/2B3K1 w - - 0 1", chess.WHITE, "c1", "h6") is not None
    assert apply_step(OPEN_ROOK, chess.WHITE, "a1", "a8") is not None
    assert apply_step("k7/8/8/8/8/8/8/3Q2K1 w - - 0 1", chess.WHITE, "d1", "h5") is not None
    assert apply_step("k7/8/8/8/8/8/3p4/4K3 w - - 0 1", chess.WHITE, "e1", "d2") is not None


def test_blocked_sliding_piece():
    assert apply_step("k7/8/3p4/8/3Q4/8/8/6K1 w - - 0 1", chess.WHITE, "d4", "d8") is None


def test_invalid_movement():
    assert apply_step(OPEN_KNIGHT, chess.WHITE, "b1", "b2") is None  # knight can't go straight
    assert apply_step(OPEN_ROOK, chess.WHITE, "a1", "b2") is None  # rook can't go diagonal
    assert apply_step(OPEN_ROOK, chess.WHITE, "a1", "a1") is None  # null move


def test_off_board_destination():
    with pytest.raises(ValueError):
        apply_step(OPEN_ROOK, chess.WHITE, "a1", "a9")
    assert apply_step(OPEN_ROOK, chess.WHITE, "h8", "a1") is None  # empty origin


# --- Enemy control ---


def test_forbidden_controlled_square():
    # d6 is empty but attacked by the e5 pawn: entry forbidden.
    assert apply_step("k7/8/8/3pp3/4P3/8/8/7K w - - 0 1", chess.WHITE, "d5", "d6") is None


def test_safe_square_allowed():
    assert apply_step("k7/8/8/8/4P3/8/8/7K w - - 0 1", chess.WHITE, "e4", "e5") is not None


def test_capture_on_controlled_square_when_legal():
    out = apply_step("k7/8/5n2/3p4/4P3/8/8/7K w - - 0 1", chess.WHITE, "e4", "d5")
    assert out is not None and out["captured"] == "d5"


def test_capture_removes_enemy():
    out = apply_step("k7/8/5n2/3p4/4P3/8/8/7K w - - 0 1", chess.WHITE, "e4", "d5")
    assert out is not None
    board = chess.Board(out["fen"])
    assert board.piece_at(chess.parse_square("d5")).symbol() == "P"
    assert board.piece_at(chess.parse_square("e4")) is None


def test_newly_opened_path_after_capture():
    # Bishop ray was shut by its own pawn; capturing it opens the diagonal.
    fen = "k7/8/8/8/8/8/3p4/2B4K w - - 0 1"
    first = apply_step(fen, chess.WHITE, "c1", "d2")
    assert first is not None and first["captured"] == "d2"
    second = apply_step(first["fen"], chess.WHITE, "d2", "e3")
    assert second is not None


def test_control_recalculated_after_capture():
    # c1 is attacked by the d2 pawn; after Bxd2 the square is safe.
    before = chess.Board("k7/8/8/8/8/8/3p4/2B4K w - - 0 1")
    assert before.is_attacked_by(chess.BLACK, chess.parse_square("c1")) is True
    out = apply_step("k7/8/8/8/8/8/3p4/2B4K w - - 0 1", chess.WHITE, "c1", "d2")
    assert out is not None
    after = chess.Board(out["fen"])
    assert after.is_attacked_by(chess.BLACK, chess.parse_square("c1")) is False


# --- Paths ---


def test_direct_valid_path():
    run = replay_path(OPEN_KNIGHT, "b1", "d2", ["b1", "d2"])
    assert run["ok"] is True and run["reached"] is True and run["moves"] == 1


def test_multi_step_path():
    run = replay_path("k7/8/8/8/8/8/4P3/7K w - - 0 1", "e2", "e4", ["e2", "e3", "e4"])
    assert run["ok"] is True and run["moves"] == 2


def test_path_requiring_turns():
    run = replay_path(
        "k7/8/8/8/8/8/2p1p3/R5K1 w - - 0 1", "a1", "h1", ["a1", "a6", "h6", "h1"]
    )
    assert run["ok"] is True and run["moves"] == 3


def test_path_around_controlled_squares():
    run = replay_path(
        "k7/8/8/8/3b4/8/8/4K3 w - - 0 1", "e1", "g3", ["e1", "e2", "f3", "g3"]
    )
    assert run["ok"] is True


def test_path_requiring_capture():
    run = replay_path(
        "k7/8/8/3p1p2/4P3/8/8/7K w - - 0 1", "e4", "d6", ["e4", "d5", "d6"]
    )
    assert run["ok"] is True


def test_multiple_valid_paths_accepted():
    fen = "k7/8/8/8/8/8/4P3/7K w - - 0 1"
    assert replay_path(fen, "e2", "e4", ["e2", "e4"])["ok"] is True
    assert replay_path(fen, "e2", "e4", ["e2", "e3", "e4"])["ok"] is True


def test_non_optimal_but_valid_path_accepted():
    run = replay_path(OPEN_ROOK, "a1", "a8", ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8"])
    assert run["ok"] is True and run["moves"] == 7


def test_incomplete_path_rejected():
    run = replay_path(OPEN_ROOK, "a1", "a8", ["a1", "a4"])
    assert run["ok"] is False and run["reached"] is False


def test_path_not_reaching_target_rejected():
    run = replay_path(OPEN_ROOK, "a1", "a8", ["a1", "h1"])
    assert run["ok"] is False


# --- Full validation ---


def test_validate_correct_and_detail():
    out = validate(answer_for(OPEN_KNIGHT, "b1", "d2"), {"path": ["b1", "d2"]})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["reached"] is True
    assert out.detail["moves"] == 1
    assert out.detail["missed"] == []


def test_validate_wrong_step():
    out = validate(answer_for(OPEN_ROOK, "a1", "a8"), {"path": ["a1", "b2"]})
    assert out.result == AttemptResult.WRONG
    assert out.detail["reached"] is False


def test_validate_wrong_start_and_empty():
    assert validate(answer_for(OPEN_ROOK, "a1", "a8"), {"path": ["a2", "a8"]}).result == AttemptResult.WRONG
    assert validate(answer_for(OPEN_ROOK, "a1", "a8"), {"path": []}).result == AttemptResult.WRONG
    assert validate(answer_for(OPEN_ROOK, "a1", "a8"), {}).result == AttemptResult.WRONG


def test_validate_malformed_path_safe():
    assert validate(answer_for(OPEN_ROOK, "a1", "a8"), {"path": "a1a8"}).result == AttemptResult.WRONG
    assert validate(answer_for(OPEN_ROOK, "a1", "a8"), {"path": ["a1", "zz"]}).result == AttemptResult.WRONG
    assert validate(answer_for(OPEN_ROOK, "a1", "a8"), {"path": ["a1", 42]}).result == AttemptResult.WRONG
    assert validate(answer_for("not a fen", "a1", "a8"), {"path": ["a1", "a8"]}).result == AttemptResult.WRONG
    assert validate({}, {"path": ["a1", "a8"]}).result == AttemptResult.WRONG
    assert validate(answer_for(OPEN_ROOK, "a1", "a8"), None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_validate_cannot_force_completion():
    # Skipping straight to the target square is not a path.
    out = validate(answer_for(OPEN_ROOK, "a1", "a8"), {"path": ["a8"], "reached": True})
    assert out.result == AttemptResult.WRONG


def test_validate_target_mismatch_rejected():
    out = validate(answer_for(OPEN_ROOK, "a1", "a8"), {"path": ["a1", "h1"]})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["a8"]


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Generator ---


def test_generator_deterministic_and_complete():
    first = generate_all()
    second = generate_all()
    assert first == second
    assert len(first) == 15
    kinds = sorted({p["kind"] for p in first})
    assert kinds == ["bishop", "king", "knight", "pawn", "queen", "rook"]
    assert all(p["shortest_moves"] >= 1 for p in first)
    assert sum(1 for p in first if p["shortest_moves"] >= 2) >= 8


def test_generated_puzzles_solvable_independently():
    # Raw python-chess recomputation: every generated shortest path replays
    # to the target using only legal moves that avoid enemy attacks.
    for item in TEMPLATES:
        path = solve(item["fen"], item["start"], item["target"])
        assert path is not None and path[0] == item["start"] and path[-1] == item["target"]
        board = chess.Board(item["fen"])
        mover = board.piece_at(chess.parse_square(item["start"])).color
        board.turn = mover
        enemy = not mover
        pos = item["start"]
        for dest in path[1:]:
            assert dest != pos
            move = next(
                m
                for m in board.legal_moves
                if chess.square_name(m.from_square) == pos and chess.square_name(m.to_square) == dest
            )
            target_piece = board.piece_at(move.to_square)
            if target_piece is not None:
                assert target_piece.color == enemy and target_piece.piece_type != chess.KING
                assert board.is_capture(move)
            else:
                assert not board.is_attacked_by(enemy, move.to_square)
            board.push(move)
            board.turn = mover  # only the selected piece ever moves
            pos = dest


# --- Seed ---


def test_seed_count_and_content(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    for puzzle in puzzles:
        assert puzzle.fen
        assert puzzle.position_json["from"]
        assert puzzle.position_json["target"]
        assert puzzle.answer_json == {
            "fen": puzzle.fen,
            "from": puzzle.position_json["from"],
            "target": puzzle.position_json["target"],
        }
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published


# --- Step endpoint + attempt API ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    return puzzle


def test_step_endpoint_accepts_valid_move(client, db_session):
    puzzle = _seeded(db_session)
    start = puzzle.position_json["from"]
    res = client.post(
        "/api/v1/pathfinding/step",
        json={"puzzle_id": puzzle.id, "fen": puzzle.fen, "selected_at": start, "from": start, "to": "d2"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["selected_at"] == "d2"
    assert body["fen"] != puzzle.fen


def test_step_endpoint_rejects_bad_moves(client, db_session):
    puzzle = _seeded(db_session)
    start = puzzle.position_json["from"]
    for payload in [
        {"from": "e5", "to": "e6"},  # wrong piece
        {"from": start, "to": "b2"},  # illegal for a knight... (b1 knight can't reach b2)
        {"from": "zz", "to": "d2"},
        {"from": start, "to": "d2", "fen": "not a fen"},
    ]:
        res = client.post(
            "/api/v1/pathfinding/step",
            json={"puzzle_id": puzzle.id, "fen": payload.pop("fen", puzzle.fen), **payload, "selected_at": start},
        )
        assert res.status_code == 200
        assert res.json()["ok"] is False


def test_step_endpoint_unknown_puzzle(client, db_session):
    res = client.post(
        "/api/v1/pathfinding/step",
        json={"puzzle_id": 999999, "fen": OPEN_KNIGHT, "selected_at": "b1", "from": "b1", "to": "d2"},
    )
    assert res.status_code == 404


def test_step_reaches_target_flag(client, db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    puzzle = next(p for p in puzzles if p.position_json["target"] == "d2")
    start = puzzle.position_json["from"]
    res = client.post(
        "/api/v1/pathfinding/step",
        json={"puzzle_id": puzzle.id, "fen": puzzle.fen, "selected_at": start, "from": start, "to": "d2"},
    )
    assert res.json()["ok"] is True
    assert res.json()["reached"] is True


def test_api_submit_full_path(client, db_session):
    puzzle = _seeded(db_session)
    from app.modules.pathfinding.generator import solve

    path = solve(puzzle.fen, puzzle.position_json["from"], puzzle.position_json["target"])
    assert path is not None
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"path": path}, "mode": "practice"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"path": [puzzle.position_json["from"], "h8"]}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"path": path}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_list_and_detail_hide_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    assert len(res.json()) == 15
    assert "answer_json" not in res.json()[0]
    detail = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert "answer_json" not in detail.json()
