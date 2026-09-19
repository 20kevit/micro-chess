"""P6 — Assignment & Assessment.

Service-level tests (+ one thin HTTP passthrough test) over the
current architecture:

* Assignment: direct coach rows carry server-set ``source`` +
  optional ``goal``; lifecycle ``assigned -> completed | cancelled``
  unchanged (terminal states never reopen, idempotent same-state,
  history untouched). Direct assignments stay structurally separate
  from system recommendations (``adaptive_recommendations``).
* Attempt link: ``submit_attempt`` accepts optional ``assignment_id`` /
  ``assessment_id`` (server-validated ownership + openness,
  write-once, NULL for ordinary practice and all pre-P6 rows).
* Assessment: distinct evaluation sessions (``active -> completed |
  cancelled``), NOT practice renamed -- attempts keep their mode,
  validators, scoring, and rating/XP eligibility; the session only
  groups them via ``attempt.assessment_id``.
* Rating, evidence, skill state, and mastery are untouched (covered by
  their own suites; asserted here only as no-behavior-change).
* Migration v14: fresh stamp + legacy upgrade without backfill
  (except the factual ``source`` default on old assignment rows).

A stub exercise slug keeps these tests independent of real modules.
"""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.migration import (
    SCHEMA_VERSION,
    _migrate_v14_p6,
    ensure_schema,
    get_schema_version,
    import_models,
)
from app.modules.assessments import service as assessment_service
from app.modules.assessments.models import Assessment
from app.modules.exercises import registry
from app.modules.progress import service as attempt_service
from app.modules.progress.models import Attempt
from app.modules.puzzles.models import STATUS_PUBLISHED, Puzzle
from app.modules.relationships import service as relationship_service
from app.modules.relationships.models import Assignment
from app.modules.rule_engine.base import (
    AttemptMode,
    AttemptResult,
    ValidationResult,
)
from app.modules.users.models import User, UserRole

TEST_SLUG = "p6-assign"


def _correct_validator(puzzle_answer, attempt):
    return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct")


if registry.get_validator(TEST_SLUG) is None:
    registry.register_validator(TEST_SLUG, _correct_validator)


