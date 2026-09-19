"""P7 — Recommendation engine.

Read-only deterministic selection over P1-P6 state:

* Direct open coach assignments override the engine, but lifecycle and
  safety still apply (unknown/disabled exercises and unservable puzzles
  are skipped, never served).
* Engine buckets: struggling skill -> emerging/developing -> cold start
  (insufficient evidence, never assumed mastered) -> proficient ->
  mastered (review only when nothing else has servable content).
* Puzzle pick is ability-relative (rating, else external placement,
  else 1200 default); external ratings never gate eligibility.
* Only ``published`` puzzles are servable: draft / validated /
  reviewed / approved / quarantined / retired / rejected (+ archived
  rows) are filtered. Speed (``duration_ms``) is never a signal.
* No persistence: row counts are identical before/after every call,
  and repeated calls over unchanged state return identical output.
"""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.migration import import_models
from app.modules.evidence.models import Evidence
from app.modules.exercises.models import Exercise
from app.modules.mastery import service as mastery_service
from app.modules.player.models import PlayerExternalIdentity
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import (
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_PUBLISHED,
    STATUS_QUARANTINED,
    STATUS_REJECTED,
    STATUS_RETIRED,
    STATUS_REVIEWED,
    STATUS_VALIDATED,
    Puzzle,
)
from app.modules.rating_engine.models import PlayerRating
from app.modules.recommendations import service as rec
from app.modules.relationships import service as relationship_service
from app.modules.skill_state import service as skill_state_service
from app.modules.users.models import User, UserRole

CAPTURES = "captures"  # primary skill: capture-finding
UNDEFENDED = "undefended-pieces"  # primary skill: undefended-detection
BASE = datetime(2026, 9, 1, 12, 0, 0)


def make_db():
    import_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def make_user(db, username, roles=()):
    user = User(username=username, email=None, password_hash="h", display_name=username)
    db.add(user)
    db.commit()
    db.refresh(user)
    for role in roles:
        db.add(UserRole(user_id=user.id, role=role))
    db.commit()
    db.refresh(user)
    return user


def ensure_exercise(db, slug, active=True):
    row = db.get(Exercise, slug)
    if row is None:
        row = Exercise(slug=slug, title_fa=slug, is_active=active, sort_order=0)
        db.add(row)
        db.commit()
        db.refresh(row)
    elif row.is_active != active:
        row.is_active = active
        db.commit()
    return row


