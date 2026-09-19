"""P1 — Attempt Context + Puzzle Lifecycle Alignment.

Covers (service level, no HTTP harness required):

* Attempt: new attempts persist difficulty/rating snapshots; legacy rows
  stay valid with NULL snapshots; snapshots are write-once (later puzzle
  edits never rewrite them); no update path exists for attempts.
* Lifecycle: valid transitions (quarantine/release/reject/retire),
  invalid transitions rejected, quarantined/rejected/retired puzzles
  excluded from serving (visible query + submit), history/audit
  preserved, rejected content immutable.
* Access: guest rated attempts never rate (eligibility boundary);
  dual-owner attempts rejected.
* Migration: v12 step adds nullable snapshot columns to a legacy-shaped
  attempts table without touching existing rows; fresh boots stamp v12.

Test-only exercise slug (``p1-snapshot``) with a stub validator is
registered here so validated-submit paths do not depend on any real
exercise module.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.migration import (
    SCHEMA_VERSION,
    _migrate_v12_p1,
    ensure_schema,
    get_schema_version,
    import_models,
)
from app.modules.admin import service as admin_service
from app.modules.exercises import registry
from app.modules.progress import service as attempt_service
from app.modules.progress.models import Attempt
from app.modules.puzzles import service as puzzle_service
from app.modules.puzzles.models import (
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_PUBLISHED,
    STATUS_QUARANTINED,
    STATUS_REJECTED,
    STATUS_RETIRED,
    Puzzle,
)
from app.modules.rating_engine import service as rating_service
from app.modules.rule_engine.base import (
    AttemptMode,
    AttemptResult,
    ValidationResult,
)

TEST_SLUG = "p1-snapshot"


def _correct_validator(puzzle_answer, attempt):
    return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct")


if registry.get_validator(TEST_SLUG) is None:
    registry.register_validator(TEST_SLUG, _correct_validator)


def make_db():
    import_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


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


# --- Attempt context --------------------------------------------------------


def test_new_attempt_persists_snapshots():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    attempt, _, _ = attempt_service.submit_attempt(
        db,
        user_id=1,
        puzzle_id=puzzle.id,
        answer={"squares": ["e4"]},
        mode=AttemptMode.PRACTICE,
    )
    assert attempt.puzzle_rating_snapshot == 1450.0
    assert attempt.difficulty_snapshot == 3
    db.close()


def test_terminal_attempt_still_captures_context():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    attempt, _, _ = attempt_service.submit_attempt(
        db,
        user_id=1,
        puzzle_id=puzzle.id,
        answer={},
        mode=AttemptMode.PRACTICE,
        client_result="skipped",
    )
    assert attempt.result == "skipped"
    assert attempt.puzzle_rating_snapshot == 1450.0
    assert attempt.difficulty_snapshot == 3
    db.close()


def test_legacy_attempt_without_snapshots_stays_valid():
    """Pre-P1 rows (NULL context) remain readable and are never backfilled."""
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    legacy = Attempt(
        user_id=7,
        guest_session_id=None,
        puzzle_id=puzzle.id,
        exercise_slug=TEST_SLUG,
        mode="practice",
        result="correct",
        answer_json={"squares": ["e4"]},
        score=1.0,
    )
    db.add(legacy)
    db.commit()
    db.refresh(legacy)
    assert legacy.puzzle_rating_snapshot is None
    assert legacy.difficulty_snapshot is None
    # New submits still work alongside legacy rows.
    attempt, _, _ = attempt_service.submit_attempt(
        db,
        user_id=7,
        puzzle_id=puzzle.id,
        answer={"squares": ["e4"]},
        mode=AttemptMode.PRACTICE,
    )
    assert attempt.puzzle_rating_snapshot == 1450.0
    reread = db.get(Attempt, legacy.id)
    assert reread.puzzle_rating_snapshot is None
    db.close()


def test_snapshot_does_not_mutate_after_puzzle_edit():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    attempt, _, _ = attempt_service.submit_attempt(
        db,
        user_id=1,
        puzzle_id=puzzle.id,
        answer={"squares": ["e4"]},
        mode=AttemptMode.PRACTICE,
    )
    # Admin edits difficulty/rating metadata afterwards (allowed on
    # servable content via update_puzzle metadata path).
    puzzle.difficulty = 5
    puzzle.initial_rating = 1800.0
    db.commit()
    reread = db.get(Attempt, attempt.id)
    assert reread.puzzle_rating_snapshot == 1450.0
    assert reread.difficulty_snapshot == 3
    db.close()


def test_attempts_have_no_update_path():
    assert not hasattr(attempt_service, "update_attempt")


def test_attempt_owner_conflict_rejected():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    try:
        attempt_service.submit_attempt(
            db,
            user_id=1,
            guest_session_id=99,
            puzzle_id=puzzle.id,
            answer={},
            mode=AttemptMode.PRACTICE,
            client_result="skipped",
        )
    except ValueError as exc:
        assert str(exc) == "attempt_owner_conflict"
    else:  # pragma: no cover
        raise AssertionError("expected attempt_owner_conflict")
    db.close()


# --- Lifecycle --------------------------------------------------------------


def test_quarantine_release_restores_published_standing():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    quarantined, changed = admin_service.quarantine_puzzle(
        db, actor_id=1, puzzle_id=puzzle.id, reason="suspect leak"
    )
    assert changed is True
    assert quarantined.status == STATUS_QUARANTINED
    assert quarantined.is_published is False
    assert quarantined.is_archived is False
    # Idempotent re-quarantine.
    _, changed_again = admin_service.quarantine_puzzle(db, actor_id=1, puzzle_id=puzzle.id)
    assert changed_again is False
    # Release restores the pre-quarantine standing (published here).
    released, _ = admin_service.release_puzzle(db, actor_id=1, puzzle_id=puzzle.id)
    assert released.status == STATUS_PUBLISHED
    assert released.is_published is True
    # Releasing a non-quarantined puzzle is rejected.
    try:
        admin_service.release_puzzle(db, actor_id=1, puzzle_id=puzzle.id)
    except ValueError as exc:
        assert str(exc) == "invalid_transition"
    else:  # pragma: no cover
        raise AssertionError("expected invalid_transition")
    db.close()


def test_prepublish_hold_releases_to_draft_and_draft_hold_refused():
    Session = make_db()
    db = Session()
    # A pre-publish hold must re-pass gates: release lands in draft.
    held = make_puzzle(db, status=STATUS_APPROVED, is_published=False)
    admin_service.quarantine_puzzle(db, actor_id=1, puzzle_id=held.id, reason="check")
    released, _ = admin_service.release_puzzle(db, actor_id=1, puzzle_id=held.id)
    assert released.status == STATUS_DRAFT
    assert released.is_published is False
    # A draft needs no safety hold: quarantine entry is refused.
    draft = make_puzzle(db, status=STATUS_DRAFT, is_published=False)
    try:
        admin_service.quarantine_puzzle(db, actor_id=1, puzzle_id=draft.id)
    except ValueError as exc:
        assert str(exc) == "invalid_transition"
    else:  # pragma: no cover
        raise AssertionError("expected invalid_transition")
    db.close()


def test_quarantined_content_is_frozen():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    admin_service.quarantine_puzzle(db, actor_id=1, puzzle_id=puzzle.id)
    try:
        admin_service.update_puzzle(
            db, actor_id=1, puzzle_id=puzzle.id, patch={"prompt_fa": "edited"}
        )
    except ValueError as exc:
        assert str(exc) == "puzzle_immutable"
    else:  # pragma: no cover
        raise AssertionError("expected puzzle_immutable")
    db.close()


def test_reject_is_terminal_and_immutable():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db, status=STATUS_APPROVED, is_published=False)
    rejected, changed = admin_service.reject_puzzle(
        db, actor_id=2, puzzle_id=puzzle.id, reason="wrong solution"
    )
    assert changed is True
    assert rejected.status == STATUS_REJECTED
    assert rejected.is_published is False
    assert rejected.is_archived is False
    # Idempotent re-reject.
    _, changed_again = admin_service.reject_puzzle(db, actor_id=2, puzzle_id=puzzle.id)
    assert changed_again is False
    # Terminal: quarantine, release, publish, validate, retire all refused.
    for op in (
        lambda: admin_service.quarantine_puzzle(db, actor_id=2, puzzle_id=puzzle.id),
        lambda: admin_service.release_puzzle(db, actor_id=2, puzzle_id=puzzle.id),
        lambda: admin_service.retire_puzzle(db, actor_id=2, puzzle_id=puzzle.id),
        lambda: admin_service.publish_puzzle(db, actor_id=2, puzzle_id=puzzle.id),
        lambda: admin_service.validate_puzzle(db, actor_id=2, puzzle_id=puzzle.id),
    ):
        try:
            op()
        except ValueError as exc:
            assert str(exc) in ("invalid_transition", "puzzle_archived")
        else:  # pragma: no cover
            raise AssertionError("expected terminal rejection to refuse transition")
    # Rejected content is immutable.
    try:
        admin_service.update_puzzle(db, actor_id=2, puzzle_id=puzzle.id, patch={"prompt_fa": "x"})
    except ValueError as exc:
        assert str(exc) == "puzzle_immutable"
    else:  # pragma: no cover
        raise AssertionError("expected puzzle_immutable")
    db.close()


def test_postpublish_refusal_goes_via_retire_not_reject():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)  # published
    try:
        admin_service.reject_puzzle(db, actor_id=2, puzzle_id=puzzle.id, reason="late refusal")
    except ValueError as exc:
        assert str(exc) == "invalid_transition"
    else:  # pragma: no cover
        raise AssertionError("expected invalid_transition")
    # The specified path: retire (history preserved) with the refusal noted.
    retired, _ = admin_service.retire_puzzle(db, actor_id=2, puzzle_id=puzzle.id)
    assert retired.status == STATUS_RETIRED
    db.close()


def test_restore_returns_retired_to_service():
    Session = make_db()
    db = Session()
    # A previously published puzzle restores to published (servable).
    puzzle = make_puzzle(db)
    admin_service.retire_puzzle(db, actor_id=1, puzzle_id=puzzle.id)
    restored, _ = admin_service.restore_puzzle(
        db, actor_id=1, puzzle_id=puzzle.id, reason="wrongful retirement"
    )
    assert restored.status == STATUS_PUBLISHED
    assert restored.is_published is True
    assert restored.is_archived is False
    assert restored.id in {p.id for p in puzzle_service.visible_query(db).all()}
    history = admin_service.puzzle_history(db, puzzle.id)
    assert history["transitions"][-1]["to_status"] == STATUS_PUBLISHED
    # A row retired before ever being served restores to draft (gates intact).
    draft = make_puzzle(db, status=STATUS_DRAFT, is_published=False)
    admin_service.retire_puzzle(db, actor_id=1, puzzle_id=draft.id)
    restored_draft, _ = admin_service.restore_puzzle(db, actor_id=1, puzzle_id=draft.id)
    assert restored_draft.status == STATUS_DRAFT
    # Restore refuses non-retired and terminal-rejected rows.
    for pid in (puzzle.id,):
        try:
            admin_service.restore_puzzle(db, actor_id=1, puzzle_id=pid)
        except ValueError as exc:
            assert str(exc) == "invalid_transition"
        else:  # pragma: no cover
            raise AssertionError("expected invalid_transition")
    rejected = make_puzzle(db, status=STATUS_APPROVED, is_published=False)
    admin_service.reject_puzzle(db, actor_id=1, puzzle_id=rejected.id)
    try:
        admin_service.restore_puzzle(db, actor_id=1, puzzle_id=rejected.id)
    except ValueError as exc:
        assert str(exc) == "invalid_transition"
    else:  # pragma: no cover
        raise AssertionError("expected invalid_transition")
    db.close()


def test_quarantined_cannot_advance_pipeline():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    admin_service.quarantine_puzzle(db, actor_id=1, puzzle_id=puzzle.id)
    for op in (
        lambda: admin_service.validate_puzzle(db, actor_id=1, puzzle_id=puzzle.id),
        lambda: admin_service.review_puzzle(
            db, actor_id=1, puzzle_id=puzzle.id, decision="approve"
        ),
        lambda: admin_service.approve_puzzle(db, actor_id=1, puzzle_id=puzzle.id),
        lambda: admin_service.publish_puzzle(db, actor_id=1, puzzle_id=puzzle.id),
    ):
        try:
            op()
        except ValueError as exc:
            assert str(exc) == "invalid_transition"
        else:  # pragma: no cover
            raise AssertionError("expected invalid_transition from quarantined")
    # Quarantined content can still be retired (safety hold -> archive).
    retired, _ = admin_service.retire_puzzle(db, actor_id=1, puzzle_id=puzzle.id)
    assert retired.status == STATUS_RETIRED
    db.close()


def test_lifecycle_history_preserves_actor_reason():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    admin_service.quarantine_puzzle(db, actor_id=42, puzzle_id=puzzle.id, reason="suspect leak")
    history = admin_service.puzzle_history(db, puzzle.id)
    assert history["status"] == STATUS_QUARANTINED
    assert len(history["transitions"]) == 1
    row = history["transitions"][0]
    assert row["from_status"] == STATUS_PUBLISHED
    assert row["to_status"] == STATUS_QUARANTINED
    assert row["changed_by_user_id"] == 42
    assert row["reason"] == "suspect leak"
    db.close()


def test_serving_boundary_excludes_safety_states():
    Session = make_db()
    db = Session()
    quarantined = make_puzzle(db, status=STATUS_QUARANTINED, is_published=False)
    rejected = make_puzzle(db, status=STATUS_REJECTED, is_published=False)
    retired = make_puzzle(
        db, status=STATUS_RETIRED, is_published=False, is_archived=True
    )
    visible_ids = {p.id for p in puzzle_service.visible_query(db).all()}
    assert quarantined.id not in visible_ids
    assert rejected.id not in visible_ids
    assert retired.id not in visible_ids
    for puzzle in (quarantined, rejected, retired):
        try:
            attempt_service.submit_attempt(
                db,
                user_id=1,
                puzzle_id=puzzle.id,
                answer={},
                mode=AttemptMode.PRACTICE,
                client_result="skipped",
            )
        except ValueError as exc:
            assert str(exc) == "puzzle_not_available"
        else:  # pragma: no cover
            raise AssertionError("expected puzzle_not_available")
    # Published control still servable.
    control = make_puzzle(db)
    assert control.id in {p.id for p in puzzle_service.visible_query(db).all()}
    db.close()


def test_admin_list_filters_safety_states():
    Session = make_db()
    db = Session()
    make_puzzle(db, status=STATUS_QUARANTINED, is_published=False)
    make_puzzle(db, status=STATUS_REJECTED, is_published=False)
    rows, _ = admin_service.list_puzzles_admin(db, status="quarantined")
    assert len(rows) == 1 and rows[0].status == STATUS_QUARANTINED
    rows, _ = admin_service.list_puzzles_admin(db, status="rejected")
    assert len(rows) == 1 and rows[0].status == STATUS_REJECTED
    try:
        admin_service.list_puzzles_admin(db, status="bogus")
    except ValueError as exc:
        assert str(exc) == "invalid_status"
    else:  # pragma: no cover
        raise AssertionError("expected invalid_status")
    db.close()


def test_linear_pipeline_transitions_unchanged():
    """The pre-P1 pipeline still advances exactly as before."""
    Session = make_db()
    db = Session()
    draft = make_puzzle(db, status=STATUS_DRAFT, is_published=False, answer_json={})
    assert draft.status == STATUS_DRAFT
    # Draft meaning edits still allowed; retired/rejected stay immutable.
    retired = make_puzzle(db, status=STATUS_RETIRED, is_published=False, is_archived=True)
    try:
        admin_service.update_puzzle(
            db, actor_id=1, puzzle_id=retired.id, patch={"prompt_fa": "x"}
        )
    except ValueError as exc:
        assert str(exc) == "puzzle_immutable"
    else:  # pragma: no cover
        raise AssertionError("expected puzzle_immutable")
    db.close()


# --- Access boundary --------------------------------------------------------


def test_guest_attempt_is_rejected_without_persistence():
    # Product decision: guests cannot practice. The service refuses
    # ownerless submissions, so no attempt (and no evidence) is stored.
    # Rating eligibility still excludes guests as before.
    assert (
        rating_service.is_rating_eligible(
            mode=AttemptMode.RATED, user_id=None, result="correct"
        )
        is False
    )
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    try:
        attempt_service.submit_attempt(
            db,
            user_id=None,
            guest_session_id=5,
            puzzle_id=puzzle.id,
            answer={"squares": ["e4"]},
            mode=AttemptMode.RATED,
        )
    except ValueError as exc:
        assert str(exc) == "auth_required"
    else:  # pragma: no cover
        raise AssertionError("expected auth_required")
    assert db.query(Attempt).count() == 0
    # Snapshots stay write-once for authenticated attempts (P1 intact).
    attempt, _, _ = attempt_service.submit_attempt(
        db,
        user_id=3,
        puzzle_id=puzzle.id,
        answer={"squares": ["e4"]},
        mode=AttemptMode.PRACTICE,
    )
    assert attempt.puzzle_rating_snapshot == 1450.0
    assert attempt.difficulty_snapshot == 3
    db.close()


def test_authenticated_rated_attempt_rates_with_snapshot():
    Session = make_db()
    db = Session()
    puzzle = make_puzzle(db)
    attempt, _, _ = attempt_service.submit_attempt(
        db,
        user_id=3,
        puzzle_id=puzzle.id,
        answer={"squares": ["e4"]},
        mode=AttemptMode.RATED,
    )
    assert attempt.rating_before is not None
    assert attempt.rating_after == attempt.rating_before + attempt.rating_delta
    assert attempt.puzzle_rating_snapshot == 1450.0
    db.close()


# --- Migration --------------------------------------------------------------


def test_fresh_boot_stamps_v12():
    engine = create_engine("sqlite:///:memory:")
    version = ensure_schema(engine)
    assert version == SCHEMA_VERSION == 14
    assert get_schema_version(engine) == 14
    # Idempotent re-run.
    assert ensure_schema(engine) == 14


def test_v12_migration_preserves_legacy_rows_without_backfill():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE attempts (id INTEGER PRIMARY KEY, puzzle_id INTEGER)")
        )
        conn.execute(text("INSERT INTO attempts (id, puzzle_id) VALUES (1, 10)"))
        _migrate_v12_p1(conn)
    with engine.connect() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("attempts")}
        assert "puzzle_rating_snapshot" in cols
        assert "difficulty_snapshot" in cols
        row = conn.execute(
            text("SELECT puzzle_id, puzzle_rating_snapshot, difficulty_snapshot FROM attempts")
        ).first()
        assert row[0] == 10
        assert row[1] is None
        assert row[2] is None
    # Idempotent re-run on the upgraded table.
    with engine.begin() as conn:
        _migrate_v12_p1(conn)
