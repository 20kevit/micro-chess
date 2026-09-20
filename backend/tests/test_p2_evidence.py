"""P2 — Mistake Taxonomy + Evidence Engine.

Service-level tests (no HTTP harness) over real exercise validators:

* Evidence persistence: positive/negative/neutral rows, Attempt link,
  source/context/observed_at, validation_detail snapshot, legacy rows.
* Mistake classification: all 8 core keys where live-observable, plus
  every exercise-specific family the validators can generate (with
  explicit no-classification proofs for piece-recognition /
  legal-destinations specificity and invalid-puzzle content).
* Skill mapping: canonical primary/secondary skills + link qualifiers,
  no-skill rows for no-response, originating-skill malformed rows.
* Idempotency, transaction atomicity, repeat detection bounds.
* Context: practice/rated/speed mode handling; rating untouched.
* Migration v13: fresh stamp + legacy upgrade without backfill.
"""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.migration import (
    SCHEMA_VERSION,
    _migrate_v13_p2,
    ensure_schema,
    get_schema_version,
    import_models,
)
from app.modules.evidence import classify, service as evidence_service
from app.modules.evidence import taxonomy as tx
from app.modules.evidence.models import Evidence
from app.modules.progress import service as attempt_service
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import STATUS_PUBLISHED, Puzzle
from app.modules.rating_engine import service as rating_service
from app.modules.rule_engine.base import AttemptMode

# Real validators for every implemented exercise (registration happens
# on package import; the classifier dispatches through the same slugs).
import app.modules.balance_scale  # noqa: F401
import app.modules.blindfold_calculation  # noqa: F401
import app.modules.blindfold_square_vision  # noqa: F401
import app.modules.captures  # noqa: F401
import app.modules.castling_rights  # noqa: F401
import app.modules.checkmate  # noqa: F401
import app.modules.chinese_board  # noqa: F401
import app.modules.get_out_of_check  # noqa: F401
import app.modules.give_check  # noqa: F401
import app.modules.legal_destinations  # noqa: F401
import app.modules.material_comparison  # noqa: F401
import app.modules.opening_traps  # noqa: F401
import app.modules.pathfinding  # noqa: F401
import app.modules.pathfinding_obstacles  # noqa: F401
import app.modules.piece_recognition  # noqa: F401
import app.modules.pin  # noqa: F401
import app.modules.reverse_opening  # noqa: F401
import app.modules.trapped_pieces  # noqa: F401
import app.modules.undefended_pieces  # noqa: F401


def make_db():
    import_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def make_puzzle(db, slug, answer, **overrides):
    fields = {
        "exercise_slug": slug,
        "fen": None,
        "position_json": {},
        "answer_json": answer,
        "hint_json": {},
        "is_published": True,
        "is_archived": False,
        "status": STATUS_PUBLISHED,
        "source": "manual",
        "difficulty": 3,
        "target_rating": 1400.0,
        "initial_rating": 1450.0,
    }
    fields.update(overrides)
    puzzle = Puzzle(**fields)
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle


def submit(db, puzzle, answer, **kwargs):
    kwargs.setdefault("user_id", 1)
    kwargs.setdefault("mode", AttemptMode.PRACTICE)
    return attempt_service.submit_attempt(
        db, puzzle_id=puzzle.id, answer=answer, **kwargs
    )


def evidence_for(db, attempt):
    return (
        db.query(Evidence)
        .filter(Evidence.attempt_id == attempt.id)
        .order_by(Evidence.id)
        .all()
    )


def keys(rows):
    return [r.evidence_key for r in rows]


# --- evidence persistence -----------------------------------------------------


def test_correct_attempt_produces_positive_evidence():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt, _, detail = submit(db, puzzle, {"selected_squares": ["d5"]})
    assert attempt.result == "correct"
    # Validator detail is now persisted write-once on the attempt.
    assert attempt.validation_detail == detail
    assert detail["missed"] == [] and detail["wrong"] == []
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    row = rows[0]
    assert row.direction == "positive"
    assert row.mistake_core is None and row.mistake_specific is None
    assert row.skill_key == "capture-finding" and row.skill_role == "primary"
    assert row.strength == "direct" and row.confidence == "high"
    assert row.source == "attempt"
    assert row.attempt_id == attempt.id
    assert row.observed_at == attempt.created_at
    assert row.context_json["mode"] == "practice"
    assert row.context_json["result"] == "correct"
    assert row.context_json["has_hints"] is False
    db.close()


def test_partial_attempt_decomposes_into_two_mistakes():
    # PARTIAL is an outcome, not a mistake: it yields omission + commission.
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5", "f5"], "from": "e4"})
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["d5", "e4"]})
    assert attempt.result == "partial"
    rows = evidence_for(db, attempt)
    by_key = {r.evidence_key: r for r in rows}
    assert "neg:missed-target:missed-capture:primary:capture-finding" in by_key
    assert "neg:wrong-target:phantom-capture:primary:capture-finding" in by_key
    # No positive row for a partial demonstration.
    assert not [r for r in rows if r.direction == "positive"]
    missed = by_key["neg:missed-target:missed-capture:primary:capture-finding"]
    assert missed.context_json["missed"] == ["f5"]
    phantom = by_key["neg:wrong-target:phantom-capture:primary:capture-finding"]
    assert phantom.context_json["wrong"] == ["e4"]
    db.close()