def make_puzzle(db, slug, rating=1200.0, status=STATUS_PUBLISHED,
                published=True, archived=False, difficulty=3):
    row = Puzzle(
        exercise_slug=slug,
        fen=None,
        position_json={},
        answer_json={"squares": ["e4"]},
        hint_json={},
        prompt_fa="",
        explanation="",
        initial_rating=rating,
        is_published=published,
        is_archived=archived,
        status=status,
        source="manual",
        difficulty=difficulty,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_attempt(db, user_id, puzzle, result="correct", duration_ms=None, day=0):
    row = Attempt(
        user_id=user_id,
        guest_session_id=None,
        puzzle_id=puzzle.id,
        exercise_slug=puzzle.exercise_slug,
        mode="practice",
        result=result,
        answer_json={},
        score=1.0,
        duration_ms=duration_ms,
        hints_used=[],
        created_at=BASE + timedelta(days=day),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_evidence(db, user_id, attempt, puzzle, skill, direction="positive",
                 day=0, difficulty=3, key="k", hinted=False):
    context = {
        "mode": "practice",
        "result": "correct" if direction == "positive" else "wrong",
        "exercise_slug": puzzle.exercise_slug,
        "puzzle_id": puzzle.id,
        "has_hints": hinted,
        "hints_count": 1 if hinted else 0,
        "difficulty_snapshot": difficulty,
    }
    row = Evidence(
        attempt_id=attempt.id,
        user_id=user_id,
        guest_session_id=None,
        exercise_slug=puzzle.exercise_slug,
        puzzle_id=puzzle.id,
        source="attempt",
        skill_key=skill,
        skill_role="primary",
        mistake_core=None if direction == "positive" else "missed-target",
        mistake_specific=None,
        direction=direction,
        strength="direct",
        confidence="high",
        context_json=context,
        evidence_key=f"{key}:{attempt.id}",
        observed_at=BASE + timedelta(days=day),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def make_pair(db, coach_name="coach", student_name="student"):
    coach = make_user(db, coach_name, roles=("COACH",))
    student = make_user(db, student_name)
    rel = relationship_service.create_relationship(
        db, actor=coach, kind="coach", other_username=student.username
    )
    relationship_service.accept_relationship(db, actor=student, relationship_id=rel.id)
    return coach, student


def counts(db):
    out = {}
    for model in (Attempt, Evidence, PlayerRating, Puzzle, PlayerExternalIdentity):
        out[model.__tablename__] = db.query(model).count()
    return out


def seed_two_exercises(db):
    ensure_exercise(db, CAPTURES)
    ensure_exercise(db, UNDEFENDED)


# --- cold start + lifecycle ----------------------------------------------------


def test_cold_start_serves_only_published_puzzle():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    ok = make_puzzle(db, CAPTURES, rating=1200.0)
    make_puzzle(db, CAPTURES, rating=1200.0, status=STATUS_DRAFT, published=False)
    user = make_user(db, "s1")
    got = rec.recommend_for_user(db, user.id)
    assert got is not None
    assert got.exercise_slug == CAPTURES
    assert got.puzzle_id == ok.id
    assert got.reason == rec.REASON_COLD_START
    assert got.assignment_id is None


def test_non_published_lifecycle_states_are_never_recommended():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    states = [
        (STATUS_DRAFT, False, False),
        (STATUS_VALIDATED, False, False),
        (STATUS_REVIEWED, False, False),
        (STATUS_APPROVED, False, False),
        (STATUS_QUARANTINED, False, False),
        (STATUS_REJECTED, False, False),
        (STATUS_RETIRED, False, True),
        (STATUS_PUBLISHED, True, True),  # archived projection of retired
    ]
    for status, published, archived in states:
        make_puzzle(db, UNDEFENDED, status=status, published=published, archived=archived)
    user = make_user(db, "s1")
    assert rec.eligible_puzzles(db, UNDEFENDED) == []
    assert rec.recommend_for_user(db, user.id) is None


def test_empty_catalog_returns_none():
    Session = make_db()
    db = Session()
    user = make_user(db, "s1")
    assert rec.recommend_for_user(db, user.id) is None


def test_disabled_exercise_yields_nothing():
    Session = make_db()
    db = Session()
    ensure_exercise(db, CAPTURES, active=False)
    make_puzzle(db, CAPTURES)
    user = make_user(db, "s1")
    assert rec.eligible_puzzles(db, CAPTURES) == []
    assert rec.recommend_for_user(db, user.id) is None


# --- skill / mastery matching -------------------------------------------------


def test_struggling_skill_outranks_cold_start():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    cap = make_puzzle(db, CAPTURES)
    make_puzzle(db, UNDEFENDED)
    user = make_user(db, "s1")
    attempt = add_attempt(db, user.id, cap, result="wrong")
    add_evidence(db, user.id, attempt, cap, "capture-finding",
                 direction="negative", key="neg")
    state = skill_state_service.skill_state_for_user(db, user.id)
    assert state.skills["capture-finding"].level == "struggling"
    got = rec.recommend_for_user(db, user.id)
    assert got is not None
    assert got.exercise_slug == CAPTURES
    assert got.reason == rec.REASON_WEAK_SKILL


def test_mastered_exercise_is_deprioritized_for_review():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    caps = [make_puzzle(db, CAPTURES, rating=1200.0) for _ in range(3)]
    fresh = make_puzzle(db, UNDEFENDED)
    user = make_user(db, "s1")
    for i in range(8):
        puzzle = caps[i % 3]
        attempt = add_attempt(db, user.id, puzzle, day=i)
        add_evidence(db, user.id, attempt, puzzle, "capture-finding",
                     day=i, difficulty=3 if i % 2 == 0 else 4, key=f"pos{i}")
    mastery = mastery_service.mastery_for_user(db, user.id)
    assert mastery["capture-finding"].status == "mastered"
    got = rec.recommend_for_user(db, user.id)
    assert got is not None
    assert got.exercise_slug == UNDEFENDED
    assert got.puzzle_id == fresh.id
    assert got.reason == rec.REASON_COLD_START


def test_insufficient_evidence_is_never_treated_as_mastered():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    cap = make_puzzle(db, CAPTURES)
    user = make_user(db, "s1")
    attempt = add_attempt(db, user.id, cap)
    add_evidence(db, user.id, attempt, cap, "capture-finding", key="one")
    mastery = mastery_service.mastery_for_user(db, user.id)
    assert mastery["capture-finding"].status == "emerging"
    got = rec.recommend_for_user(db, user.id)
    assert got is not None
    assert got.reason == rec.REASON_DEVELOPING_SKILL
    assert got.reason != rec.REASON_REVIEW_MASTERED


def test_review_mastered_when_everything_is_mastered():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    caps = [make_puzzle(db, CAPTURES) for _ in range(3)]
    unds = [make_puzzle(db, UNDEFENDED) for _ in range(3)]
    user = make_user(db, "s1")
    for i in range(8):
        for puzzles, skill in ((caps, "capture-finding"), (unds, "undefended-detection")):
            puzzle = puzzles[i % 3]
            attempt = add_attempt(db, user.id, puzzle, day=i)
            add_evidence(db, user.id, attempt, puzzle, skill,
                         day=i, difficulty=3 if i % 2 == 0 else 4,
                         key=f"{skill}:{i}")
    mastery = mastery_service.mastery_for_user(db, user.id)
    assert mastery["capture-finding"].status == "mastered"
    assert mastery["undefended-detection"].status == "mastered"
    got = rec.recommend_for_user(db, user.id)
    assert got is not None
    assert got.reason == rec.REASON_REVIEW_MASTERED


# --- puzzle rating / difficulty + external placement ---------------------------


def test_puzzle_pick_is_ability_relative():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    make_puzzle(db, CAPTURES, rating=1200.0)
    mid = make_puzzle(db, CAPTURES, rating=1500.0)
    make_puzzle(db, CAPTURES, rating=1800.0)
    user = make_user(db, "s1")
    db.add(PlayerRating(user_id=user.id, exercise_slug=CAPTURES, rating=1500.0,
                        rating_deviation=350.0, is_provisional=True, games_count=1))
    db.commit()
    got = rec.recommend_for_user(db, user.id)
    assert got is not None
    assert got.puzzle_id == mid.id
    assert got.trace["placement_used"] is False


def test_external_rating_is_placement_only_never_a_gate():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    make_puzzle(db, CAPTURES, rating=1200.0)
    hard = make_puzzle(db, CAPTURES, rating=1900.0)
    user = make_user(db, "s1")
    db.add(PlayerExternalIdentity(user_id=user.id, provider="lichess",
                                 external_username="s1", rating=1900))
    db.commit()
    got = rec.recommend_for_user(db, user.id)
    assert got is not None
    assert got.puzzle_id == hard.id
    assert got.trace["placement_used"] is True
    # Behavioral evidence outweighs the external signal once it exists.
    db.add(PlayerRating(user_id=user.id, exercise_slug=CAPTURES, rating=1200.0,
                        rating_deviation=350.0, is_provisional=True, games_count=1))
    db.commit()
    ability, placement_used = rec.ability_for(db, user.id, CAPTURES)
    assert (ability, placement_used) == (1200.0, False)


# --- history / repetition ------------------------------------------------------


def test_recent_puzzle_is_avoided_but_output_stays_deterministic():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    seen = make_puzzle(db, CAPTURES, rating=1200.0)
    fresh = make_puzzle(db, CAPTURES, rating=1200.0)
    user = make_user(db, "s1")
    add_attempt(db, user.id, seen)
    first = rec.recommend_for_user(db, user.id)
    second = rec.recommend_for_user(db, user.id)
    assert first is not None and second is not None
    assert first.puzzle_id == fresh.id
    assert first == second
    assert first.trace["fallback_recency"] is False


def test_recency_relaxes_when_everything_was_seen():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    old = make_puzzle(db, CAPTURES, rating=1200.0)
    new = make_puzzle(db, CAPTURES, rating=1200.0)
    user = make_user(db, "s1")
    add_attempt(db, user.id, old, day=0)
    add_attempt(db, user.id, new, day=1)
    got = rec.recommend_for_user(db, user.id)
    assert got is not None
    assert got.puzzle_id == old.id  # least recently attempted
    assert got.trace["fallback_recency"] is True


def test_speed_is_never_a_recommendation_signal():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    make_puzzle(db, CAPTURES, rating=1200.0)
    make_puzzle(db, UNDEFENDED, rating=1200.0)
    fast = make_user(db, "fast")
    slow = make_user(db, "slow")
    puzzles = db.query(Puzzle).order_by(Puzzle.id).all()
    for user, duration in ((fast, 500), (slow, 120000)):
        for puzzle in puzzles:
            add_attempt(db, user.id, puzzle, duration_ms=duration)
    assert rec.recommend_for_user(db, fast.id) == rec.recommend_for_user(db, slow.id)


# --- assignment override -------------------------------------------------------


def test_direct_assignment_overrides_the_engine():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    make_puzzle(db, CAPTURES)
    assigned_puzzle = make_puzzle(db, UNDEFENDED)
    coach, student = make_pair(db)
    # Engine alone would serve the struggling exercise...
    cap_attempt = add_attempt(db, student.id,
                             db.query(Puzzle).filter_by(exercise_slug=CAPTURES).one(),
                             result="wrong")
    add_evidence(db, student.id, cap_attempt,
                 db.query(Puzzle).filter_by(exercise_slug=CAPTURES).one(),
                 "capture-finding", direction="negative", key="neg")
    assert rec.recommend_for_user(db, student.id).exercise_slug == CAPTURES
    # ...but the open direct assignment wins.
    row = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=UNDEFENDED, note="drill"
    )
    got = rec.recommend_for_user(db, student.id)
    assert got is not None
    assert got.exercise_slug == UNDEFENDED
    assert got.puzzle_id == assigned_puzzle.id
    assert got.reason == rec.REASON_DIRECT_ASSIGNMENT
    assert got.assignment_id == row.id


def test_assignment_to_unservable_content_is_skipped_safely():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    engine_puzzle = make_puzzle(db, CAPTURES)
    coach, student = make_pair(db)
    row = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=UNDEFENDED, note="drill"
    )
    assert row.status == "assigned"
    # UNDEFENDED has no servable puzzle: the assignment is skipped and the
    # engine serves CAPTURES instead of retired content.
    got = rec.recommend_for_user(db, student.id)
    assert got is not None
    assert got.exercise_slug == CAPTURES
    assert got.puzzle_id == engine_puzzle.id
    assert got.reason != rec.REASON_DIRECT_ASSIGNMENT


def test_closed_assignment_no_longer_overrides():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    make_puzzle(db, CAPTURES)
    make_puzzle(db, UNDEFENDED)
    coach, student = make_pair(db)
    row = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=UNDEFENDED, note="drill"
    )
    relationship_service.update_assignment(
        db, actor=student, assignment_id=row.id, status="completed"
    )
    got = rec.recommend_for_user(db, student.id)
    assert got is not None
    assert got.reason != rec.REASON_DIRECT_ASSIGNMENT
    assert got.assignment_id is None


