"""P3 — Skill State aggregation over P2 evidence.

Unit tests use synthetic rows against the pure ``aggregate`` fold;
integration tests submit real attempts (real validators) and read the
derived state back. Skill state is read-only: row counts must be
identical before/after every read.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.migration import import_models
from app.modules.evidence import taxonomy as tx
from app.modules.evidence.models import Evidence
from app.modules.progress import service as attempt_service
from app.modules.puzzles.models import STATUS_PUBLISHED, Puzzle
from app.modules.rule_engine.base import AttemptMode
from app.modules.skill_state import service as skill_state

import app.modules.captures  # noqa: F401  (registers validator + classifier)

BASE_TIME = datetime(2026, 9, 1, 12, 0, 0)


def row(skill="capture-finding", direction="positive", strength="direct",
        confidence="high", role="primary", attempt=1, day=0):
    return SimpleNamespace(
        id=attempt,
        attempt_id=attempt,
        skill_key=skill,
        direction=direction,
        strength=strength,
        confidence=confidence,
        skill_role=role,
        observed_at=BASE_TIME + timedelta(days=day),
    )


def clean_positives(skill, n, start_attempt=1):
    return [row(skill, attempt=start_attempt + i, day=i) for i in range(n)]


# --- pure fold ---------------------------------------------------------------


def test_empty_history_gives_18_unseen_skills():
    state = skill_state.aggregate([])
    assert len(state.skills) == 18 == len(tx.SKILLS)
    assert set(state.skills) == set(tx.SKILLS)
    assert all(s.level == "unseen" for s in state.skills.values())
    assert state.overall_level == "unseen"
    assert state.overall_confidence == "low"
    assert state.skills_seen == 0


def test_no_response_is_never_skill_evidence():
    rows = [row(skill=None, direction="neutral", strength="weak",
                confidence="high", role="none")]
    state = skill_state.aggregate(rows)
    assert state.skills_seen == 0
    assert state.overall_level == "unseen"


def test_neutral_rows_never_move_estimates():
    rows = [
        row("capture-finding", direction="neutral"),  # malformed-input shape
        row("capture-finding", direction="neutral", strength="weak",
            confidence="low", role="none"),  # unclassified shape
    ]
    state = skill_state.aggregate(rows)
    assert state.skills["capture-finding"].level == "unseen"
    assert state.skills_seen == 0


def test_noncanonical_skill_rows_are_ignored():
    state = skill_state.aggregate([row("memory-board")])
    assert state.skills_seen == 0
    assert state.overall_level == "unseen"


def test_one_clean_demonstration_is_one_unit():
    state = skill_state.aggregate([row("capture-finding")])
    skill = state.skills["capture-finding"]
    assert (skill.points, skill.units) == (8, 1.0)
    assert skill.level == "developing"
    assert skill.confidence == "low"  # single observation
    assert skill.attempts_count == 1


def test_scaffolded_positive_counts_half():
    state = skill_state.aggregate(
        [row("capture-finding", strength="weak")])  # hints-used shape
    skill = state.skills["capture-finding"]
    assert (skill.points, skill.units) == (4, 0.5)
    assert skill.level == "emerging"


def test_secondary_carries_less_than_primary():
    secondary = skill_state.aggregate(
        [row("legal-destinations", direction="negative", role="secondary")])
    primary = skill_state.aggregate(
        [row("legal-destinations", direction="negative", role="primary")])
    assert secondary.skills["legal-destinations"].points == -4
    assert primary.skills["legal-destinations"].points == -8
    assert secondary.skills["legal-destinations"].level == "emerging"
    assert primary.skills["legal-destinations"].level == "struggling"


def test_repeated_mistake_hits_harder_than_single_error():
    single = skill_state.aggregate([row("capture-finding", direction="negative")])
    repeated = skill_state.aggregate(
        [row("capture-finding", direction="negative", strength="strong")])
    assert single.skills["capture-finding"].units == -1.0
    assert repeated.skills["capture-finding"].units == -1.5


def test_low_confidence_carries_no_points():
    state = skill_state.aggregate(
        [row("capture-finding", confidence="low")])
    assert state.skills["capture-finding"].points == 0


def test_medium_confidence_counts_half_of_high():
    state = skill_state.aggregate(
        [row("capture-finding", confidence="medium")])
    assert state.skills["capture-finding"].points == 4


def test_level_bands():
    assert skill_state.aggregate(clean_positives("capture-finding", 2)).skills[
        "capture-finding"].level == "developing"  # 2 units
    assert skill_state.aggregate(clean_positives("capture-finding", 5)).skills[
        "capture-finding"].level == "proficient"  # 5 units
    assert skill_state.aggregate(
        clean_positives("capture-finding", 5)).skills[
        "capture-finding"].confidence == "high"  # 5 attempts


def test_unseen_skills_do_not_drag_overall():
    state = skill_state.aggregate([row("capture-finding", direction="negative")])
    assert state.skills_seen == 1
    assert state.overall_level == "struggling"
    assert state.overall_units == -1.0


def test_overall_is_evidence_weighted_not_simple_average():
    rows = clean_positives("capture-finding", 10) + [
        row("undefended-detection", direction="negative", attempt=100)]
    state = skill_state.aggregate(rows)
    assert state.skills_seen == 2
    # Simple average of units would be (10 + -1) / 2 = 4.5; the
    # evidence-weighted mean is (10*80 + -1*8) / 88 = 9.0.
    assert state.overall_units == 9.0
    assert state.overall_level == "proficient"


def test_fold_is_deterministic_under_reordering():
    rows = clean_positives("capture-finding", 4) + [
        row("undefended-detection", direction="negative", attempt=50, day=9)]
    first = skill_state.aggregate(rows)
    second = skill_state.aggregate(list(reversed(rows)))
    assert first == second


def test_full_history_counts_without_decay():
    rows = clean_positives("capture-finding", 2) + [
        row("capture-finding", direction="negative", attempt=9, day=60)]
    skill = skill_state.aggregate(rows).skills["capture-finding"]
    assert skill.points == 16 - 8
    assert skill.attempts_count == 3


# --- integration over real attempts ------------------------------------------

def make_db():
    import_models()
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def make_puzzle(db, slug, answer):
    puzzle = Puzzle(
        exercise_slug=slug, fen=None, position_json={}, answer_json=answer,
        hint_json={}, is_published=True, is_archived=False,
        status=STATUS_PUBLISHED, source="manual", difficulty=3,
        target_rating=1400.0, initial_rating=1450.0,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle


def counts(db):
    from app.modules.progress.models import Attempt

    return (db.query(Attempt).count(), db.query(Evidence).count())


def test_correct_attempts_build_skill_state():
    db = make_db()()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    for _ in range(3):
        attempt_service.submit_attempt(
            db, user_id=1, puzzle_id=puzzle.id,
            answer={"selected_squares": ["d5"]}, mode=AttemptMode.PRACTICE)
    state = skill_state.skill_state_for_user(db, 1)
    skill = state.skills["capture-finding"]
    assert (skill.points, skill.units) == (24, 3.0)
    assert skill.level == "proficient"
    assert skill.confidence == "medium"
    assert state.skills_seen == 1
    assert state.overall_level == "proficient"


def test_wrong_commission_hits_primary_and_secondary():
    db = make_db()()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt_service.submit_attempt(
        db, user_id=1, puzzle_id=puzzle.id,
        answer={"selected_squares": ["a1"]}, mode=AttemptMode.PRACTICE)
    state = skill_state.skill_state_for_user(db, 1)
    assert state.skills["capture-finding"].points == -16  # missed + wrong
    assert state.skills["capture-finding"].level == "struggling"
    assert state.skills["legal-destinations"].points == -4  # secondary only
    assert state.skills["legal-destinations"].level == "emerging"


def test_timeout_leaves_no_skill_trace():
    db = make_db()()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt_service.submit_attempt(
        db, user_id=1, puzzle_id=puzzle.id, answer={},
        mode=AttemptMode.PRACTICE, client_result="timeout")
    state = skill_state.skill_state_for_user(db, 1)
    assert state.skills_seen == 0
    assert state.overall_level == "unseen"


def test_skill_state_reads_are_side_effect_free():
    db = make_db()()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt_service.submit_attempt(
        db, user_id=1, puzzle_id=puzzle.id,
        answer={"selected_squares": ["d5"]}, mode=AttemptMode.PRACTICE)
    before = counts(db)
    skill_state.skill_state_for_user(db, 1)
    skill_state.skill_state_for_user(db, 1)
    assert counts(db) == before


def test_state_is_isolated_per_user():
    db = make_db()()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt_service.submit_attempt(
        db, user_id=1, puzzle_id=puzzle.id,
        answer={"selected_squares": ["d5"]}, mode=AttemptMode.PRACTICE)
    assert skill_state.skill_state_for_user(db, 2).skills_seen == 0
    assert skill_state.skill_state_for_user(db, 1).skills_seen == 1