def test_commission_fans_out_strong_secondary():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    # All-selected squares hallucinated, target missed: both primaries fire.
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["e4"]})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    secondaries = [r for r in rows if r.skill_role == "secondary"]
    assert len(secondaries) == 1
    sec = secondaries[0]
    assert sec.skill_key == "legal-destinations"
    assert sec.mistake_specific == "phantom-capture"
    assert sec.direction == "negative"
    assert sec.context_json["skill_link"] == "strong"
    # Omission rows never implicate the enumeration sub-skill.
    assert not [r for r in secondaries if r.mistake_specific == "missed-capture"]
    db.close()


def test_empty_move_list_is_no_response_not_omission():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "give-check", {"moves": ["e5e8"]})
    attempt, _, _ = submit(db, puzzle, {"moves": []})
    # Empty move list against a non-empty target: effort signal, not omission.
    rows = evidence_for(db, attempt)
    assert len(rows) == 1 and rows[0].mistake_core == "no-response"
    db.close()


def test_piece_recognition_has_no_specific_keys():
    # Color-vs-kind mechanism is unobservable: core C1/C2 is the ceiling.
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "piece-recognition", {"squares": ["a2", "c4"]})
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["a2", "e5"]})
    assert attempt.result == "partial"
    rows = evidence_for(db, attempt)
    assert rows
    for row in rows:
        assert row.mistake_specific is None
        assert row.mistake_core in ("missed-target", "wrong-target")
        assert row.skill_key == "piece-identification"
    db.close()


def test_legal_destinations_has_no_specific_keys():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "legal-destinations", {"squares": ["e6"], "from": "d4"})
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["f5"]})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    assert rows
    for row in rows:
        assert row.mistake_specific is None
        assert row.skill_key == "legal-destinations"
    db.close()


def test_malformed_input_is_neutral_with_originating_skill():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["zzz", 42]})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    row = rows[0]
    assert row.mistake_core == "malformed-input"
    assert row.direction == "neutral"
    assert row.strength == "weak" and row.confidence == "high"
    assert row.skill_key == "capture-finding" and row.skill_role == "primary"
    db.close()


def test_empty_submission_is_no_response_without_skill():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt, _, _ = submit(db, puzzle, {"selected_squares": []})
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    row = rows[0]
    assert row.mistake_core == "no-response"
    assert row.direction == "neutral"
    assert row.skill_key is None and row.skill_role == "none"
    db.close()


def test_terminal_results_are_no_response():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    for terminal in ("timeout", "skipped", "abandoned"):
        attempt, _, detail = submit(db, puzzle, {}, client_result=terminal)
        assert attempt.result == terminal
        assert attempt.validation_detail == detail
        rows = evidence_for(db, attempt)
        assert len(rows) == 1
        assert rows[0].mistake_core == "no-response"
        assert rows[0].direction == "neutral"
        assert rows[0].skill_key is None
    db.close()


def test_correct_with_hints_is_downgraded_positive():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt, _, _ = submit(
        db, puzzle, {"selected_squares": ["d5"]}, hints_used=["reveal-one"]
    )
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    row = rows[0]
    assert row.direction == "positive"
    assert row.strength == "weak"  # scaffolded, not independent
    assert row.context_json["has_hints"] is True
    assert row.context_json["hints_count"] == 1
    db.close()


def test_legacy_attempts_stay_valid_without_evidence():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    legacy = Attempt(
        user_id=7,
        guest_session_id=None,
        puzzle_id=puzzle.id,
        exercise_slug="captures",
        mode="practice",
        result="wrong",
        answer_json={"selected_squares": ["e4"]},
        score=0.0,
    )
    db.add(legacy)
    db.commit()
    db.refresh(legacy)
    assert legacy.validation_detail is None
    assert evidence_for(db, legacy) == []
    # No backfill: historical rows gain no evidence, new submits work.
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["d5"]}, user_id=7)
    assert len(evidence_for(db, attempt)) == 1
    assert evidence_for(db, legacy) == []
    db.close()


# --- single-choice / confusion-pair exercises ---------------------------------


def test_heavier_side_wrong_choice_with_pair():
    Session = make_db()
    db = Session()
    # White up one pawn (black e-pawn missing): expected "white".
    fen = "rnbqkbnr/pppp1ppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
    puzzle = make_puzzle(db, "heavier-side", {"fen": fen})
    attempt, _, _ = submit(db, puzzle, {"choice": "black"})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    row = rows[0]
    assert (row.mistake_core, row.mistake_specific) == ("wrong-choice", "miscount-direction")
    assert row.skill_key == "material-comparison"
    assert row.direction == "negative" and row.strength == "direct"
    assert row.context_json["expected"] == "white"
    assert row.context_json["submitted"] == "black"
    db.close()


