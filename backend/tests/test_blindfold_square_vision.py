"""Blindfold Square Vision: distances, validation, seed, API."""

from collections import deque

from app.modules.exercises import registry
from app.modules.blindfold_square_vision import seed as seed_mod
from app.modules.blindfold_square_vision.validator import (
    SLUG,
    bishop_distance,
    example_path,
    king_distance,
    knight_distance,
    min_moves,
    normalize_color,
    normalize_moves,
    normalize_piece,
    pawn_distance,
    queen_distance,
    rook_distance,
    validate,
)
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def answer_for(piece: str, color: str, origin: str, dest: str) -> dict:
    return {"piece": piece, "color": color, "from": origin, "to": dest}


def attempt(moves: object) -> dict:
    return {"moves": moves}


# --- King ---


def test_king_same_square():
    assert king_distance("e4", "e4") == 0


def test_king_adjacent():
    assert king_distance("e4", "e5") == 1
    assert king_distance("e4", "f5") == 1


def test_king_horizontal():
    assert king_distance("a1", "h1") == 7


def test_king_vertical():
    assert king_distance("e2", "e7") == 5


def test_king_diagonal():
    assert king_distance("a1", "h8") == 7


def test_king_large_distance():
    assert king_distance("a1", "h7") == 7
    assert king_distance("c3", "f6") == 3


# --- Rook ---


def test_rook_same_rank():
    assert rook_distance("a1", "h1") == 1


def test_rook_same_file():
    assert rook_distance("a1", "a8") == 1


def test_rook_different_rank_file():
    assert rook_distance("a1", "h8") == 2


def test_rook_same_square():
    assert rook_distance("d4", "d4") == 0


# --- Bishop ---


def test_bishop_same_diagonal():
    assert bishop_distance("c1", "h6") == 1


def test_bishop_same_color_unaligned():
    assert bishop_distance("a1", "d2") == 2


def test_bishop_same_color_two_moves():
    # Same color but off-diagonal squares always connect in exactly 2.
    assert bishop_distance("a1", "d2") == 2
    assert bishop_distance("c1", "b4") == 2


def test_bishop_opposite_color_unreachable():
    assert bishop_distance("a1", "h7") is None
    assert bishop_distance("a1", "a2") is None


def test_bishop_same_square():
    assert bishop_distance("e4", "e4") == 0


# --- Queen ---


def test_queen_same_rank():
    assert queen_distance("d4", "h4") == 1


def test_queen_same_file():
    assert queen_distance("d4", "d8") == 1


def test_queen_same_diagonal():
    assert queen_distance("d4", "h8") == 1


def test_queen_non_aligned():
    assert queen_distance("a1", "h7") == 2


def test_queen_same_square():
    assert queen_distance("e4", "e4") == 0


# --- Knight ---


def test_knight_same_square():
    assert knight_distance("e4", "e4") == 0


def test_knight_one_move():
    assert knight_distance("a1", "c2") == 1
    assert knight_distance("b5", "d6") == 1


def test_knight_two_moves():
    assert knight_distance("a1", "d4") == 2


def test_knight_three_moves():
    assert knight_distance("a1", "e6") == 3


def test_knight_longer_distance():
    assert knight_distance("a1", "h8") == 6


def test_knight_independent_bfs():
    # Independent BFS over knight jumps (not the validator helper).
    steps = ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2))

    def bfs(origin: str, dest: str) -> int:
        if origin == dest:
            return 0
        seen = {origin}
        queue: deque[tuple[str, int]] = deque([(origin, 0)])
        while queue:
            square, dist = queue.popleft()
            fx, fr = ord(square[0]) - 97, int(square[1]) - 1
            for dx, dy in steps:
                f, r = fx + dx, fr + dy
                if 0 <= f < 8 and 0 <= r < 8:
                    nxt = chr(97 + f) + str(r + 1)
                    if nxt == dest:
                        return dist + 1
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append((nxt, dist + 1))
        raise AssertionError("knights reach every square")

    for origin, dest in (("a1", "c2"), ("a1", "d4"), ("a1", "e6"), ("a1", "h8"), ("g1", "f3"), ("h8", "a1")):
        assert knight_distance(origin, dest) == bfs(origin, dest)