def make_db():
    import_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def make_user(db, username, roles=()):
    user = User(
        username=username,
        email=None,
        password_hash="h",
        display_name=username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    for role in roles:
        db.add(UserRole(user_id=user.id, role=role))
    db.commit()
    db.refresh(user)
    return user


def make_pair(db, coach_name="coach", student_name="student"):
    """Coach + student with an ACTIVE coach relationship."""
    coach = make_user(db, coach_name, roles=("COACH",))
    student = make_user(db, student_name)
    rel = relationship_service.create_relationship(
        db, actor=coach, kind="coach", other_username=student.username
    )
    relationship_service.accept_relationship(
        db, actor=student, relationship_id=rel.id
    )
    return coach, student


def make_puzzle(db, **overrides):
    fields = {
        "exercise_slug": TEST_SLUG,
        "fen": None,
        "position_json": {},
        "answer_json": {"squares": ["e4"]},
        "hint_json": {},
        "prompt_fa": "",
        "explanation": "",
        "initial_rating": 1450.0,
        "is_published": True,
        "is_archived": False,
        "status": STATUS_PUBLISHED,
        "source": "manual",
        "difficulty": 3,
        "target_rating": 1400.0,
    }
    fields.update(overrides)
    puzzle = Puzzle(**fields)
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    return puzzle


def submit(db, puzzle, user_id, **kwargs):
    kwargs.setdefault("mode", AttemptMode.PRACTICE)
    return attempt_service.submit_attempt(
        db, user_id=user_id, puzzle_id=puzzle.id, answer={"squares": ["e4"]}, **kwargs
    )


# --- assignment: source/goal + lifecycle --------------------------------------


def test_assignment_create_carries_source_goal_and_stays_direct():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    row = relationship_service.create_assignment(
        db,
        coach=coach,
        student_id=student.id,
        exercise_slug=TEST_SLUG,
        note="train this",
        goal="capture evaluation",
    )
    assert row.status == "assigned"
    assert row.source == "coach_direct"
    assert row.goal == "capture evaluation"
    assert row.note == "train this"
    assert row.coach_user_id == coach.id
    assert row.student_user_id == student.id
    # Goal is optional: omitted stays NULL, never an empty-string fact.
    plain = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    assert plain.goal is None
    assert plain.source == "coach_direct"
    db.close()


def test_assignment_lifecycle_unchanged_terminal_and_idempotent():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    row = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    # Student may complete their own assignment.
    done, changed = relationship_service.update_assignment(
        db, actor=student, assignment_id=row.id, status="completed"
    )
    assert changed is True and done.status == "completed"
    # Idempotent re-complete.
    done_again, changed_again = relationship_service.update_assignment(
        db, actor=student, assignment_id=row.id, status="completed"
    )
    assert changed_again is False
    # Terminal states never reopen.
    with pytest.raises(ValueError, match="invalid_transition"):
        relationship_service.update_assignment(
            db, actor=coach, assignment_id=row.id, status="assigned"
        )
    with pytest.raises(ValueError, match="invalid_transition"):
        relationship_service.update_assignment(
            db, actor=coach, assignment_id=row.id, status="cancelled"
        )
    # Student cannot cancel; coach can cancel an open one.
    second = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    with pytest.raises(ValueError, match="update_forbidden"):
        relationship_service.update_assignment(
            db, actor=student, assignment_id=second.id, status="cancelled"
        )
    cancelled, _ = relationship_service.update_assignment(
        db, actor=coach, assignment_id=second.id, status="cancelled"
    )
    assert cancelled.status == "cancelled"
    db.close()


def test_assignment_requires_active_relationship_and_revocation_blocks():
    Session = make_db()
    db = Session()
    coach = make_user(db, "coach", roles=("COACH",))
    student = make_user(db, "student")
    rel = relationship_service.create_relationship(
        db, actor=coach, kind="coach", other_username=student.username
    )
    # Pending grants nothing.
    with pytest.raises(ValueError, match="no_active_relationship"):
        relationship_service.create_assignment(
            db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
        )
    relationship_service.accept_relationship(db, actor=student, relationship_id=rel.id)
    relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    relationship_service.revoke_relationship(db, actor=coach, relationship_id=rel.id)
    with pytest.raises(ValueError, match="no_active_relationship"):
        relationship_service.create_assignment(
            db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
        )
    db.close()


def test_assignment_user_isolation():
    Session = make_db()
    db = Session()
    coach_a, student_a = make_pair(db, "coach_a", "student_a")
    coach_b, student_b = make_pair(db, "coach_b", "student_b")
    mine = relationship_service.create_assignment(
        db, coach=coach_a, student_id=student_a.id, exercise_slug=TEST_SLUG
    )
    theirs = relationship_service.create_assignment(
        db, coach=coach_b, student_id=student_b.id, exercise_slug=TEST_SLUG
    )
    # Coach A sees only their own rows.
    assert [r.id for r in relationship_service.list_assignments_for_coach(db, coach_a)] == [mine.id]
    # Students see only their own rows.
    assert [r.id for r in relationship_service.list_assignments_for_student(db, student_a)] == [mine.id]
    assert [r.id for r in relationship_service.list_assignments_for_student(db, student_b)] == [theirs.id]
    # Object-level: outsiders resolve to None (callers map to 404).
    assert relationship_service.get_assignment(db, coach_b, mine.id) is None
    assert relationship_service.get_assignment(db, student_b, mine.id) is None
    assert relationship_service.get_assignment(db, coach_a, mine.id) is not None
    # Cross-coach completion resolves to None (party-scoped; callers map to 404).
    assert (
        relationship_service.update_assignment(
            db, actor=coach_b, assignment_id=mine.id, status="completed"
        )
        is None
    )
    db.close()


# --- assignment -> attempt link -------------------------------------------------


def test_exact_assignment_link_and_practice_default():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    puzzle = make_puzzle(db)
    assignment = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    linked, _, _ = submit(db, puzzle, student.id, assignment_id=assignment.id)
    assert linked.assignment_id == assignment.id
    assert linked.assessment_id is None
    # Ordinary practice carries no context.
    plain, _, _ = submit(db, puzzle, student.id)
    assert plain.assignment_id is None
    assert plain.assessment_id is None
    db.close()


def test_assignment_link_rejects_unknown_foreign_and_closed():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    _, other_student = make_pair(db, "coach_b", "other")
    puzzle = make_puzzle(db)
    before = db.query(Attempt).count()
    with pytest.raises(ValueError, match="assignment_not_available"):
        submit(db, puzzle, student.id, assignment_id=9999)
    # A genuinely foreign assignment via the other pair.
    coach_b = db.query(User).filter(User.username == "coach_b").one()
    foreign = relationship_service.create_assignment(
        db, coach=coach_b, student_id=other_student.id, exercise_slug=TEST_SLUG
    )
    with pytest.raises(ValueError, match="assignment_not_available"):
        submit(db, puzzle, student.id, assignment_id=foreign.id)
    mine = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    relationship_service.update_assignment(
        db, actor=coach, assignment_id=mine.id, status="cancelled"
    )
    with pytest.raises(ValueError, match="assignment_not_available"):
        submit(db, puzzle, student.id, assignment_id=mine.id)
    done = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    relationship_service.update_assignment(
        db, actor=student, assignment_id=done.id, status="completed"
    )
    with pytest.raises(ValueError, match="assignment_not_available"):
        submit(db, puzzle, student.id, assignment_id=done.id)
    # Rejected links persist nothing.
    assert db.query(Attempt).count() == before
    db.close()


def test_completing_assignment_preserves_attempts():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    puzzle = make_puzzle(db)
    assignment = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    linked, _, _ = submit(db, puzzle, student.id, assignment_id=assignment.id)
    relationship_service.update_assignment(
        db, actor=student, assignment_id=assignment.id, status="completed"
    )
    reread = db.get(Attempt, linked.id)
    assert reread.assignment_id == assignment.id
    assert reread.result == "correct"
    db.close()


# --- assessment lifecycle -------------------------------------------------------


def test_assessment_create_complete_by_coach_and_student():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    row = assessment_service.create_assessment(
        db, creator=coach, student_id=student.id, note="midterm"
    )
    assert row.status == "active"
    assert row.student_user_id == student.id
    assert row.created_by_user_id == coach.id
    assert row.assignment_id is None
    assert row.note == "midterm"
    # The student can complete; idempotent re-complete.
    done, changed = assessment_service.complete_assessment(
        db, actor=student, assessment_id=row.id
    )
    assert changed is True and done.status == "completed"
    assert done.completed_at is not None
    done_again, changed_again = assessment_service.complete_assessment(
        db, actor=student, assessment_id=row.id
    )
    assert changed_again is False
    # Terminal states never reopen.
    with pytest.raises(ValueError, match="invalid_transition"):
        assessment_service.cancel_assessment(db, actor=coach, assessment_id=row.id)
    db.close()


def test_assessment_self_create_and_cancel():
    Session = make_db()
    db = Session()
    _, student = make_pair(db)
    row = assessment_service.create_assessment(db, creator=student, student_id=student.id)
    assert row.status == "active"
    cancelled, _ = assessment_service.cancel_assessment(
        db, actor=student, assessment_id=row.id
    )
    assert cancelled.status == "cancelled"
    with pytest.raises(ValueError, match="invalid_transition"):
        assessment_service.complete_assessment(db, actor=student, assessment_id=row.id)
    db.close()


def test_assessment_creation_authorization():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db, "coach", "student")
    stranger_coach = make_user(db, "stranger", roles=("COACH",))
    plain = make_user(db, "plain")
    parent = make_user(db, "parent", roles=("PARENT",))
    # Unrelated coach, plain user, and parent cannot open sessions for the student.
    for actor in (stranger_coach, plain, parent):
        with pytest.raises(ValueError, match="assessment_forbidden"):
            assessment_service.create_assessment(
                db, creator=actor, student_id=student.id
            )
    # Unknown or inactive students are rejected.
    with pytest.raises(ValueError, match="unknown_student"):
        assessment_service.create_assessment(db, creator=coach, student_id=9999)
    # Reads are party-scoped (outsiders resolve to None).
    row = assessment_service.create_assessment(db, creator=coach, student_id=student.id)
    assert assessment_service.get_assessment(db, stranger_coach, row.id) is None
    assert assessment_service.get_assessment(db, plain, row.id) is None
    assert assessment_service.get_assessment(db, coach, row.id) is not None
    assert assessment_service.get_assessment(db, student, row.id) is not None
    # Coach lists only created sessions; student lists own.
    assert [r.id for r in assessment_service.list_created_by(db, coach)] == [row.id]
    assert assessment_service.list_created_by(db, stranger_coach) == []
    assert [r.id for r in assessment_service.list_for_student(db, student)] == [row.id]
    db.close()


