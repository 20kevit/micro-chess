"""Pin: value-gated pin detection, ordered-triplet validation, seed, API."""

import chess

from app.modules.exercises import registry
from app.modules.pin import seed as seed_mod
from app.modules.pin.validator import SLUG, find_pins, validate
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers, publish_staged_puzzles


def answer_for(fen: str, pin: list) -> dict:
    return {"fen": fen, "pin": pin}


def attempt(squares: object) -> dict:
    return {"squares": squares}


def triplets(fen: str) -> set[tuple[str, str, str]]:
    return {(p["pinner"], p["pinned"], p["behind"]) for p in find_pins(fen)}


# --- Pin detection: absolute pins ---


def test_absolute_rook_pin():
    assert triplets("4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1") == {("e1", "e6", "e8")}
    assert find_pins("4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1")[0]["absolute"] is True


def test_absolute_bishop_pin():
    assert triplets("7k/6p1/8/8/8/8/1B6/4K3 w - - 0 1") == {("b2", "g7", "h8")}


def test_absolute_queen_pin():
    assert triplets("4k3/8/4b3/8/8/8/4Q3/4K3 w - - 0 1") == {("e2", "e6", "e8")}


def test_queen_pinned_to_king_is_absolute():
    pins = find_pins("2k5/8/8/8/2q5/8/8/2R1K3 w - - 0 1")
    assert [(p["pinner"], p["pinned"], p["behind"]) for p in pins] == [("c1", "c4", "c8")]
    assert pins[0]["absolute"] is True


def test_pawn_pinned_to_king_is_absolute():
    assert triplets("4k3/8/2p5/8/B7/8/8/4K3 w - - 0 1") == {("a4", "c6", "e8")}


def test_black_pinner_counts():
    assert triplets("4k3/8/8/8/1b6/2N5/8/4K3 w - - 0 1") == {("b4", "c3", "e1")}


# --- Pin detection: relative pins (behind strictly more valuable) ---


def test_relative_rook_pin_behind_queen():
    pins = find_pins("k3q3/8/4r3/8/8/8/8/4RK2 w - - 0 1")
    assert [(p["pinner"], p["pinned"], p["behind"]) for p in pins] == [("e1", "e6", "e8")]
    assert pins[0]["absolute"] is False


def test_relative_bishop_pin():
    assert triplets("k7/8/8/2q5/1n6/B7/8/4K3 w - - 0 1") == {("a3", "b4", "c5")}


def test_relative_rook_behind_rook():
    assert triplets("7k/8/r7/8/b7/8/8/R3K3 w - - 0 1") == {("a1", "a4", "a6")}


def test_relative_pin_behind_is_not_king():
    pins = find_pins("k7/7r/8/8/7n/8/8/4K2R w - - 0 1")
    assert len(pins) == 1
    assert pins[0]["absolute"] is False


# --- Skewer / non-pin rejection ---


def test_skewer_valuable_front_is_not_pin():
    # Queen in front of a rook looks aligned but is a skewer, not a pin.
    assert find_pins("k7/8/4r3/8/8/4q3/8/4RK2 w - - 0 1") == []


def test_equal_value_behind_is_not_pin():
    # Knight (3) in front of bishop (3): equal value, not a pin.
    assert find_pins("k7/8/8/2b5/1n6/B7/8/4K3 w - - 0 1") == []


def test_pawn_behind_is_never_relative_pin():
    # Nothing is less valuable than a pawn, so a pawn can never be the
    # rear piece of a relative pin: Ra4-Nc4(pe4) is rejected.
    assert find_pins("k7/8/8/8/R1n1p3/8/8/4K3 w - - 0 1") == []


def test_knight_pinner_is_not_pin():
    assert find_pins("4k3/8/8/1N6/8/8/8/4K3 w - - 0 1") == []


def test_king_cannot_be_pinned():
    # A king with a slider behind it is check, not a pin.
    assert find_pins("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1") == []


def test_empty_board_has_no_pins():
    assert find_pins("4k3/8/8/8/8/8/8/4K3 w - - 0 1") == []


# --- Validation: ordered triplet ---


def test_correct_triplet_in_order():
    out = validate(answer_for("4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1", ["e1", "e6", "e8"]), attempt(["e1", "e6", "e8"]))
    assert out.result == AttemptResult.CORRECT
    assert out.detail == {"correct": ["e1", "e6", "e8"], "missed": [], "wrong": []}