def test_heavier_side_malformed_choice():
    Session = make_db()
    db = Session()
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
    puzzle = make_puzzle(db, "heavier-side", {"fen": fen})
    attempt, _, _ = submit(db, puzzle, {"choice": "left"})
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    assert rows[0].mistake_core == "malformed-input"
    assert rows[0].direction == "neutral"
    db.close()


def test_checkmate_escape_blindness():
    Session = make_db()
    db = Session()
    # White in check with exactly one escape: claiming mate is escape-blindness.
    puzzle = make_puzzle(db, "is-checkmate", {"fen": "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"})
    attempt, _, _ = submit(db, puzzle, {"choice": "checkmate"})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    row = rows[0]
    assert (row.mistake_core, row.mistake_specific) == ("wrong-choice", "escape-blindness")
    assert row.skill_key == "mate-classification"
    assert row.confidence == "high"
    db.close()


def test_checkmate_stalemate_blindness_is_medium():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "is-checkmate", {"fen": "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"})
    attempt, _, _ = submit(db, puzzle, {"choice": "checkmate"})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    row = rows[0]
    assert (row.mistake_core, row.mistake_specific) == ("wrong-choice", "stalemate-blindness")
    assert row.confidence == "medium"  # post-hoc FEN derivation
    assert row.strength == "strong"  # capped precise diagnosis
    db.close()


def test_checkmate_unlisted_pair_is_core_only():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "is-checkmate", {"fen": "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"})
    # Missing that the side is in check: no named confusion pair.
    attempt, _, _ = submit(db, puzzle, {"choice": "not_check"})
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    assert rows[0].mistake_core == "wrong-choice"
    assert rows[0].mistake_specific is None
    db.close()


def test_pin_role_swap_vs_non_pin():
    Session = make_db()
    db = Session()
    answer = {"fen": "4k3/4r3/8/8/8/8/4N3/4K3 w - - 0 1", "pin": ["e7", "e2", "e1"]}
    puzzle = make_puzzle(db, "pin", answer)
    # Same squares, wrong order: the structure was seen, roles were not.
    attempt, _, _ = submit(db, puzzle, {"squares": ["e2", "e7", "e1"]})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    assert [(r.mistake_core, r.mistake_specific) for r in rows] == [
        ("wrong-target", "role-swap")
    ]
    assert rows[0].skill_key == "pin-recognition"
    # An unrelated triplet is not a swap.
    attempt2, _, _ = submit(db, puzzle, {"squares": ["a1", "a2", "a3"]}, user_id=2)
    rows2 = evidence_for(db, attempt2)
    assert [(r.mistake_core, r.mistake_specific) for r in rows2] == [
        ("wrong-target", "non-pin-triplet")
    ]
    # A malformed triplet is a format failure, not a pin error.
    attempt3, _, _ = submit(db, puzzle, {"squares": ["e7", "e2"]}, user_id=3)
    rows3 = evidence_for(db, attempt3)
    assert len(rows3) == 1 and rows3[0].mistake_core == "malformed-input"
    db.close()


# --- move-set exercises --------------------------------------------------------


def test_give_check_missed_and_phantom():
    Session = make_db()
    db = Session()
    fen = "4k3/8/8/4Q3/8/8/8/4K3 w - - 0 1"
    answer = {
        "moves": ["e5b8", "e5h5"],
        "correct_moves": ["e5b8", "e5h5"],
    }
    # Partial: one checking move found, one missed, one hallucinated.
    puzzle = make_puzzle(db, "give-check", {"moves": ["e5b8", "e5h5"]})
    _ = (fen, answer)
    attempt, _, detail = submit(
        db, puzzle, {"moves": [{"from": "e5", "to": "b8"}, {"from": "e1", "to": "e2"}]}
    )
    assert attempt.result == "partial"
    rows = evidence_for(db, attempt)
    by_key = {r.evidence_key: r for r in rows}
    assert "neg:missed-target:missed-check:primary:check-giving" in by_key
    assert "neg:wrong-target:phantom-check:primary:check-giving" in by_key
    # Only the commission implicates legal-move enumeration (Strong link).
    secondaries = [r for r in rows if r.skill_role == "secondary"]
    assert len(secondaries) == 1
    assert secondaries[0].skill_key == "legal-destinations"
    assert secondaries[0].mistake_specific == "phantom-check"
    assert set(detail["missed"]) == {"e5h5"}
    db.close()