def test_revoked_relationship_blocks_new_assessments():
    Session = make_db()
    db = Session()
    coach = make_user(db, "coach", roles=("COACH",))
    student = make_user(db, "student")
    rel = relationship_service.create_relationship(
        db, actor=coach, kind="coach", other_username=student.username
    )
    relationship_service.accept_relationship(db, actor=student, relationship_id=rel.id)
    assessment_service.create_assessment(db, creator=coach, student_id=student.id)
    relationship_service.revoke_relationship(db, actor=coach, relationship_id=rel.id)
    with pytest.raises(ValueError, match="assessment_forbidden"):
        assessment_service.create_assessment(db, creator=coach, student_id=student.id)
    # Self-assessment needs no relationship and still works.
    own = assessment_service.create_assessment(db, creator=student, student_id=student.id)
    assert own.status == "active"
    db.close()


def test_assessment_with_assignment_context():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db, "coach", "student")
    other_coach, _ = make_pair(db, "other_coach", "other_student")
    assignment = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    row = assessment_service.create_assessment(
        db, creator=coach, student_id=student.id, assignment_id=assignment.id
    )
    assert row.assignment_id == assignment.id
    # Another coach cannot execute someone else's assignment.
    with pytest.raises(ValueError, match="assessment_forbidden"):
        assessment_service.create_assessment(
            db, creator=other_coach, student_id=student.id, assignment_id=assignment.id
        )
    # Unknown assignments are rejected.
    with pytest.raises(ValueError, match="unknown_assignment"):
        assessment_service.create_assessment(
            db, creator=coach, student_id=student.id, assignment_id=9999
        )
    # Closed assignments accept no new sessions.
    relationship_service.update_assignment(
        db, actor=coach, assignment_id=assignment.id, status="cancelled"
    )
    with pytest.raises(ValueError, match="assessment_forbidden"):
        assessment_service.create_assessment(
            db, creator=coach, student_id=student.id, assignment_id=assignment.id
        )
    db.close()


