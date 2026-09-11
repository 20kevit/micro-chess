"""Trapped Pieces: SEE-based detection, validation, scoring, seed, API."""

import chess
import pytest

from app.modules.exercises import registry
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult, ValidationResult
from app.modules.trapped_pieces import generator as gen_mod
from app.modules.trapped_pieces import seed as seed_mod
from app.modules.trapped_pieces.detector import (
    either_king_in_check,
    is_safe_destination,
    static_exchange,
    trapped_squares,
)
from app.modules.trapped_pieces.scoring import score_squares
from app.modules.trapped_pieces.validator import SLUG, validate


def trapped(fen: str) -> set[str]:
    return set(trapped_squares(fen))


# --- Basic trapped cases (blocked, zero legal moves) ---


def test_knight_corner_trapped():
    assert trapped("4k3/8/8/8/8/1P6/2P5/N5K1 w - - 0 1") == {"a1"}


def test_bishop_trapped_by_own_pawns():
    assert trapped("2b1k3/1p1p4/8/8/8/8/8/4K3 w - - 0 1") == {"c8"}


def test_rook_corner_trapped():
    assert trapped("4k3/8/8/8/8/8/P7/RN4K1 w - - 0 1") == {"a1"}


def test_queen_trapped():
    assert trapped("4k3/8/8/8/8/8/2PPP3/2BQK3 w - - 0 1") == {"d1"}


def test_double_trapped():
    assert trapped("2bqk3/1pppp3/8/8/8/8/8/4K3 w - - 0 1") == {"c8", "d8"}


def test_not_currently_attacked_can_be_trapped():
    # Nobody attacks c8: the bishop is still trapped because every
    # diagonal is blocked by its own pawns.
    fen = "2b1k3/1p1p4/8/8/8/8/8/4K3 w - - 0 1"
    board = chess.Board(fen)
    assert not list(board.attackers(chess.WHITE, chess.C8))
    assert not list(board.attackers(chess.BLACK, chess.C8))
    assert trapped(fen) == {"c8"}


# --- Safe-square evaluation (the core of the exercise) ---


def test_attacked_but_favorable_recapture_is_safe():
    # Rb1-b5 lands under Qd5, but Pc4 recaptures the queen: net +4.
    fen = "4k3/8/8/3q4/2P5/8/8/1R2K3 w - - 0 1"
    assert is_safe_destination(fen, chess.B1, chess.Move.from_uci("b1b5")) is True
    # ...and the rook is therefore NOT trapped (it also has other moves).
    assert "b1" not in trapped(fen)


def test_attacked_losing_exchange_is_unsafe():
    # Rxd5 wins a pawn but Be6 recaptures for free: net -5.
    fen = "4k3/8/4b3/3p4/8/8/3R4/4K3 w - - 0 1"
    assert is_safe_destination(fen, chess.D2, chess.Move.from_uci("d2d5")) is False


def test_see_equal_exchange_is_acceptable():
    # Knight takes knight, pawn recaptures: -3 + 3 = 0, still safe.
    board = chess.Board("4k3/8/8/3n4/2P5/8/8/4K3 w - - 0 1")
    board.push(chess.Move.from_uci("c4d5"))
    assert static_exchange(board, chess.D5, chess.WHITE) == 0


def test_see_undefended_capture_is_loss():
    board = chess.Board("4k3/8/8/8/8/8/3R4/4K3 w - - 0 1")
    board.push(chess.Move.from_uci("d2d4"))
    # Nothing attacks d4: no exchange, net 0.
    assert static_exchange(board, chess.D4, chess.WHITE) == 0


def test_piece_with_safe_escape_not_trapped():
    # Knight h1 captures g3, so nothing is trapped.
    assert trapped("4k3/8/8/8/8/6p1/5PK1/7N w - - 0 1") == set()


# --- Kings and pawns ---


def test_king_with_no_legal_move_is_trapped():
    # Kings ARE candidates: g1 has no legal move (all boxed by own men).
    assert trapped("4k3/8/8/8/8/8/5PPP/5RKR w - - 0 1") == {"g1", "h1"}