def test_get_out_of_check_escape_rows():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "get-out-of-check", {"fen": "4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"})
    # One escape found, two missed.
    attempt, _, _ = submit(db, puzzle, {"moves": ["e1d1"]})
    assert attempt.result == "partial"
    rows = evidence_for(db, attempt)
    assert [r.mistake_specific for r in rows] == ["missed-escape"]
    assert rows[0].skill_key == "check-escaping"
    # A legal non-escaping move is a phantom escape (+ enumeration secondary).
    attempt2, _, _ = submit(db, puzzle, {"moves": ["a2a3"]}, user_id=2)
    assert attempt2.result == "wrong"
    rows2 = evidence_for(db, attempt2)
    specifics = {r.mistake_specific for r in rows2 if r.skill_role == "primary"}
    assert specifics == {"missed-escape", "phantom-escape"}
    assert any(r.skill_key == "legal-destinations" for r in rows2 if r.skill_role == "secondary")
    db.close()


def test_get_out_of_check_invalid_puzzle_is_neutral():
    # Side not in check: every submission is WRONG by construction.
    # That verdict describes content, never the user.
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(
        db,
        "get-out-of-check",
        {"fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"},
    )
    attempt, _, _ = submit(db, puzzle, {"moves": ["e1e2"]})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    assert rows[0].direction == "neutral"
    assert rows[0].mistake_core is None
    assert rows[0].skill_key is None
    assert rows[0].context_json["invalid_content"] == "side-not-in-check"
    db.close()


def test_castling_options_per_option_keys():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(
        db,
        "castling-rights",
        {"options": ["white_kingside", "white_queenside"]},
        fen="r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQ - 0 1",
    )
    attempt, _, _ = submit(db, puzzle, {"options": ["white_kingside"]})
    assert attempt.result == "partial"
    rows = evidence_for(db, attempt)
    assert [(r.mistake_core, r.mistake_specific) for r in rows] == [
        ("missed-target", "missed-option")
    ]
    assert rows[0].skill_key == "castling-legality"
    attempt2, _, _ = submit(
        db, puzzle, {"options": ["white_kingside", "white_queenside", "black_kingside"]}, user_id=2
    )
    rows2 = evidence_for(db, attempt2)
    assert ("wrong-target", "false-option") in [
        (r.mistake_core, r.mistake_specific) for r in rows2
    ]
    db.close()


# --- pathfinding family ---------------------------------------------------------


def test_pathfinding_failure_points():
    Session = make_db()
    db = Session()
    answer = {"fen": None, "from": "a1", "target": "a8", "piece": "rook", "optimal_moves": 1}
    puzzle = make_puzzle(db, "pathfinding", answer)
    # Wrong start square.
    attempt, _, _ = submit(db, puzzle, {"path": ["b1", "b8"]})
    rows = evidence_for(db, attempt)
    assert [(r.mistake_core, r.mistake_specific) for r in rows] == [
        ("illegal-action", "wrong-start")
    ]
    # Illegal rook step.
    attempt2, _, _ = submit(db, puzzle, {"path": ["a1", "b2"]}, user_id=2)
    rows2 = evidence_for(db, attempt2)
    assert [(r.mistake_core, r.mistake_specific) for r in rows2] == [
        ("illegal-action", "illegal-step")
    ]
    assert rows2[0].context_json["fail_at"] == "b2"
    assert rows2[0].confidence == "high"  # pure geometry replay
    # Legal but short path: completeness failure.
    attempt3, _, _ = submit(db, puzzle, {"path": ["a1", "a4"]}, user_id=3)
    rows3 = evidence_for(db, attempt3)
    assert [(r.mistake_core, r.mistake_specific) for r in rows3] == [
        ("missed-target", "incomplete-path")
    ]
    # Empty path: effort signal.
    attempt4, _, _ = submit(db, puzzle, {"path": []}, user_id=4)
    rows4 = evidence_for(db, attempt4)
    assert len(rows4) == 1 and rows4[0].mistake_core == "no-response"
    db.close()


def test_pathfinding_efficient_and_inefficient_correct():
    Session = make_db()
    db = Session()
    answer = {"fen": None, "from": "a1", "target": "a8", "piece": "rook", "optimal_moves": 1}
    puzzle = make_puzzle(db, "pathfinding", answer)
    attempt, _, _ = submit(db, puzzle, {"path": ["a1", "a8"]})
    rows = evidence_for(db, attempt)
    assert len(rows) == 1 and rows[0].direction == "positive"
    # Correct but non-minimal: positive-with-note, not a second negative.
    attempt2, _, _ = submit(db, puzzle, {"path": ["a1", "a4", "a8"]}, user_id=2)
    rows2 = evidence_for(db, attempt2)
    assert [r.direction for r in rows2] == ["positive", "neutral"]
    note = rows2[1]
    assert note.mistake_core == "inefficiency" and note.mistake_specific is None
    assert note.context_json["moves"] == 2
    db.close()