# --- Pawn ---


def test_pawn_forward_movement():
    assert pawn_distance("white", "e2", "e5") == 2
    assert pawn_distance("black", "e7", "e3") == 3


def test_pawn_wrong_direction():
    assert pawn_distance("white", "e5", "e2") is None
    assert pawn_distance("black", "e2", "e5") is None


def test_pawn_same_square():
    assert pawn_distance("white", "e4", "e4") == 0


def test_pawn_unreachable_sideways_backward():
    assert pawn_distance("white", "e4", "d5") is None
    assert pawn_distance("white", "e4", "e3") is None
    assert pawn_distance("black", "e4", "e5") is None


def test_pawn_white_vs_black_direction():
    assert pawn_distance("white", "e2", "e4") == 1
    assert pawn_distance("black", "e7", "e5") == 1
    assert pawn_distance("white", "e7", "e5") is None
    assert pawn_distance("black", "e2", "e4") is None


# --- Validation ---


def test_correct_answer():
    out = validate(answer_for("N", "white", "a1", "c2"), attempt(1))
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {
        "correct": ["1"],
        "missed": [],
        "wrong": [],
        "moves": 1,
        "path": ["a1", "c2"],
    }


def test_wrong_answer():
    out = validate(answer_for("N", "white", "a1", "c2"), attempt(2))
    assert out.result == AttemptResult.WRONG
    assert out.detail["moves"] == 1
    assert out.detail["wrong"] == ["2"]


def test_zero_answer():
    assert validate(answer_for("K", "white", "e4", "e4"), attempt(0)).result == AttemptResult.CORRECT
    assert validate(answer_for("K", "white", "e4", "e5"), attempt(0)).result == AttemptResult.WRONG


def test_negative_answer():
    assert validate(answer_for("K", "white", "e4", "e4"), attempt(-1)).result == AttemptResult.WRONG


def test_malformed_answer():
    answer = answer_for("K", "white", "e4", "e5")
    assert validate(answer, {}).result == AttemptResult.WRONG
    assert validate(answer, {"moves": "1"}).result == AttemptResult.WRONG
    assert validate(answer, {"moves": "3 moves"}).result == AttemptResult.WRONG
    assert validate(answer, {"moves": 1.0}).result == AttemptResult.WRONG
    assert validate(answer, {"moves": True}).result == AttemptResult.WRONG
    assert validate(answer, {"moves": None}).result == AttemptResult.WRONG
    assert validate(answer, None).result == AttemptResult.WRONG  # type: ignore[arg-type]
    assert validate({}, attempt(1)).result == AttemptResult.WRONG
    assert validate({"piece": "X", "color": "white", "from": "a1", "to": "c2"}, attempt(1)).result == AttemptResult.WRONG
    assert validate({"piece": "N", "color": "red", "from": "a1", "to": "c2"}, attempt(1)).result == AttemptResult.WRONG
    assert validate({"piece": "N", "color": "white", "from": "a9", "to": "c2"}, attempt(1)).result == AttemptResult.WRONG


def test_fake_correctness_flags_ignored():
    out = validate(answer_for("K", "white", "e4", "e5"), {"moves": 5, "result": "correct", "correct": True})
    assert out.result == AttemptResult.WRONG


def test_fake_distance_metadata_ignored():
    out = validate(answer_for("K", "white", "e4", "e5"), {"moves": 9, "moves_expected": 9, "distance": 9})
    assert out.result == AttemptResult.WRONG
    assert out.detail["moves"] == 1