def test_king_with_escape_not_trapped():
    assert "g1" not in trapped("4k3/8/8/8/8/8/6PP/6KR w - - 0 1")


def test_pawns_never_trapped():
    # Mutually blocked pawns have no moves but are excluded by definition.
    assert trapped("4k3/8/8/8/4p3/4P3/8/4K3 w - - 0 1") == set()
    assert trapped("4k3/8/8/8/3p4/3P4/8/4K3 w - - 0 1") == set()


def test_pinned_piece_with_no_legal_move_is_trapped():
    # Legal-move based (not pseudo-legal): Ne2 is absolutely pinned by
    # Re8 and has zero legal moves, so it IS trapped.
    assert trapped("4rk2/8/8/8/8/8/4N3/4K3 w - - 0 1") == {"e2"}


def test_multiple_trapped_pieces_returned():
    assert trapped("2b1k3/1p1p4/8/8/8/8/P7/RN4K1 w - - 0 1") == {"a1", "c8"}


def test_answer_ordering_does_not_matter():
    assert trapped_squares("2b1k3/1p1p4/8/8/8/8/P7/RN4K1 w - - 0 1") == ["a1", "c8"]


def test_invalid_fen_raises():
    with pytest.raises(ValueError):
        trapped_squares("not-a-fen")


def test_either_king_in_check():
    assert either_king_in_check("4k3/8/8/8/8/8/5PPP/5RKR w - - 0 1") is False
    assert either_king_in_check("4k3/8/8/8/8/8/5pq1/5RKR b - - 0 1") is True


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None
    assert registry.get_scorer(SLUG) is not None


# --- Validation ---


def test_validate_correct_partial_wrong():
    answer = {"squares": ["a1", "c8"]}
    assert validate(answer, {"selected_squares": ["a1", "c8"]}).result == AttemptResult.CORRECT
    assert validate(answer, {"selected_squares": ["c8", "a1"]}).result == AttemptResult.CORRECT
    partial = validate(answer, {"selected_squares": ["a1", "h1"]})
    assert partial.result == AttemptResult.PARTIAL
    assert partial.detail == {"correct": ["a1"], "missed": ["c8"], "wrong": ["h1"]}
    assert validate(answer, {"selected_squares": ["h1"]}).result == AttemptResult.WRONG
    assert validate(answer, {"selected_squares": []}).result == AttemptResult.WRONG
    malformed = validate(answer, {"selected_squares": ["a1", "c8", "zzz"]})
    assert malformed.result == AttemptResult.PARTIAL
    assert "zzz" in malformed.detail["wrong"]


def test_validate_missed_only_is_wrong_without_correct():
    # Selecting nothing when two are trapped: no correct pick -> WRONG,
    # but both are reported missed for the -2-each penalty.
    out = validate({"squares": ["e4", "g7"]}, {"selected_squares": []})
    assert out.result == AttemptResult.WRONG
    assert out.detail == {"correct": [], "missed": ["e4", "g7"], "wrong": []}


def test_validate_empty_answer():
    answer = {"squares": []}
    assert validate(answer, {"selected_squares": []}).result == AttemptResult.CORRECT
    assert validate(answer, {"selected_squares": ["a1"]}).result == AttemptResult.WRONG
    assert validate(answer, {"selected_squares": ["zzz"]}).result == AttemptResult.WRONG


def test_validate_ignores_client_answer_and_fen():
    answer = {"squares": ["a1"]}
    assert validate(answer, {"selected_squares": ["A1"]}).result == AttemptResult.CORRECT
    out = validate(answer, {"selected_squares": ["h1"], "squares": ["h1"], "fen": "8/8/8/8/8/8/8/4K3 w - - 0 1"})
    assert out.result == AttemptResult.WRONG
    assert out.detail["missed"] == ["a1"]


# --- Scoring (+5 correct / -2 missed / -2 wrong) ---


def _validation(correct: list[str], missed: list[str], wrong: list[str], result: AttemptResult) -> ValidationResult:
    return ValidationResult(result=result, message_key="", detail={"correct": correct, "missed": missed, "wrong": wrong})