def test_obstacle_path_failure_is_medium_with_shortest_path_secondary():
    Session = make_db()
    db = Session()
    answer = {
        "fen": None,
        "piece": "rook",
        "from": "a1",
        "target": "a8",
        "enemies": [],
        "optimal_moves": 1,
    }
    puzzle = make_puzzle(db, "pathfinding-obstacles", answer)
    attempt, _, _ = submit(db, puzzle, {"path": ["a1", "b2"]})
    rows = evidence_for(db, attempt)
    primaries = [r for r in rows if r.skill_role == "primary"]
    assert [(r.mistake_core, r.mistake_specific) for r in primaries] == [
        ("illegal-action", "unsafe-step")
    ]
    assert primaries[0].skill_key == "constrained-path"
    assert primaries[0].confidence == "medium"  # transition replay inference
    secondaries = [r for r in rows if r.skill_role == "secondary"]
    assert len(secondaries) == 1
    assert secondaries[0].skill_key == "shortest-path"
    assert secondaries[0].context_json["skill_link"] == "strong"
    db.close()


# --- material composition / reconstruction --------------------------------------


def test_balance_scale_gap_and_over_count():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "balance-scale", {"left": ["Q", "P"], "target": 10})
    # Wrong total + too many pieces: gap (negative) + over-count (neutral note).
    attempt, _, _ = submit(db, puzzle, {"pieces": ["p"] * 6})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    gap = next(r for r in rows if r.mistake_specific == "arithmetic-gap")
    assert gap.direction == "negative" and gap.skill_key == "value-composition"
    assert gap.context_json["submitted_value"] == 6
    assert gap.context_json["target_value"] == 10
    weak_sec = [r for r in rows if r.skill_role == "secondary"]
    assert len(weak_sec) == 1 and weak_sec[0].skill_key == "material-comparison"
    assert weak_sec[0].context_json["skill_link"] == "weak"
    over = next(r for r in rows if r.mistake_specific == "over-count")
    assert over.direction == "neutral" and over.mistake_core == "inefficiency"
    # Exact minimal solution: single positive, no notes.
    attempt2, _, _ = submit(db, puzzle, {"pieces": ["Q", "P"]}, user_id=2)
    rows2 = evidence_for(db, attempt2)
    assert len(rows2) == 1 and rows2[0].direction == "positive"
    db.close()


def test_chinese_board_error_classes():
    from app.modules.chinese_board import pieces as cb

    Session = make_db()
    db = Session()
    fen = "4k3/8/8/8/8/8/5PPP/4K3 w - - 0 1"
    original = cb.extract_pieces(fen)
    assert len(original) == 5

    def placement(d, square=None):
        return {
            "square": square or d["square"],
            "piece": d["type"],
            "color": d["color"],
        }

    puzzle = make_puzzle(db, "chinese-board", {"fen": fen})
    # Drop one pawn: omission only.
    dropped = [d for d in original if d["square"] != "h2"]
    attempt, _, _ = submit(db, puzzle, {"pieces": [placement(d) for d in dropped]})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    assert [(r.mistake_core, r.mistake_specific) for r in rows] == [
        ("missed-target", "omission-lapse")
    ]
    # Right pawn, wrong square: binding error (single error, not two).
    moved = [placement(d, "f3") if d["square"] == "f2" else placement(d) for d in original]
    attempt2, _, _ = submit(db, puzzle, {"pieces": moved}, user_id=2)
    rows2 = evidence_for(db, attempt2)
    assert [(r.mistake_core, r.mistake_specific) for r in rows2] == [
        ("wrong-target", "binding-error")
    ]
    # Invented extra piece: hallucination.
    extra = [placement(d) for d in original] + [
        {"square": "a3", "piece": "P", "color": "white"}
    ]
    attempt3, _, _ = submit(db, puzzle, {"pieces": extra}, user_id=3)
    rows3 = evidence_for(db, attempt3)
    assert [(r.mistake_core, r.mistake_specific) for r in rows3] == [
        ("wrong-target", "hallucination")
    ]
    for row in rows + rows2 + rows3:
        assert row.skill_key == "position-recall"
    db.close()


# --- blind exercises ------------------------------------------------------------


def test_square_vision_identity_vs_parity():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "blindfold-square-vision", {"square": "d5"})
    # Practice tap on the wrong square.
    attempt, _, _ = submit(db, puzzle, {"square": "d6"})
    rows = evidence_for(db, attempt)
    assert [(r.mistake_core, r.mistake_specific) for r in rows] == [
        ("wrong-target", "identity-error")
    ]
    assert rows[0].skill_key == "square-knowledge"
    # Speed color button: parity error (d5 is light -> "white" is right).
    attempt2, _, _ = submit(db, puzzle, {"choice": "black"}, user_id=2)
    rows2 = evidence_for(db, attempt2)
    assert [(r.mistake_core, r.mistake_specific) for r in rows2] == [
        ("wrong-choice", "parity-error")
    ]
    db.close()