# --- assessment -> attempt link + practice separation ----------------------------


def test_assessment_attempt_link_and_practice_separation():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    puzzle = make_puzzle(db)
    session = assessment_service.create_assessment(
        db, creator=coach, student_id=student.id
    )
    linked, _, _ = submit(db, puzzle, student.id, assessment_id=session.id)
    assert linked.assessment_id == session.id
    assert linked.assignment_id is None
    # Assessment is a grouping context, not a mode: practice stays practice.
    assert linked.mode == "practice"
    assert linked.rating_delta is None
    # The session's attempts are exactly queryable.
    ids = {
        a.id
        for a in db.query(Attempt).filter(Attempt.assessment_id == session.id).all()
    }
    assert ids == {linked.id}
    # Plain practice stays unlinked.
    plain, _, _ = submit(db, puzzle, student.id)
    assert plain.assessment_id is None
    db.close()


def test_assessment_attempt_keeps_mode_rating_rules_unchanged():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    puzzle = make_puzzle(db)
    session = assessment_service.create_assessment(
        db, creator=coach, student_id=student.id
    )
    # Rated mode still rates inside an assessment (rating untouched by P6).
    rated, _, _ = submit(
        db, puzzle, student.id, mode=AttemptMode.RATED, assessment_id=session.id
    )
    assert rated.rating_delta is not None
    assert rated.rating_after == rated.rating_before + rated.rating_delta
    db.close()