def test_reversed_triplet_is_wrong():
    out = validate(answer_for("4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1", ["e1", "e6", "e8"]), attempt(["e8", "e6", "e1"]))
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["e1", "e6", "e8"]


def test_rotated_triplet_is_wrong():
    out = validate(answer_for("4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1", ["e1", "e6", "e8"]), attempt(["e6", "e8", "e1"]))
    assert out.result == AttemptResult.WRONG


def test_skewer_order_is_wrong():
    # Valuable piece first is the skewer reading of the same line.
    out = validate(answer_for("k3q3/8/4r3/8/8/8/8/4RK2 w - - 0 1", ["e1", "e6", "e8"]), attempt(["e8", "e6", "e1"]))
    assert out.result == AttemptResult.WRONG


def test_wrong_squares_are_wrong():
    out = validate(answer_for("4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1", ["e1", "e6", "e8"]), attempt(["e1", "e6", "e7"]))
    assert out.result == AttemptResult.WRONG


def test_legacy_selected_squares_key_accepted():
    out = validate(
        answer_for("4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1", ["e1", "e6", "e8"]),
        {"selected_squares": ["e1", "e6", "e8"]},
    )
    assert out.result == AttemptResult.CORRECT


def test_stored_pin_is_not_trusted():
    # Correctness is recomputed from the FEN; a lying stored pin changes nothing.
    out = validate(answer_for("4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1", ["a1", "a2", "a3"]), attempt(["e1", "e6", "e8"]))
    assert out.result == AttemptResult.CORRECT
    bad = validate(answer_for("4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1", ["a1", "a2", "a3"]), attempt(["a1", "a2", "a3"]))
    assert bad.result == AttemptResult.WRONG


# --- Validation: malformed input never crashes ---


def test_malformed_answers_are_safe_wrong():
    fen = "4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1"
    assert validate(answer_for(fen, ["e1", "e6", "e8"]), {}).result == AttemptResult.WRONG
    assert validate(answer_for(fen, ["e1", "e6", "e8"]), {"squares": []}).result == AttemptResult.WRONG
    assert validate(answer_for(fen, ["e1", "e6", "e8"]), attempt(["e1", "e6"])).result == AttemptResult.WRONG
    assert validate(answer_for(fen, ["e1", "e6", "e8"]), attempt(["e1", "e6", "e8", "a1"])).result == AttemptResult.WRONG
    assert validate(answer_for(fen, ["e1", "e6", "e8"]), attempt(["e1", "e6", "e9"])).result == AttemptResult.WRONG
    assert validate(answer_for(fen, ["e1", "e6", "e8"]), attempt(["e1", "e1", "e1"])).result == AttemptResult.WRONG
    assert validate(answer_for(fen, ["e1", "e6", "e8"]), attempt([42, None, "e8"])).result == AttemptResult.WRONG
    assert validate(answer_for(fen, ["e1", "e6", "e8"]), attempt("e1e6e8")).result == AttemptResult.WRONG
    assert validate(answer_for("not a fen!!", ["e1", "e6", "e8"]), attempt(["e1", "e6", "e8"])).result == (
        AttemptResult.WRONG
    )
    assert validate({}, attempt(["e1", "e6", "e8"])).result == AttemptResult.WRONG
    assert validate(None, attempt(["e1", "e6", "e8"])).result == AttemptResult.WRONG  # type: ignore[arg-type]
    assert validate(answer_for(fen, ["e1", "e6", "e8"]), None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_old_move_shape_is_wrong():
    # The move-finding contract is gone; from/to payloads answer nothing.
    out = validate(
        answer_for("4k3/8/4n3/8/8/8/8/4RK2 w - - 0 1", ["e1", "e6", "e8"]),
        {"from": "a1", "to": "e1"},
    )
    assert out.result == AttemptResult.WRONG


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None


# --- Seed correctness (INDEPENDENT recomputation) ---
# These tests never call find_pins: they regenerate pins with a
# separately written slider-perspective scan with the same value gate.


def _independent_pins(fen: str) -> set[tuple[str, str, str]]:
    board = chess.Board(fen)
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    rays = {
        chess.ROOK: [(1, 0), (-1, 0), (0, 1), (0, -1)],
        chess.BISHOP: [(1, 1), (1, -1), (-1, 1), (-1, -1)],
        chess.QUEEN: [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)],
    }
    found = set()
    for slider_sq in chess.SQUARES:
        slider = board.piece_at(slider_sq)
        if slider is None or slider.piece_type not in rays:
            continue
        fx, rk = chess.square_file(slider_sq), chess.square_rank(slider_sq)
        for dx, dy in rays[slider.piece_type]:
            met = []
            f, r = fx + dx, rk + dy
            while 0 <= f < 8 and 0 <= r < 8:
                occ = chess.square(f, r)
                if board.piece_at(occ) is not None:
                    met.append(occ)
                    if len(met) == 2:
                        break
                f += dx
                r += dy
            if len(met) == 2:
                middle, behind = met
                mid_piece = board.piece_at(middle)
                behind_piece = board.piece_at(behind)
                if mid_piece is None or behind_piece is None:
                    continue
                if mid_piece.piece_type == chess.KING:
                    continue
                if mid_piece.color == slider.color or behind_piece.color == slider.color:
                    continue
                if behind_piece.piece_type == chess.KING or values[behind_piece.piece_type] > values[
                    mid_piece.piece_type
                ]:
                    found.add((chess.square_name(slider_sq), chess.square_name(middle), chess.square_name(behind)))
    return found