def test_blind_calculation_parseable_vs_notation():
    Session = make_db()
    db = Session()
    startpos = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    puzzle = make_puzzle(db, "blindfold-calculation", {"fen": startpos, "solution": "e2e4"})
    # Legal SAN, wrong tactic: parseable (Medium), negative.
    attempt, _, _ = submit(db, puzzle, {"move": "Nf3"})
    rows = evidence_for(db, attempt)
    assert [(r.mistake_core, r.mistake_specific) for r in rows] == [
        ("wrong-target", "wrong-tactic")
    ]
    assert rows[0].confidence == "medium"
    assert rows[0].skill_key == "blind-tactics"
    # Unparseable SAN: notation failure, neutral + weak.
    attempt2, _, _ = submit(db, puzzle, {"move": "zzz"}, user_id=2)
    rows2 = evidence_for(db, attempt2)
    assert [(r.mistake_core, r.mistake_specific) for r in rows2] == [
        ("malformed-input", "notation-error")
    ]
    assert rows2[0].direction == "neutral" and rows2[0].strength == "weak"
    # Empty move: no response at all.
    attempt3, _, _ = submit(db, puzzle, {"move": ""}, user_id=3)
    assert evidence_for(db, attempt3)[0].mistake_core == "no-response"
    db.close()


def test_opening_traps_wrong_tactic():
    Session = make_db()
    db = Session()
    startpos = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    puzzle = make_puzzle(
        db, "opening-traps", {"fen": startpos, "solutions": ["e2e4"], "theme": "FORK"}
    )
    attempt, _, _ = submit(db, puzzle, {"move": "Nf3"})
    rows = evidence_for(db, attempt)
    assert [(r.mistake_core, r.mistake_specific) for r in rows] == [
        ("wrong-target", "wrong-tactic")
    ]
    assert rows[0].skill_key == "blind-tactics"  # shared skill, second exercise
    db.close()


def test_reverse_opening_divergence_ladder():
    Session = make_db()
    db = Session()
    startpos = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    target = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    puzzle = make_puzzle(
        db,
        "reverse-opening",
        {"start_fen": startpos, "target_fen": target, "solutions": [["e2e4", "e7e5"]]},
    )
    attempt, _, _ = submit(db, puzzle, {"moves": ["e2e4", "e7e5"]})
    assert attempt.result == "correct"
    assert [r.direction for r in evidence_for(db, attempt)] == ["positive"]
    # Immediate divergence.
    attempt2, _, _ = submit(db, puzzle, {"moves": ["d2d4"]}, user_id=2)
    rows2 = evidence_for(db, attempt2)
    assert [(r.mistake_core, r.mistake_specific) for r in rows2] == [
        ("illegal-action", "early-divergence")
    ]
    assert rows2[0].skill_key == "sequence-reconstruction"
    # Late divergence (first ply matches).
    attempt3, _, _ = submit(db, puzzle, {"moves": ["e2e4", "g8f6"]}, user_id=3)
    rows3 = evidence_for(db, attempt3)
    assert [(r.mistake_core, r.mistake_specific) for r in rows3] == [
        ("illegal-action", "late-divergence")
    ]
    # Illegal UCI inside the sequence.
    attempt4, _, _ = submit(db, puzzle, {"moves": ["e2e4", "e7e9"]}, user_id=4)
    rows4 = evidence_for(db, attempt4)
    assert [(r.mistake_core, r.mistake_specific) for r in rows4] == [
        ("illegal-action", "illegal-sequence")
    ]
    db.close()


def test_trapped_pieces_weak_secondary():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "trapped-pieces", {"squares": ["a1"]})
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["h8"]})
    assert attempt.result == "wrong"
    rows = evidence_for(db, attempt)
    primaries = {r.mistake_specific for r in rows if r.skill_role == "primary"}
    assert primaries == {"missed-trap", "false-trap-claim"}
    secondaries = [r for r in rows if r.skill_role == "secondary"]
    assert secondaries and all(s.skill_key == "capture-finding" for s in secondaries)
    assert all(s.context_json["skill_link"] == "weak" for s in secondaries)
    db.close()


def test_undefended_and_pin_secondary_absence():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "undefended-pieces", {"squares": ["a1"]})
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["h8"]})
    rows = evidence_for(db, attempt)
    assert {r.mistake_specific for r in rows} == {"missed-loose-piece", "false-loose-claim"}
    assert not [r for r in rows if r.skill_role == "secondary"]
    db.close()


# --- repetition ------------------------------------------------------------------


def test_repeated_mistake_upgrades_strength():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    first, _, _ = submit(db, puzzle, {"selected_squares": ["e4"]})
    assert not [r for r in evidence_for(db, first) if r.mistake_core == "repeated-mistake"]
    # Same user, same skill, same mistake again: recurrence established.
    second, _, _ = submit(db, puzzle, {"selected_squares": ["e4"]})
    repeats = [r for r in evidence_for(db, second) if r.mistake_core == "repeated-mistake"]
    assert len(repeats) == 1
    repeat = repeats[0]
    assert repeat.direction == "negative"
    assert repeat.strength == "strong" and repeat.confidence == "high"
    assert repeat.skill_key == "capture-finding"
    assert repeat.mistake_specific == "missed-capture"  # first negative primary draft
    assert repeat.context_json["repeats_attempt_id"] == first.id
    # The base mistake is still stored (recurrence never replaces it).
    assert any(r.mistake_specific == "missed-capture" for r in evidence_for(db, second))
    db.close()