def test_assessment_link_rejects_unknown_foreign_and_closed():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    _, other = make_pair(db, "coach_b", "other")
    puzzle = make_puzzle(db)
    before = db.query(Attempt).count()
    with pytest.raises(ValueError, match="assessment_not_available"):
        submit(db, puzzle, student.id, assessment_id=9999)
    foreign = assessment_service.create_assessment(db, creator=other, student_id=other.id)
    with pytest.raises(ValueError, match="assessment_not_available"):
        submit(db, puzzle, student.id, assessment_id=foreign.id)
    mine = assessment_service.create_assessment(db, creator=coach, student_id=student.id)
    assessment_service.complete_assessment(db, actor=student, assessment_id=mine.id)
    with pytest.raises(ValueError, match="assessment_not_available"):
        submit(db, puzzle, student.id, assessment_id=mine.id)
    assert db.query(Attempt).count() == before
    db.close()


def test_closing_assessment_preserves_attempts():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    puzzle = make_puzzle(db)
    session = assessment_service.create_assessment(
        db, creator=coach, student_id=student.id
    )
    linked, _, _ = submit(db, puzzle, student.id, assessment_id=session.id)
    assessment_service.complete_assessment(db, actor=coach, assessment_id=session.id)
    reread = db.get(Attempt, linked.id)
    assert reread.assessment_id == session.id
    db.close()


def test_combined_assignment_and_assessment_link():
    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    puzzle = make_puzzle(db)
    assignment = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    session = assessment_service.create_assessment(
        db, creator=coach, student_id=student.id, assignment_id=assignment.id
    )
    attempt, _, _ = submit(
        db, puzzle, student.id, assignment_id=assignment.id, assessment_id=session.id
    )
    assert attempt.assignment_id == assignment.id
    assert attempt.assessment_id == session.id
    db.close()


# --- separation + idempotency -----------------------------------------------------


def test_direct_work_stays_separate_from_recommendations():
    """Assignments/assessments never fabricate recommendation rows."""
    from app.modules.adaptive.models import AdaptiveRecommendation

    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    assignment = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    assessment_service.create_assessment(
        db, creator=coach, student_id=student.id, assignment_id=assignment.id
    )
    assert assignment.source == "coach_direct"
    assert db.query(AdaptiveRecommendation).count() == 0
    assert not hasattr(assignment, "recommendation_id")
    db.close()


def test_close_operations_are_idempotent_without_duplication():
    from app.modules.admin.models import AuditLog

    Session = make_db()
    db = Session()
    coach, student = make_pair(db)
    assignment = relationship_service.create_assignment(
        db, coach=coach, student_id=student.id, exercise_slug=TEST_SLUG
    )
    first, changed_first = relationship_service.update_assignment(
        db, actor=coach, assignment_id=assignment.id, status="completed"
    )
    second, changed_second = relationship_service.update_assignment(
        db, actor=coach, assignment_id=assignment.id, status="completed"
    )
    assert changed_first is True and changed_second is False
    assert first.id == second.id
    session = assessment_service.create_assessment(
        db, creator=coach, student_id=student.id
    )
    _, changed = assessment_service.cancel_assessment(
        db, actor=coach, assessment_id=session.id
    )
    _, unchanged = assessment_service.cancel_assessment(
        db, actor=coach, assessment_id=session.id
    )
    assert changed is True and unchanged is False
    assert db.query(Assessment).count() == 1
    assert db.query(Assignment).count() == 1
    # Sensitive transitions stay audited.
    actions = {row.action for row in db.query(AuditLog).all()}
    assert "assessments.create" in actions
    assert "assessments.update" in actions
    assert "assignments.create" in actions
    assert "assignments.update" in actions
    db.close()


# --- thin HTTP passthrough (only what the phase really needs) --------------------