# --- isolation / read-only / determinism ---------------------------------------


def test_recommendations_are_isolated_per_user():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    make_puzzle(db, CAPTURES)
    make_puzzle(db, UNDEFENDED)
    u1 = make_user(db, "u1")
    u2 = make_user(db, "u2")
    cap = db.query(Puzzle).filter_by(exercise_slug=CAPTURES).one()
    attempt = add_attempt(db, u1.id, cap, result="wrong")
    add_evidence(db, u1.id, attempt, cap, "capture-finding",
                 direction="negative", key="neg")
    got1 = rec.recommend_for_user(db, u1.id)
    got2 = rec.recommend_for_user(db, u2.id)
    assert got1 is not None and got2 is not None
    assert got1.exercise_slug == CAPTURES
    assert got1.reason == rec.REASON_WEAK_SKILL
    assert got2.reason == rec.REASON_COLD_START


def test_recommendation_writes_nothing():
    Session = make_db()
    db = Session()
    seed_two_exercises(db)
    make_puzzle(db, CAPTURES)
    user = make_user(db, "s1")
    before = counts(db)
    first = rec.recommend_for_user(db, user.id)
    mid = counts(db)
    second = rec.recommend_for_user(db, user.id)
    after = counts(db)
    assert first is not None and first == second
    assert before == mid == after