def test_scoring_exact_match_single():
    assert score_squares(_validation(["e4"], [], [], AttemptResult.CORRECT)) == 5.0


def test_scoring_exact_match_multi():
    assert score_squares(_validation(["e4", "g7"], [], [], AttemptResult.CORRECT)) == 10.0


def test_scoring_partial_missed():
    # e4 correct (+5), g7 missed (-2) -> +3.
    assert score_squares(_validation(["e4"], ["g7"], [], AttemptResult.PARTIAL)) == 3.0


def test_scoring_partial_wrong_and_missed():
    # e4 correct (+5), h5 wrong (-2), g7 missed (-2) -> +1.
    assert score_squares(_validation(["e4"], ["g7"], ["h5"], AttemptResult.PARTIAL)) == 1.0


def test_scoring_wrong_single_speed_shape():
    # Speed wrong tap: nothing correct, one wrong, one missed -> -4.
    assert score_squares(_validation([], ["e4"], ["h5"], AttemptResult.WRONG)) == -4.0


def test_scoring_zero_target_bonus():
    assert score_squares(_validation([], [], [], AttemptResult.CORRECT)) == 5.0


def test_score_goes_through_registry():
    validation = validate({"squares": ["a1", "c8"]}, {"selected_squares": ["a1", "h1"]})
    assert registry.score_for_answer(SLUG, validation) == 1.0


# --- Generator ---


def test_question_for_fen_rejects_empty_and_degenerate():
    with pytest.raises(ValueError):
        gen_mod.question_for_fen("4k3/8/8/8/4P3/8/4P3/4K3 w - - 0 1")
    with pytest.raises(ValueError):
        gen_mod.question_for_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    with pytest.raises(ValueError):
        gen_mod.question_for_fen("r1bqkbnr/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")


def test_question_for_fen_exactly_one():
    data = gen_mod.question_for_fen("4k3/8/8/8/8/1P6/2P5/N5K1 w - - 0 1", exactly_one=True)
    assert data["squares"] == ["a1"]
    with pytest.raises(ValueError):
        gen_mod.question_for_fen("2bqk3/1pppp3/8/8/8/8/8/4K3 w - - 0 1", exactly_one=True)


def test_curated_fens_all_valid():
    for fen in gen_mod.CURATED_FENS:
        data = gen_mod.question_for_fen(fen)
        assert 1 <= len(data["squares"]) <= 3


def test_generate_from_real_source():
    import random

    data = gen_mod.generate_question_data(random.Random(42))
    assert 1 <= len(data["squares"]) <= 3
    assert data["squares"] == trapped_squares(data["fen"])
    single = gen_mod.generate_question_data(random.Random(42), exactly_one=True)
    assert len(single["squares"]) == 1


# --- Seed correctness ---


def test_seed_count_and_answer_match(db_session):
    import random

    assert seed_mod.seed_db(db_session, random.Random(18)) >= 24
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) >= 24
    kinds = set()
    multi_count = 0
    single_count = 0
    for puzzle in puzzles:
        assert puzzle.fen
        expected = trapped_squares(puzzle.fen)
        assert puzzle.answer_json["squares"] == expected
        assert 1 <= len(expected) <= 3
        if len(expected) > 1:
            multi_count += 1
        else:
            single_count += 1
        for sq in expected:
            kinds.add(chess.Board(puzzle.fen).piece_at(chess.parse_square(sq)).symbol().lower())
        assert puzzle.prompt_fa and puzzle.explanation and puzzle.is_published
        assert puzzle.position_json["mode"] == "standard"
    assert "p" not in kinds  # pawns never answers
    assert multi_count >= 1
    assert single_count >= 1  # speed pool exists