def test_normalize_helpers():
    assert normalize_piece(" n ") == "N"
    assert normalize_piece("x") is None
    assert normalize_piece(5) is None
    from app.modules.blindfold_square_vision.validator import normalize_color, normalize_moves

    assert normalize_color(" White ") == "white"
    assert normalize_color("red") is None
    assert normalize_moves(0) == 0
    assert normalize_moves(-2) is None
    assert normalize_moves("2") is None
    assert normalize_moves(True) is None


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Seed correctness (INDEPENDENT recomputation) ---
# These tests never call min_moves/example_path/validate: every distance is
# re-derived with a separately written BFS over per-piece move rules.


def _independent_moves(piece: str, color: str, square: str) -> list[str]:
    fx, fr = ord(square[0]) - 97, int(square[1]) - 1

    def ray(steps: list[tuple[int, int]]) -> list[str]:
        out = []
        for dx, dy in steps:
            f, r = fx + dx, fr + dy
            while 0 <= f < 8 and 0 <= r < 8:
                out.append(chr(97 + f) + str(r + 1))
                f += dx
                r += dy
        return out

    orth = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    diag = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    if piece == "K":
        return [chr(97 + fx + dx) + str(fr + dy + 1) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx or dy) and 0 <= fx + dx < 8 and 0 <= fr + dy < 8]
    if piece == "Q":
        return ray(orth + diag)
    if piece == "R":
        return ray(orth)
    if piece == "B":
        return ray(diag)
    if piece == "N":
        return [
            chr(97 + fx + dx) + str(fr + dy + 1)
            for dx, dy in ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2))
            if 0 <= fx + dx < 8 and 0 <= fr + dy < 8
        ]
    step = 1 if color == "white" else -1
    start_rank = 1 if color == "white" else 6
    out = []
    if 0 <= fr + step < 8:
        out.append(chr(97 + fx) + str(fr + step + 1))
    if fr == start_rank and 0 <= fr + 2 * step < 8:
        out.append(chr(97 + fx) + str(fr + 2 * step + 1))
    return out


def _independent_distance(piece: str, color: str, origin: str, dest: str) -> int | None:
    if origin == dest:
        return 0
    seen = {origin}
    queue: deque[tuple[str, int]] = deque([(origin, 0)])
    while queue:
        square, dist = queue.popleft()
        for nxt in _independent_moves(piece, color, square):
            if nxt == dest:
                return dist + 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    return None


def test_seed_count_and_content(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    for puzzle in puzzles:
        assert puzzle.fen is None  # no board for this exercise
        assert set(puzzle.position_json) == {"piece", "color", "from", "to"}
        assert puzzle.answer_json == {
            "piece": puzzle.position_json["piece"],
            "color": puzzle.position_json["color"],
            "from": puzzle.position_json["from"],
            "to": puzzle.position_json["to"],
        }
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published


def test_seed_answers_match_independent_recomputation(db_session):
    seed_mod.seed_db(db_session)
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    by_piece: dict[str, int] = {}
    for puzzle in puzzles:
        task = puzzle.answer_json
        expected = _independent_distance(task["piece"], task["color"], task["from"], task["to"])
        assert expected is not None, puzzle.id
        assert validate(task, {"moves": expected}).result == AttemptResult.CORRECT
        assert validate(task, {"moves": expected + 1}).result == AttemptResult.WRONG
        by_piece[task["piece"]] = by_piece.get(task["piece"], 0) + 1
    assert by_piece == {"K": 3, "Q": 2, "R": 2, "B": 2, "N": 4, "P": 2}
    ratings = {p.initial_rating for p in puzzles}
    assert len(ratings) >= 5


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    )
    assert puzzle is not None
    return puzzle


def test_api_list_and_submit(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    assert "answer_json" not in body[0]
    task = body[0]["position_json"]
    assert set(task) == {"piece", "color", "from", "to"}

    expected = _independent_distance(task["piece"], task["color"], task["from"], task["to"])
    assert expected is not None
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"moves": expected}, "mode": "practice"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"moves": expected + 10}, "mode": "practice"},
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"moves": expected}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()