def test_attempt_api_accepts_and_reports_p6_context(client, db_session):
    from app.modules.puzzles.models import Puzzle as PuzzleModel
    from app.modules.users.models import User as UserModel
    from app.modules.users.models import UserRole as UserRoleModel

    def _register(username):
        res = client.post(
            "/api/v1/auth/register", json={"username": username, "password": "secret123"}
        )
        assert res.status_code == 201, res.text
        return res.json()["access_token"]

    def _bearer(token):
        return {"Authorization": f"Bearer {token}"}

    coach_token = _register("p6_coach")
    student_token = _register("p6_student")
    coach = db_session.query(UserModel).filter(UserModel.username == "p6_coach").one()
    db_session.add(UserRoleModel(user_id=coach.id, role="COACH"))
    db_session.commit()
    rel = client.post(
        "/api/v1/relationships",
        json={"kind": "coach", "other_username": "p6_student"},
        headers=_bearer(coach_token),
    )
    assert rel.status_code == 201, rel.text
    accept = client.post(
        f"/api/v1/relationships/{rel.json()['id']}/accept", headers=_bearer(student_token)
    )
    assert accept.status_code == 200, accept.text
    student = db_session.query(UserModel).filter(UserModel.username == "p6_student").one()

    created = client.post(
        "/api/v1/coach/assignments",
        json={"student_id": student.id, "exercise_slug": "piece-recognition", "goal": "board literacy"},
        headers=_bearer(coach_token),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["source"] == "coach_direct"
    assert body["goal"] == "board literacy"

    from app.modules.piece_recognition import seed as seed_mod

    seed_mod.seed_db(db_session)
    puzzle = (
        db_session.query(PuzzleModel)
        .filter(PuzzleModel.exercise_slug == "piece-recognition")
        .order_by(PuzzleModel.id)
        .first()
    )
    answer = {"selected_squares": list(puzzle.answer_json["squares"])}

    assessment = assessment_service.create_assessment(
        db_session, creator=coach, student_id=student.id
    )
    ok = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": puzzle.id,
            "answer": answer,
            "mode": "practice",
            "assignment_id": body["id"],
            "assessment_id": assessment.id,
        },
        headers=_bearer(student_token),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["assignment_id"] == body["id"]
    assert ok.json()["assessment_id"] == assessment.id

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": answer, "mode": "practice", "assignment_id": 9999},
        headers=_bearer(student_token),
    )
    assert bad.status_code == 404
    assert bad.json()["detail"] == "assignment_not_available"


# --- migration --------------------------------------------------------------------


def test_fresh_boot_stamps_v14_with_p6_tables():
    engine = create_engine("sqlite:///:memory:")
    version = ensure_schema(engine)
    assert version == SCHEMA_VERSION == 14
    assert get_schema_version(engine) == 14
    tables = set(inspect(engine).get_table_names())
    assert "assessments" in tables
    attempt_cols = {c["name"] for c in inspect(engine).get_columns("attempts")}
    assert {"assignment_id", "assessment_id"} <= attempt_cols
    assignment_cols = {c["name"] for c in inspect(engine).get_columns("assignments")}
    assert {"source", "goal"} <= assignment_cols
    # Idempotent re-run.
    assert ensure_schema(engine) == 14


def test_v14_migration_preserves_legacy_rows_without_backfill():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE assignments (id INTEGER PRIMARY KEY, student_user_id INTEGER)")
        )
        conn.execute(text("INSERT INTO assignments (id, student_user_id) VALUES (1, 7)"))
        conn.execute(
            text("CREATE TABLE attempts (id INTEGER PRIMARY KEY, puzzle_id INTEGER)")
        )
        conn.execute(text("INSERT INTO attempts (id, puzzle_id) VALUES (1, 10)"))
        _migrate_v14_p6(conn)
    with engine.connect() as conn:
        assignment_cols = {c["name"] for c in inspect(conn).get_columns("assignments")}
        assert {"source", "goal"} <= assignment_cols
        attempt_cols = {c["name"] for c in inspect(conn).get_columns("attempts")}
        assert {"assignment_id", "assessment_id"} <= attempt_cols
        row = conn.execute(
            text("SELECT student_user_id, source, goal FROM assignments")
        ).first()
        # Pre-P6 rows were all coach-direct by construction (only writer).
        assert row[0] == 7 and row[1] == "coach_direct" and row[2] is None
        attempt = conn.execute(
            text("SELECT puzzle_id, assignment_id, assessment_id FROM attempts")
        ).first()
        assert attempt == (10, None, None)
    # Idempotent re-run on the upgraded tables.
    with engine.begin() as conn:
        _migrate_v14_p6(conn)