def test_seed_archives_stale_and_empty_legacy_rows(db_session):
    """Pre-SEE rows (pawn answers, zero-target rows) are archived, never deleted."""
    import random

    from app.modules.exercises.models import Exercise

    db_session.add(
        Exercise(
            slug=SLUG,
            title_fa="مهره‌ی گرفتار",
            title_en="Trapped Piece",
            description="x",
            is_active=True,
            sort_order=17,
        )
    )
    stale_pawn = Puzzle(
        exercise_slug=SLUG,
        fen="4k3/8/8/8/4p3/4P3/8/4K3 w - - 0 1",
        position_json={"fen": "4k3/8/8/8/4p3/4P3/8/4K3 w - - 0 1", "mode": "standard"},
        answer_json={"squares": ["e3", "e4"]},
        hint_json={"hints": []},
        prompt_fa="x",
        explanation="x",
        is_published=True,
        is_archived=False,
    )
    stale_empty = Puzzle(
        exercise_slug=SLUG,
        fen="4k3/8/8/8/4P3/8/4P3/4K3 w - - 0 1",
        position_json={"fen": "4k3/8/8/8/4P3/8/4P3/4K3 w - - 0 1", "mode": "standard"},
        answer_json={"squares": []},
        hint_json={"hints": []},
        prompt_fa="x",
        explanation="x",
        is_published=True,
        is_archived=False,
    )
    db_session.add_all([stale_pawn, stale_empty])
    db_session.commit()

    created = seed_mod.seed_db(db_session, random.Random(18))
    assert created >= 30  # full fresh pool on top of the archived rows
    db_session.refresh(stale_pawn)
    db_session.refresh(stale_empty)
    assert stale_pawn.is_archived is True
    assert stale_empty.is_archived is True
    live = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG, Puzzle.is_archived == False).all()  # noqa: E712
    assert all(1 <= len(p.answer_json["squares"]) <= 3 for p in live)
    assert seed_mod.seed_db(db_session, random.Random(18)) == 0


# --- API flow ---


def _seeded(db_session) -> Puzzle:
    import random

    seed_mod.seed_db(db_session, random.Random(18))
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    assert puzzle is not None
    return puzzle


def test_api_list_and_submit(client, db_session):
    puzzle = _seeded(db_session)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    body = res.json()
    assert len(body) >= 24
    assert "answer_json" not in body[0]
    assert body[0]["position_json"]["mode"] == "standard"

    ok = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": puzzle.id,
            "answer": {"selected_squares": puzzle.answer_json["squares"]},
            "mode": "practice",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == 5.0 * len(puzzle.answer_json["squares"])

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": ["h1"]}, "mode": "practice"},
    )
    assert bad.json()["result"] in ("wrong", "partial")
    assert bad.json()["score"] < 0

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"selected_squares": []}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_next_practice_and_speed_flow(client, db_session):
    import random

    seed_mod.seed_db(db_session, random.Random(18))
    nxt = client.post("/api/v1/trapped-pieces/next", json={"exclude_ids": []})
    assert nxt.status_code == 200
    assert "answer_json" not in nxt.json()
    assert nxt.json()["fen"]

    created = client.post("/api/v1/trapped-pieces/sessions", json={})
    assert created.status_code == 200
    sid = created.json()["session_id"]
    prep = client.post(f"/api/v1/trapped-pieces/sessions/{sid}/puzzles", json={"count": 20})
    assert prep.status_code == 200
    assert len(prep.json()) == 20
    # Every buffered speed puzzle holds exactly one trapped piece.
    for row in prep.json():
        puzzle = db_session.get(Puzzle, row["id"])
        assert puzzle is not None
        assert len(puzzle.answer_json["squares"]) == 1
    start = client.post(f"/api/v1/trapped-pieces/sessions/{sid}/start")
    assert start.status_code == 200
    first_id = prep.json()[0]["id"]
    first = db_session.get(Puzzle, first_id)
    assert first is not None
    sub = client.post(
        f"/api/v1/trapped-pieces/sessions/{sid}/submit",
        json={"puzzle_id": first_id, "answer": {"selected_squares": first.answer_json["squares"]}},
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["result"] == "correct"
    assert sub.json()["attempt"]["score"] == 5.0
    rep = client.get(f"/api/v1/trapped-pieces/sessions/{sid}/report")
    assert rep.status_code == 200
    assert rep.json()["session"]["attempted"] == 1