def test_seed_count_and_answer_match(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    seen_fens = set()
    for puzzle in puzzles:
        assert puzzle.fen
        assert puzzle.position_json == {"fen": puzzle.fen, "mode": "standard"}
        stored = puzzle.answer_json["pin"]
        assert _independent_pins(puzzle.fen) == {(stored[0], stored[1], stored[2])}, puzzle.fen
        # ...and the validator accepts exactly that ordered triplet:
        out = validate(puzzle.answer_json, {"squares": list(stored)})
        assert out.result == AttemptResult.CORRECT, puzzle.fen
        swapped = validate(puzzle.answer_json, {"squares": [stored[2], stored[1], stored[0]]})
        assert swapped.result == AttemptResult.WRONG, puzzle.fen
        seen_fens.add(puzzle.fen)
        assert puzzle.prompt_fa and puzzle.explanation
        assert not puzzle.is_published and puzzle.status == "validated"
    assert len(seen_fens) == 15
    assert len({p.initial_rating for p in puzzles}) >= 5


def test_seed_archives_legacy_move_rows(db_session):
    from app.modules.exercises.models import Exercise

    db_session.add(
        Exercise(slug=SLUG, title_fa="آچمز", title_en="Pin", description="legacy", is_active=True, sort_order=10)
    )
    legacy = Puzzle(
        exercise_slug=SLUG,
        fen="4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1",
        position_json={"fen": "4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1", "mode": "standard"},
        answer_json={"fen": "4k3/8/4n3/8/8/8/8/R4K2 w - - 0 1", "example": {"from": "a1", "to": "e1"}},
        hint_json={"hints": []},
        prompt_fa="legacy",
        explanation="legacy",
        initial_rating=800.0,
        is_published=True,
        is_archived=False,
    )
    db_session.add(legacy)
    db_session.commit()

    assert seed_mod.seed_db(db_session) == 15
    db_session.refresh(legacy)
    assert legacy.is_archived is True
    visible = (
        db_session.query(Puzzle)
        .filter(
            Puzzle.exercise_slug == SLUG,
            Puzzle.status == "validated",
            Puzzle.is_archived == False,  # noqa: E712
        )
        .all()
    )
    assert len(visible) == 15
    assert all("pin" in p.answer_json for p in visible)


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    seed_mod.seed_db(db_session)
    publish_staged_puzzles(db_session, SLUG)
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    assert puzzle is not None
    return puzzle


def test_api_list_and_submit(client, db_session):
    puzzle = _seeded(db_session)
    headers = make_auth_headers(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 15
    assert "answer_json" not in body[0]

    pin = puzzle.answer_json["pin"]
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"squares": pin}, "mode": "practice"},
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 1.0
    assert ok.json()["detail"]["correct"] == pin

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"squares": [pin[2], pin[1], pin[0]]}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"squares": ["e1", "e2", "e3"]}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_puzzle_detail_hides_answer(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles/{puzzle.id}")
    assert res.status_code == 200
    assert "answer_json" not in res.json()


def test_missing_puzzle_returns_404(client, db_session):
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": 999999, "answer": {"squares": ["e1", "e6", "e8"]}, "mode": "practice"},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 404
