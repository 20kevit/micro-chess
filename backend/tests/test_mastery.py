"""P4 — Mastery derivation over Skill State + Evidence.

Unit tests use synthetic rows through the real ``skill_state.aggregate``
fold into ``mastery.evaluate_skill`` (Evidence -> Skill State ->
Mastery); integration tests submit real attempts (real validators) and
read mastery back. Mastery is read-only: row counts must be identical
before/after every read.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.migration import import_models
from app.modules.evidence import taxonomy as tx
from app.modules.evidence.models import Evidence
from app.modules.mastery import service as mastery
from app.modules.progress import service as attempt_service
from app.modules.puzzles.models import STATUS_PUBLISHED, Puzzle
from app.modules.rule_engine.base import AttemptMode
from app.modules.skill_state import service as skill_state

import app.modules.captures  # noqa: F401  (registers validator + classifier)

BASE_TIME = datetime(2026, 9, 1, 12, 0, 0)


def row(skill="capture-finding", direction="positive", strength="direct",
        confidence="high", role="primary", attempt=1, day=0, puzzle=1,
        difficulty=3, hinted=False, hour=0):
    if hinted and direction == "positive":
        strength = "weak"
    return SimpleNamespace(
        id=attempt,
        attempt_id=attempt,
        skill_key=skill,
        direction=direction,
        strength=strength,
        confidence=confidence,
        skill_role=role,
        puzzle_id=puzzle,
        exercise_slug="captures",
        observed_at=BASE_TIME + timedelta(days=day, hours=hour),
        context_json={
            "scaffolded": hinted,
            "has_hints": hinted,
            "hints_count": 1 if hinted else 0,
            "difficulty_snapshot": difficulty,
        },
    )


def clean(skill, n, start_attempt=1, puzzles=None, days=None,
          difficulties=None, hinted=False):
    rows = []
    for i in range(n):
        puzzle = puzzles[i % len(puzzles)] if puzzles else 1
        day = days[i % len(days)] if days else i
        difficulty = difficulties[i % len(difficulties)] if difficulties else 3
        rows.append(row(
            skill, attempt=start_attempt + i, day=day, puzzle=puzzle,
            difficulty=difficulty, hinted=hinted,
        ))
    return rows


def mastery_of(rows, skill="capture-finding", reference=None):
    state = skill_state.aggregate(rows)
    return mastery.evaluate_skill(skill, state.skills[skill], rows, reference=reference)


def ref(day):
    return BASE_TIME + timedelta(days=day)


# --- insufficient evidence --------------------------------------------------


def test_empty_history_is_unknown():
    state = skill_state.aggregate([])
    result = mastery.evaluate_skill("capture-finding", state.skills["capture-finding"], [])
    assert result.status == "unknown"
    assert result.attempts == 0
    assert "no-evidence" in result.reasons


def test_neutral_rows_are_unknown():
    rows = [SimpleNamespace(
        id=1, attempt_id=1, skill_key=None, direction="neutral",
        strength="weak", confidence="high", skill_role="none",
        puzzle_id=1, exercise_slug="captures", observed_at=BASE_TIME,
        context_json={},
    )]
    assert mastery_of(rows).status == "unknown"


def test_single_attempt_never_passes_emerging():
    assert mastery_of(clean("capture-finding", 1)).status == "emerging"


def test_single_negative_is_emerging():
    rows = [row("capture-finding", direction="negative")]
    assert mastery_of(rows).status == "emerging"


def test_two_attempts_still_emerging():
    assert mastery_of(clean("capture-finding", 2)).status == "emerging"


# --- level ladder -----------------------------------------------------------


def test_three_clean_demonstrations_develop():
    result = mastery_of(clean("capture-finding", 3))
    assert result.status == "developing"
    assert result.clean_positives == 3


def test_five_clean_across_puzzles_and_days_are_proficient():
    rows = clean("capture-finding", 5, puzzles=[1, 2], days=[0, 1])
    result = mastery_of(rows, reference=ref(1))
    assert result.status == "proficient"


def test_eight_clean_across_time_are_mastered():
    rows = clean(
        "capture-finding", 8, puzzles=[1, 2, 3],
        days=[0, 1, 2, 3, 4, 5, 6, 8], difficulties=[3, 4],
    )
    result = mastery_of(rows, reference=ref(8))
    assert result.status == "mastered"
    assert result.span_days == 8
    assert result.confidence == "high"


# --- confidence -------------------------------------------------------------


def test_proficient_needs_medium_confidence():
    level = SimpleNamespace(units=5.0, confidence="low")
    rows = clean("capture-finding", 5, puzzles=[1, 2], days=[0, 1])
    result = mastery.evaluate_skill("capture-finding", level, rows, reference=ref(1))
    assert result.status in ("emerging", "developing")
    assert "confidence-low" in result.reasons


def test_mastered_needs_high_confidence():
    rows = clean(
        "capture-finding", 8, puzzles=[1, 2, 3],
        days=[0, 1, 2, 3, 4, 5, 6, 8], difficulties=[3, 4],
    )
    state = skill_state.aggregate(rows[:5])
    assert state.skills["capture-finding"].confidence == "high"
    # Five attempts (medium confidence) with full spread still stop at
    # proficient: mastered structurally needs 8 attempts / high confidence.
    five = mastery_of(rows[:5], reference=ref(4))
    assert five.status == "proficient"


# --- diversity / spread -----------------------------------------------------


def test_proficient_needs_two_puzzles():
    rows = clean("capture-finding", 5, puzzles=[1], days=[0, 1])
    result = mastery_of(rows, reference=ref(1))
    assert result.status != "proficient"
    assert "puzzles<2" in result.reasons


def test_proficient_needs_two_days():
    rows = clean("capture-finding", 5, puzzles=[1, 2], days=[0])
    result = mastery_of(rows, reference=ref(0))
    assert result.status != "proficient"
    assert "spread<2d" in result.reasons


def test_mastered_needs_three_puzzles_and_days():
    rows = clean(
        "capture-finding", 8, puzzles=[1, 2],
        days=[0, 1, 2, 3, 4, 5, 6, 8], difficulties=[3, 4],
    )
    result = mastery_of(rows, reference=ref(8))
    assert result.status == "proficient"  # falls back, never mastered
    assert result.puzzles == 2


def test_mastered_gate_reports_missing_puzzles():
    state = skill_state.aggregate(
        clean("capture-finding", 8, puzzles=[1, 2],
              days=[0, 1, 2, 3, 4, 5, 6, 8], difficulties=[3, 4]))
    rows = clean("capture-finding", 8, puzzles=[1, 2],
                 days=[0, 1, 2, 3, 4, 5, 6, 8], difficulties=[3, 4])
    level = state.skills["capture-finding"]
    missing = mastery._missing_mastered(
        units=level.units, confidence=level.confidence, attempts=8,
        puzzles=2, days=8, difficulties=2, max_difficulty=4, clean=8,
        recent_ok=True, span_days=8, fresh=True,
    )
    assert "puzzles<3" in missing


def test_mastered_needs_difficulty_diversity():
    rows = clean(
        "capture-finding", 8, puzzles=[1, 2, 3],
        days=[0, 1, 2, 3, 4, 5, 6, 8], difficulties=[3],
    )
    result = mastery_of(rows, reference=ref(8))
    assert result.status == "proficient"  # falls back, never mastered
    assert result.max_difficulty == 3


# --- difficulty -------------------------------------------------------------


def test_proficient_needs_difficulty_two():
    rows = clean("capture-finding", 5, puzzles=[1, 2], days=[0, 1],
                 difficulties=[1])
    result = mastery_of(rows, reference=ref(1))
    assert result.status != "proficient"
    assert "difficulty<2" in result.reasons


def test_mastered_needs_difficulty_three():
    rows = clean(
        "capture-finding", 8, puzzles=[1, 2, 3],
        days=[0, 1, 2, 3, 4, 5, 6, 8], difficulties=[2],
    )
    result = mastery_of(rows, reference=ref(8))
    assert result.status == "proficient"  # falls back, never mastered
    assert result.max_difficulty == 2


def test_missing_difficulty_never_satisfies_gate():
    rows = clean("capture-finding", 5, puzzles=[1, 2], days=[0, 1])
    for r in rows:
        r.context_json = {}
    result = mastery_of(rows, reference=ref(1))
    assert result.status != "proficient"
    assert "difficulty<2" in result.reasons


# --- recent clean record ----------------------------------------------------


def test_recent_failure_blocks_developing():
    rows = clean("capture-finding", 3) + [
        row("capture-finding", direction="negative", attempt=9, day=3)]
    result = mastery_of(rows, reference=ref(3))
    assert result.status == "emerging"
    assert "recent-failure" in result.reasons


def test_recent_failure_blocks_proficient():
    rows = clean("capture-finding", 5, puzzles=[1, 2], days=[0, 1]) + [
        row("capture-finding", direction="negative", attempt=9, day=1)]
    result = mastery_of(rows, reference=ref(1))
    # A trailing failure breaks the developing gate too, so the skill
    # falls all the way back to emerging (never proficient/mastered).
    assert result.status == "emerging"
    assert "recent-failure" in result.reasons


def test_hinted_tail_blocks_but_old_failure_heals():
    rows = clean("capture-finding", 4, puzzles=[1, 2], days=[0, 1])
    rows.append(row("capture-finding", attempt=9, day=1, puzzle=2,
                    direction="negative"))
    result = mastery_of(rows, reference=ref(1))
    assert result.status != "proficient"


def test_old_failure_does_not_block_forever():
    rows = [row("capture-finding", direction="negative", attempt=1, day=0)]
    rows += clean("capture-finding", 5, start_attempt=2,
                  puzzles=[1, 2], days=[1, 2])
    result = mastery_of(rows, reference=ref(2))
    assert result.status == "proficient"


# --- hints ------------------------------------------------------------------


def test_hinted_only_history_never_develops():
    rows = clean("capture-finding", 3, hinted=True)
    result = mastery_of(rows)
    assert result.status == "emerging"
    assert "no-clean-positive" in result.reasons


def test_hinted_recent_blocks_proficient():
    rows = clean("capture-finding", 4, puzzles=[1, 2], days=[0, 1])
    rows.append(row("capture-finding", attempt=9, day=1, puzzle=2, hinted=True))
    result = mastery_of(rows, reference=ref(1))
    assert result.status != "proficient"
    assert "recent-unclean" in result.reasons


def test_hinted_recent_blocks_mastered():
    rows = clean(
        "capture-finding", 7, puzzles=[1, 2, 3],
        days=[0, 1, 2, 3, 4, 5, 6], difficulties=[3, 4],
    )
    rows.append(row("capture-finding", attempt=9, day=8, puzzle=1, hinted=True))
    result = mastery_of(rows, reference=ref(8))
    assert result.status != "mastered"
    assert "recent-unclean" in result.reasons


# --- retention / recency ----------------------------------------------------


def test_mastered_needs_week_span():
    rows = clean(
        "capture-finding", 8, puzzles=[1, 2, 3],
        days=[0, 0, 1, 1, 2, 2, 2, 2], difficulties=[3, 4],
    )
    result = mastery_of(rows, reference=ref(2))
    assert result.status == "proficient"  # falls back, never mastered
    assert result.span_days == 2


def test_stale_history_caps_at_developing():
    rows = clean("capture-finding", 5, puzzles=[1, 2], days=[0, 1])
    result = mastery_of(rows, reference=ref(60))
    assert result.status == "developing"
    assert "stale" in result.reasons


def test_stale_mastered_candidate_falls_back():
    rows = clean(
        "capture-finding", 8, puzzles=[1, 2, 3],
        days=[0, 1, 2, 3, 4, 5, 6, 8], difficulties=[3, 4],
    )
    result = mastery_of(rows, reference=ref(90))
    assert result.status == "developing"
    assert "stale" in result.reasons


# --- determinism + isolation ------------------------------------------------


def test_fold_is_deterministic_under_reordering():
    rows = clean(
        "capture-finding", 8, puzzles=[1, 2, 3],
        days=[0, 1, 2, 3, 4, 5, 6, 8], difficulties=[3, 4],
    )
    first = mastery_of(rows, reference=ref(8))
    second = mastery_of(list(reversed(rows)), reference=ref(8))
    assert first == second
    assert first.status == "mastered"


def test_other_skills_do_not_leak():
    rows = clean("capture-finding", 5, puzzles=[1, 2], days=[0, 1])
    rows += clean("undefended-detection", 5, start_attempt=50,
                  puzzles=[7, 8], days=[0, 1])
    assert mastery_of(rows, "capture-finding", reference=ref(1)).status == "proficient"
    assert mastery_of(rows, "check-giving", reference=ref(1)).status == "unknown"


# --- integration over real attempts -----------------------------------------


def make_db():
    import_models()
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def make_puzzle(db, slug, answer, difficulty=3):
    puzzle = Puzzle(
        exercise_slug=slug, fen=None, position_json={}, answer_json=answer,
        hint_json={}, is_published=True, is_archived=False,
        status=STATUS_PUBLISHED, source="manual", difficulty=difficulty,
        target_rating=1400.0, initial_rating=1450.0,
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle


def counts(db):
    from app.modules.progress.models import Attempt

    return (db.query(Attempt).count(), db.query(Evidence).count())


def test_single_real_attempt_is_emerging():
    db = make_db()()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt_service.submit_attempt(
        db, user_id=1, puzzle_id=puzzle.id,
        answer={"selected_squares": ["d5"]}, mode=AttemptMode.PRACTICE)
    result = mastery.mastery_for_user(db, 1)["capture-finding"]
    assert result.status == "emerging"


def test_three_real_attempts_develop():
    db = make_db()()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    for _ in range(3):
        attempt_service.submit_attempt(
            db, user_id=1, puzzle_id=puzzle.id,
            answer={"selected_squares": ["d5"]}, mode=AttemptMode.PRACTICE)
    result = mastery.mastery_for_user(db, 1)["capture-finding"]
    assert result.status == "developing"
    assert result.clean_positives == 3


def test_real_hinted_attempts_never_count_clean():
    db = make_db()()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    for _ in range(3):
        attempt_service.submit_attempt(
            db, user_id=1, puzzle_id=puzzle.id,
            answer={"selected_squares": ["d5"]}, mode=AttemptMode.PRACTICE,
            hints_used=["h1"])
    result = mastery.mastery_for_user(db, 1)["capture-finding"]
    assert result.status == "emerging"
    assert result.clean_positives == 0


def test_mastery_reads_are_side_effect_free():
    db = make_db()()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    attempt_service.submit_attempt(
        db, user_id=1, puzzle_id=puzzle.id,
        answer={"selected_squares": ["d5"]}, mode=AttemptMode.PRACTICE)
    before = counts(db)
    mastery.mastery_for_user(db, 1)
    mastery.mastery_for_user(db, 1)
    assert counts(db) == before


def test_mastery_is_isolated_per_user():
    db = make_db()()
    puzzle = make_puzzle(db, "captures", {"squares": ["d5"], "from": "e4"})
    for _ in range(3):
        attempt_service.submit_attempt(
            db, user_id=1, puzzle_id=puzzle.id,
            answer={"selected_squares": ["d5"]}, mode=AttemptMode.PRACTICE)
    assert mastery.mastery_for_user(db, 2)["capture-finding"].status == "unknown"
    assert mastery.mastery_for_user(db, 1)["capture-finding"].status == "developing"


def test_mastery_covers_all_canonical_skills():
    db = make_db()()
    result = mastery.mastery_for_user(db, 1)
    assert set(result) == set(tx.SKILLS)
    assert all(r.status == "unknown" for r in result.values())