def test_repeat_is_owner_scoped_and_mistake_scoped():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    submit(db, puzzle, {"selected_squares": ["e4"]}, user_id=1)
    # A different user with the same mistake: no recurrence.
    other, _, _ = submit(db, puzzle, {"selected_squares": ["e4"]}, user_id=2)
    assert not [r for r in evidence_for(db, other) if r.mistake_core == "repeated-mistake"]
    # Same user, a correct solve: positives never trigger repeats.
    clean, _, _ = submit(db, puzzle, {"selected_squares": ["d5"]}, user_id=1)
    assert not [r for r in evidence_for(db, clean) if r.mistake_core == "repeated-mistake"]
    db.close()


def test_repeat_lookup_is_bounded():
    assert evidence_service.REPEAT_LOOKUP_LIMIT == 20


# --- idempotency + transactions -----------------------------------------------------


def test_reprocessing_attempt_does_not_duplicate():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5", "f5"], "from": "e4"})
    attempt, _, detail = submit(db, puzzle, {"selected_squares": ["d5"]})
    first = evidence_for(db, attempt)
    assert first
    again = evidence_service.generate_for_attempt(
        db,
        attempt=attempt,
        result=attempt.result,
        detail=dict(attempt.validation_detail or {}),
        raw_answer=dict(attempt.answer_json),
        puzzle_answer=dict(puzzle.answer_json),
        hints_used=list(attempt.hints_used or []),
    )
    assert [r.id for r in again] == [r.id for r in first]
    assert len(evidence_for(db, attempt)) == len(first)
    db.close()


def test_evidence_key_uniqueness_is_database_enforced():
    from sqlalchemy.exc import IntegrityError

    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["d5"]})
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    dupe = Evidence(
        attempt_id=attempt.id,
        user_id=attempt.user_id,
        guest_session_id=None,
        exercise_slug=attempt.exercise_slug,
        puzzle_id=attempt.puzzle_id,
        source="attempt",
        skill_key=rows[0].skill_key,
        skill_role=rows[0].skill_role,
        mistake_core=rows[0].mistake_core,
        mistake_specific=rows[0].mistake_specific,
        direction=rows[0].direction,
        strength=rows[0].strength,
        confidence=rows[0].confidence,
        context_json={},
        evidence_key=rows[0].evidence_key,
        observed_at=attempt.created_at,
    )
    db.add(dupe)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    db.close()


def test_failed_attempt_leaves_no_orphan_evidence(monkeypatch):
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    before_attempts = db.query(Attempt).count()
    before_evidence = db.query(Evidence).count()

    def _boom(*args, **kwargs):
        raise RuntimeError("evidence-store-down")

    monkeypatch.setattr(evidence_service, "generate_for_attempt", _boom)
    with pytest.raises(RuntimeError):
        submit(db, puzzle, {"selected_squares": ["d5"]})
    db.rollback()
    # Atomic submission: neither a half-attempt nor orphan evidence survives.
    assert db.query(Attempt).count() == before_attempts
    assert db.query(Evidence).count() == before_evidence
    db.close()


def test_classification_bug_can_never_break_a_submit(monkeypatch):
    # Even a total classifier collapse degrades to explicit neutral
    # evidence; the attempt outcome itself is never corrupted.
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})

    def _boom(**kwargs):
        raise RuntimeError("classifier-bug")

    monkeypatch.setattr(classify, "get_classifier", lambda slug: _boom)
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["e4"]})
    assert attempt.result == "wrong"  # validator verdict intact
    rows = evidence_for(db, attempt)
    assert len(rows) == 1
    assert rows[0].direction == "neutral" and rows[0].confidence == "low"
    assert rows[0].context_json["classification"] == "unsupported"
    db.close()


def test_classify_is_total_over_adversarial_inputs():
    garbage_details = [{}, {"correct": "nope"}, {"missed": None, "wrong": 42}, {"missed": ["a9"]}]
    garbage_answers = [{}, [], None, {"moves": "e2e4"}, {"path": [None, {}]}, {"pieces": "Q"}]
    for slug in tx.EXERCISE_SKILLS:
        for detail in garbage_details:
            for raw in garbage_answers:
                drafts = classify.classify(
                    exercise_slug=slug,
                    result="wrong",
                    detail=detail,
                    raw_answer=raw if isinstance(raw, dict) else {},
                    puzzle_answer={},
                    hints_used=[],
                )
                assert drafts, slug
                for draft in drafts:
                    assert draft.direction in tx.DIRECTIONS
                    assert draft.strength in tx.STRENGTHS
                    assert draft.confidence in tx.CONFIDENCES
                    if draft.mistake_specific is not None:
                        assert draft.mistake_specific in tx.SPECIFIC_TO_CORE
                    if draft.role == "secondary":
                        assert draft.link in ("strong", "weak")


def test_unknown_exercise_is_explicitly_unclassified():
    drafts = classify.classify(
        exercise_slug="future-exercise",
        result="wrong",
        detail={"correct": [], "missed": ["e4"], "wrong": []},
        raw_answer={"selected_squares": ["e4"]},
        puzzle_answer={},
        hints_used=[],
    )
    assert len(drafts) == 1
    assert drafts[0].confidence == "low"
    assert drafts[0].direction == "neutral"


# --- context: modes, rating boundary, speed ----------------------------------------


def test_practice_attempts_never_rate_but_still_evidenced():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["d5"]})
    assert attempt.rating_before is None
    assert attempt.rating_delta is None
    assert attempt.rating_after is None
    assert len(evidence_for(db, attempt)) == 1
    db.close()


def test_rated_attempt_rates_and_evidences_without_coupling():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt, _, _ = submit(
        db, puzzle, {"selected_squares": ["d5"]}, mode=AttemptMode.RATED
    )
    assert attempt.rating_before is not None
    assert attempt.rating_after == attempt.rating_before + attempt.rating_delta
    rows = evidence_for(db, attempt)
    assert len(rows) == 1 and rows[0].direction == "positive"
    assert rows[0].context_json["mode"] == "rated"
    # Rating math is untouched by evidence (formula v1, K=32 provisional).
    assert rating_service.INITIAL_RATING == 1200.0
    db.close()


def test_guest_attempt_is_rejected_without_evidence():
    # Product decision: guests cannot practice. The service refuses
    # ownerless submissions, so neither an attempt nor evidence persists.
    # Historical guest rows stay readable; only new submissions are gated.
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    with pytest.raises(ValueError, match="auth_required"):
        submit(
            db, puzzle, {"selected_squares": ["e4"]}, user_id=None, guest_session_id=9
        )
    assert db.query(Attempt).count() == 0
    assert db.query(Evidence).count() == 0
    db.close()


def test_speed_session_submit_is_practice_evidence():
    from app.modules.piece_recognition import sessions

    Session = make_db()
    db = Session()
    session = sessions.start_session(db, user_id=11)
    sessions.prepare_puzzles(db, session.id, count=sessions.MIN_START_BUFFER)
    session = sessions.begin_session(db, session.id)
    puzzle_id = (session.puzzle_ids or [])[0]
    puzzle = db.get(Puzzle, puzzle_id)
    assert puzzle is not None
    answer = {"selected_squares": list((puzzle.answer_json or {}).get("squares", []))}
    attempt, _, _, _ = sessions.submit(
        db, session.id, user_id=11, puzzle_id=puzzle_id, answer=answer
    )
    # Speed attempts persist as practice attempts (no session FK on Attempt
    # yet): the speed-vs-practice discount rule stays deferred, but the
    # mode context is preserved honestly for P3.
    assert attempt.mode == "practice"
    rows = evidence_for(db, attempt)
    assert rows
    assert all(r.context_json["mode"] == "practice" for r in rows)
    db.close()


def test_evidence_vocab_uses_only_canonical_keys():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5", "f5"], "from": "e4"})
    attempt, _, _ = submit(db, puzzle, {"selected_squares": ["e4"]})
    for row in evidence_for(db, attempt):
        assert row.direction in tx.DIRECTIONS
        assert row.strength in tx.STRENGTHS
        assert row.confidence in tx.CONFIDENCES
        assert row.skill_role in ("primary", "secondary", "none")
        if row.mistake_core is not None:
            assert row.mistake_core in tx.CORE_MISTAKES
        if row.mistake_specific is not None:
            assert row.mistake_specific in tx.SPECIFIC_TO_CORE
            assert tx.SPECIFIC_TO_CORE[row.mistake_specific] == row.mistake_core
        if row.skill_key is not None:
            assert row.skill_key in tx.SKILLS
    db.close()


# --- migration ----------------------------------------------------------------------


def test_fresh_boot_stamps_v13():
    engine = create_engine("sqlite:///:memory:")
    version = ensure_schema(engine)
    assert version == SCHEMA_VERSION == 15
    assert get_schema_version(engine) == SCHEMA_VERSION
    assert ensure_schema(engine) == SCHEMA_VERSION


def test_v13_migration_preserves_legacy_rows_without_backfill():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE attempts (id INTEGER PRIMARY KEY, puzzle_id INTEGER)")
        )
        conn.execute(text("INSERT INTO attempts (id, puzzle_id) VALUES (1, 10)"))
        _migrate_v13_p2(conn)
    with engine.connect() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("attempts")}
        assert "validation_detail" in cols
        row = conn.execute(
            text("SELECT puzzle_id, validation_detail FROM attempts")
        ).first()
        assert row[0] == 10
        assert row[1] is None
    with engine.begin() as conn:
        _migrate_v13_p2(conn)
