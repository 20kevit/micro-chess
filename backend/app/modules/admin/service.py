"""Administration application service (Phase 6 foundation + Phase 7 content).

Business rules live here; routers stay thin (auth context, capability
checks, validation, response mapping). Every state-changing operation
records a persistent audit row via ``record_audit`` (secret-free).

Phase 7 content lifecycle (server-enforced, no frontend trust):

```text
draft -> validated -> reviewed -> approved -> published -> retired
```

* validate: exercise-aware content validation must pass.
* review: explicit human decision (approve / request_changes / reject).
* approve: explicit sign-off of reviewed content.
* publish: only approved content becomes player-visible.
* retire: stops new delivery, preserves all history.

Generated content enters as ``validated`` candidates through
generation jobs and follows the same review/approval gates.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.audit import audit_event
from app.modules.admin.models import AuditLog

# Re-exported so the thin router can load rows without importing models.
__all__ = ["AuditLog", "Puzzle"]
from app.modules.exercises import registry
from app.modules.exercises.models import Exercise
from app.modules.generators import service as generator_service
from app.modules.generators.models import GeneratorRun
from app.modules.player.models import PlayerProfile
from app.modules.progress.models import Attempt
from app.modules.puzzles import service as puzzle_service
from app.modules.puzzles.models import (
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_PUBLISHED,
    STATUS_RETIRED,
    STATUS_REVIEWED,
    STATUS_VALIDATED,
    Puzzle,
    PuzzleReview,
    PuzzleStatusHistory,
    PuzzleValidation,
)
from app.modules.puzzles.validation import CONTENT_VALIDATOR_VERSION, validate_puzzle_fields
from app.modules.users.models import CANONICAL_ROLES, User, UserRole

USER_SORT_FIELDS = ("created_at", "username", "id")
# Admin filter vocabulary. "archived" stays accepted as an alias of the
# canonical "retired" state (Phase 6 clients).
PUZZLE_STATUSES = ("draft", "validated", "reviewed", "approved", "published", "retired", "archived")
PUZZLE_SOURCES = ("manual", "imported")
REVIEW_DECISIONS = ("approve", "request_changes", "reject")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- audit -----------------------------------------------------------------


def record_audit(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    target_type: str,
    target_id: int | str,
    metadata: dict | None = None,
    result: str = "ok",
) -> AuditLog:
    """Persist a secret-free audit record + emit the log primitive."""
    row = AuditLog(
        actor_user_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        metadata_json=dict(metadata or {}),
        result=result,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit_event(
        action=action,
        actor=actor_id,
        target_type=target_type,
        target_id=target_id,
        result=result,
        extra=dict(metadata or {}),
    )
    return row


# --- overview ---------------------------------------------------------------


def overview(db: Session) -> dict:
    """Read-only operational snapshot. No secrets, no personal data beyond
    the minimal identity needed to recognize recent registrations."""
    users_total = db.query(func.count(User.id)).scalar() or 0
    users_active = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0  # noqa: E712
    exercises_total = db.query(func.count(Exercise.slug)).scalar() or 0
    exercises_active = (
        db.query(func.count(Exercise.slug)).filter(Exercise.is_active == True).scalar() or 0  # noqa: E712
    )
    puzzles_total = db.query(func.count(Puzzle.id)).scalar() or 0
    puzzles_published = (
        db.query(func.count(Puzzle.id))
        .filter(Puzzle.is_published == True, Puzzle.is_archived == False)  # noqa: E712
        .scalar()
        or 0
    )
    puzzles_archived = (
        db.query(func.count(Puzzle.id)).filter(Puzzle.is_archived == True).scalar() or 0  # noqa: E712
    )
    attempts_total = db.query(func.count(Attempt.id)).scalar() or 0
    day_ago = _utcnow() - timedelta(hours=24)
    attempts_24h = (
        db.query(func.count(Attempt.id)).filter(Attempt.created_at >= day_ago).scalar() or 0
    )
    recent_users = (
        db.query(User).order_by(User.created_at.desc(), User.id.desc()).limit(5).all()
    )
    recent_audit = (
        db.query(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(5).all()
    )
    return {
        "users_total": users_total,
        "users_active": users_active,
        "users_suspended": users_total - users_active,
        "exercises_total": exercises_total,
        "exercises_active": exercises_active,
        "puzzles_total": puzzles_total,
        "puzzles_published": puzzles_published,
        "puzzles_archived": puzzles_archived,
        "attempts_total": attempts_total,
        "attempts_last_24h": attempts_24h,
        "recent_registrations": [
            {
                "id": u.id,
                "username": u.username or "",
                "display_name": u.display_name,
                "created_at": u.created_at,
            }
            for u in recent_users
        ],
        "recent_audit": [
            {
                "id": a.id,
                "actor_user_id": a.actor_user_id,
                "action": a.action,
                "target_type": a.target_type,
                "target_id": a.target_id,
                "result": a.result,
                "created_at": a.created_at,
            }
            for a in recent_audit
        ],
    }


# --- users ------------------------------------------------------------------


def _role_codes(user: User) -> list[str]:
    codes = [row.role for row in (user.roles or []) if row.role in CANONICAL_ROLES]
    return sorted(codes, key=CANONICAL_ROLES.index)


def user_public(row: User) -> dict:
    return {
        "id": row.id,
        "username": row.username or "",
        "display_name": row.display_name,
        "roles": _role_codes(row),
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
    }


def list_users(
    db: Session,
    *,
    search: str | None = None,
    role: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    sort: str = "created_at",
    order: str = "desc",
) -> tuple[list[User], int]:
    """Search/filter users. Only documented filters; no generic querying."""
    if role is not None and role not in CANONICAL_ROLES:
        raise ValueError("invalid_role")
    if status is not None and status not in ("active", "suspended"):
        raise ValueError("invalid_status")
    if sort not in USER_SORT_FIELDS:
        raise ValueError("invalid_sort")
    if order not in ("asc", "desc"):
        raise ValueError("invalid_order")

    query = db.query(User)
    if search:
        like = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(User.username).like(like),
                func.lower(User.display_name).like(like),
            )
        )
    if role is not None:
        query = query.join(UserRole, UserRole.user_id == User.id).filter(UserRole.role == role)
    if status == "active":
        query = query.filter(User.is_active == True)  # noqa: E712
    elif status == "suspended":
        query = query.filter(User.is_active == False)  # noqa: E712

    total = query.count()
    column = {"created_at": User.created_at, "username": User.username, "id": User.id}[sort]
    ordered = column.asc() if order == "asc" else column.desc()
    rows = query.order_by(ordered, User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return rows, total


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def user_detail(db: Session, user: User) -> dict:
    """Permitted administrative view of one account. Never includes
    password hashes, emails, session tokens, or other auth secrets."""
    profile = db.query(PlayerProfile).filter(PlayerProfile.user_id == user.id).first()
    attempts = db.query(func.count(Attempt.id)).filter(Attempt.user_id == user.id).scalar() or 0
    return {
        **user_public(user),
        "profile": {
            "display_name": profile.display_name if profile else "",
            "bio": profile.bio if profile else "",
            "avatar_reference": profile.avatar_reference if profile else "",
        },
        "attempts_count": attempts,
    }


def suspend_user(db: Session, *, actor_id: int, target_id: int) -> tuple[User, bool]:
    """Suspend an account. Suspended tokens fail closed on next use
    (``get_current_session_optional`` rejects inactive accounts), so no
    session-row rewrite is needed. Idempotent: repeats return unchanged."""
    target = db.get(User, target_id)
    if target is None:
        raise ValueError("user_not_found")
    if not target.is_active:
        return target, False
    target.is_active = False
    db.commit()
    db.refresh(target)
    record_audit(
        db,
        actor_id=actor_id,
        action="users.suspend",
        target_type="user",
        target_id=target.id,
        metadata={"username": target.username or ""},
    )
    return target, True


def reactivate_user(db: Session, *, actor_id: int, target_id: int) -> tuple[User, bool]:
    target = db.get(User, target_id)
    if target is None:
        raise ValueError("user_not_found")
    if target.is_active:
        return target, False
    target.is_active = True
    db.commit()
    db.refresh(target)
    record_audit(
        db,
        actor_id=actor_id,
        action="users.reactivate",
        target_type="user",
        target_id=target.id,
        metadata={"username": target.username or ""},
    )
    return target, True


def list_user_roles(user: User) -> list[str]:
    return _role_codes(user)


def assign_role(db: Session, *, actor_id: int, target_id: int, role: str) -> tuple[list[str], bool]:
    if role not in CANONICAL_ROLES:
        raise ValueError("invalid_role")
    target = db.get(User, target_id)
    if target is None:
        raise ValueError("user_not_found")
    existing = db.get(UserRole, (target.id, role))
    if existing is not None:
        return _role_codes(target), False
    db.add(UserRole(user_id=target.id, role=role))
    db.commit()
    db.refresh(target)
    record_audit(
        db,
        actor_id=actor_id,
        action="roles.assign",
        target_type="user",
        target_id=target.id,
        metadata={"role": role},
    )
    return _role_codes(target), True


def revoke_role(db: Session, *, actor_id: int, target_id: int, role: str) -> tuple[list[str], bool]:
    if role not in CANONICAL_ROLES:
        raise ValueError("invalid_role")
    target = db.get(User, target_id)
    if target is None:
        raise ValueError("user_not_found")
    existing = db.get(UserRole, (target.id, role))
    if existing is None:
        return _role_codes(target), False
    if role == "ADMIN":
        # Never remove the final administrative access path.
        others = (
            db.query(func.count(UserRole.user_id))
            .filter(UserRole.role == "ADMIN", UserRole.user_id != target.id)
            .scalar()
            or 0
        )
        if others == 0:
            raise ValueError("last_admin")
    db.delete(existing)
    db.commit()
    db.refresh(target)
    record_audit(
        db,
        actor_id=actor_id,
        action="roles.revoke",
        target_type="user",
        target_id=target.id,
        metadata={"role": role},
    )
    return _role_codes(target), True


# --- exercises --------------------------------------------------------------


def list_exercises_admin(db: Session) -> list[Exercise]:
    return db.query(Exercise).order_by(Exercise.sort_order, Exercise.slug).all()


def get_exercise_admin(db: Session, slug: str) -> Exercise | None:
    return db.get(Exercise, slug)


def exercise_admin_view(db: Session, exercise: Exercise) -> dict:
    puzzle_count = (
        db.query(func.count(Puzzle.id)).filter(Puzzle.exercise_slug == exercise.slug).scalar() or 0
    )
    attempts = (
        db.query(func.count(Attempt.id)).filter(Attempt.exercise_slug == exercise.slug).scalar() or 0
    )
    return {
        "slug": exercise.slug,
        "title_fa": exercise.title_fa,
        "title_en": exercise.title_en,
        "description": exercise.description,
        "is_active": bool(exercise.is_active),
        "sort_order": exercise.sort_order,
        "puzzle_count": puzzle_count,
        "attempts_count": attempts,
    }


def update_exercise(db: Session, *, actor_id: int, slug: str, patch: dict) -> Exercise:
    """Metadata + availability update. The slug is immutable (stable
    identity across attempts/ratings/progress/frontend routes)."""
    exercise = db.get(Exercise, slug)
    if exercise is None:
        raise ValueError("exercise_not_found")
    changes: dict = {}
    if "title_fa" in patch:
        title = (patch["title_fa"] or "").strip()
        if not title:
            raise ValueError("invalid_title")
        exercise.title_fa = title[:200]
        changes["title_fa"] = exercise.title_fa
    if "title_en" in patch:
        exercise.title_en = (patch["title_en"] or "").strip()[:200]
        changes["title_en"] = exercise.title_en
    if "description" in patch:
        exercise.description = (patch["description"] or "").strip()[:1000]
        changes["description"] = exercise.description
    if "sort_order" in patch:
        order = patch["sort_order"]
        if not isinstance(order, int) or order < 0:
            raise ValueError("invalid_sort_order")
        exercise.sort_order = order
        changes["sort_order"] = order
    if "is_active" in patch:
        active = bool(patch["is_active"])
        if active and not exercise.is_active:
            # Enabling requires a real implementation behind the slug.
            if exercise.slug not in registry.registered_slugs():
                raise ValueError("exercise_not_implemented")
            exercise.is_active = True
            changes["is_active"] = True
        elif not active and exercise.is_active:
            # Disabling preserves history; new attempts are refused
            # server-side while the catalog hides the exercise.
            exercise.is_active = False
            changes["is_active"] = False
    if not changes:
        return exercise
    db.commit()
    db.refresh(exercise)
    record_audit(
        db,
        actor_id=actor_id,
        action="exercises.update",
        target_type="exercise",
        target_id=exercise.slug,
        metadata=changes,
    )
    return exercise


def is_exercise_playable(db: Session, slug: str) -> bool:
    """Server-side availability for new attempts. Missing rows (legacy or
    generated content without a catalog entry) stay playable so Phase 1-5
    behavior is preserved; an explicit disabled row blocks new attempts."""
    row = db.get(Exercise, slug)
    if row is None:
        return True
    return bool(row.is_active)


# --- puzzles ----------------------------------------------------------------


def _puzzle_status(row: Puzzle) -> str:
    # Canonical lifecycle state (backfilled for legacy rows by the v7
    # migration; runtime rows enter via the model default).
    return row.status or STATUS_DRAFT


def _record_transition(
    db: Session, *, actor_id: int, puzzle: Puzzle, to_status: str, reason: str = ""
) -> None:
    """Apply a lifecycle transition with history + flag sync.

    Player-visibility booleans mirror the canonical status so existing
    player queries keep working unchanged.
    """
    from_status = _puzzle_status(puzzle)
    puzzle.status = to_status
    if to_status == STATUS_PUBLISHED:
        puzzle.is_published = True
        puzzle.is_archived = False
        puzzle.published_at = _utcnow()
        puzzle.retired_at = None
    elif to_status == STATUS_RETIRED:
        puzzle.is_archived = True
        puzzle.retired_at = _utcnow()
    else:
        puzzle.is_published = False
        puzzle.is_archived = False
    db.add(
        PuzzleStatusHistory(
            puzzle_id=puzzle.id,
            from_status=from_status,
            to_status=to_status,
            changed_by_user_id=actor_id,
            reason=reason[:500],
        )
    )


def _known_exercise(db: Session, slug: str) -> bool:
    if db.get(Exercise, slug) is not None:
        return True
    return slug in registry.registered_slugs()


def list_puzzles_admin(
    db: Session,
    *,
    exercise: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Puzzle], int]:
    if status is not None and status not in PUZZLE_STATUSES:
        raise ValueError("invalid_status")
    query = db.query(Puzzle)
    if exercise:
        query = query.filter(Puzzle.exercise_slug == exercise)
    if status in ("draft", "validated", "reviewed", "approved", "published"):
        query = query.filter(Puzzle.status == status, Puzzle.is_archived == False)  # noqa: E712
    elif status in ("retired", "archived"):
        query = query.filter(Puzzle.status == STATUS_RETIRED)
    total = query.count()
    rows = query.order_by(Puzzle.id).offset((page - 1) * page_size).limit(page_size).all()
    return rows, total


def puzzle_admin_view(row: Puzzle) -> dict:
    """Full administrative view, including the definitive answer (needed
    for review) and lifecycle/provenance metadata. Never reused by
    player-facing endpoints."""
    return {
        "id": row.id,
        "exercise_slug": row.exercise_slug,
        "status": _puzzle_status(row),
        "fen": row.fen,
        "position_json": row.position_json or {},
        "answer_json": row.answer_json or {},
        "hint_json": row.hint_json or {},
        "prompt_fa": row.prompt_fa,
        "explanation": row.explanation,
        "initial_rating": row.initial_rating,
        "is_published": bool(row.is_published),
        "is_archived": bool(row.is_archived),
        "published_at": row.published_at,
        "created_at": row.created_at,
        "source": row.source or "manual",
        "source_reference": row.source_reference,
        "generator_run_id": row.generator_run_id,
        "difficulty": row.difficulty,
        "target_rating": row.target_rating,
        "retired_at": row.retired_at,
    }


def _check_puzzle_metadata(difficulty, target_rating, initial_rating) -> None:
    if difficulty is not None and (not isinstance(difficulty, int) or not 1 <= difficulty <= 5):
        raise ValueError("invalid_difficulty")
    for label, value in (("target_rating", target_rating), ("initial_rating", initial_rating)):
        if value is not None:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"invalid_{label}")
            if not 100.0 <= numeric <= 3000.0:
                raise ValueError(f"invalid_{label}")


def create_puzzle_draft(db: Session, *, actor_id: int, fields: dict) -> Puzzle:
    slug = (fields.get("exercise_slug") or "").strip()
    if not slug:
        raise ValueError("unknown_exercise")
    if not _known_exercise(db, slug):
        raise ValueError("unknown_exercise")
    source = (fields.get("source") or "manual").strip()
    if source not in PUZZLE_SOURCES:
        raise ValueError("invalid_source")
    difficulty = fields.get("difficulty")
    target_rating = fields.get("target_rating")
    initial_rating = fields.get("initial_rating", 1200.0)
    _check_puzzle_metadata(difficulty, target_rating, initial_rating)
    try:
        initial_rating = float(initial_rating)
    except (TypeError, ValueError):
        raise ValueError("invalid_initial_rating")
    answer = fields.get("answer_json") or {}
    fen = fields.get("fen")
    from app.modules.puzzles.validation import content_hash_for

    puzzle = Puzzle(
        exercise_slug=slug,
        fen=fen,
        position_json=fields.get("position_json") or {},
        answer_json=answer,
        hint_json=fields.get("hint_json") or {},
        prompt_fa=(fields.get("prompt_fa") or "")[:500],
        explanation=(fields.get("explanation") or "")[:2000],
        initial_rating=initial_rating,
        is_published=False,
        is_archived=False,
        status=STATUS_DRAFT,
        source=source,
        source_reference=(fields.get("source_reference") or None),
        difficulty=difficulty,
        target_rating=float(target_rating) if target_rating is not None else None,
        content_hash=content_hash_for(slug, fen, answer),
    )
    db.add(puzzle)
    db.commit()
    db.refresh(puzzle)
    record_audit(
        db,
        actor_id=actor_id,
        action="puzzles.create",
        target_type="puzzle",
        target_id=puzzle.id,
        metadata={"exercise_slug": slug, "source": source},
    )
    return puzzle


def _meaning_keys_in(patch: dict) -> list[str]:
    # Exercise reassignment is rejected separately (only when changed);
    # an unchanged slug is a no-op, so it is not a meaning edit.
    return [key for key in ("answer_json", "position_json", "fen") if key in patch]


def update_puzzle(db: Session, *, actor_id: int, puzzle_id: int, patch: dict) -> Puzzle:
    puzzle = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        raise ValueError("puzzle_not_found")
    status = _puzzle_status(puzzle)
    if status == STATUS_RETIRED:
        # Retired content is production history; it is never edited.
        raise ValueError("puzzle_immutable")
    if "exercise_slug" in patch and patch["exercise_slug"] != puzzle.exercise_slug:
        # Exercise association is part of the puzzle's stable identity and
        # historical references; it is never reassigned.
        raise ValueError("puzzle_immutable")
    if _meaning_keys_in(patch) and status != STATUS_DRAFT:
        # Meaning-defining fields lock once the puzzle leaves draft.
        # To correct content, request changes (back to draft) and
        # re-validate: history stays interpretable. (An unchanged
        # exercise_slug is a harmless no-op, not a meaning edit.)
        raise ValueError("puzzle_immutable")
    changes: dict = {}
    if status == STATUS_DRAFT:
        if "answer_json" in patch:
            puzzle.answer_json = patch["answer_json"] or {}
            changes["answer_json"] = True
        if "position_json" in patch:
            puzzle.position_json = patch["position_json"] or {}
            changes["position_json"] = True
        if "fen" in patch:
            puzzle.fen = patch["fen"]
            changes["fen"] = True
    if "hint_json" in patch:
        puzzle.hint_json = patch["hint_json"] or {}
        changes["hint_json"] = True
    if "prompt_fa" in patch:
        puzzle.prompt_fa = (patch["prompt_fa"] or "")[:500]
        changes["prompt_fa"] = True
    if "explanation" in patch:
        puzzle.explanation = (patch["explanation"] or "")[:2000]
        changes["explanation"] = True
    if "initial_rating" in patch:
        _check_puzzle_metadata(None, None, patch["initial_rating"])
        puzzle.initial_rating = float(patch["initial_rating"])
        changes["initial_rating"] = puzzle.initial_rating
    if "difficulty" in patch:
        _check_puzzle_metadata(patch["difficulty"], None, None)
        puzzle.difficulty = patch["difficulty"]
        changes["difficulty"] = puzzle.difficulty
    if "target_rating" in patch:
        _check_puzzle_metadata(None, patch["target_rating"], None)
        puzzle.target_rating = (
            float(patch["target_rating"]) if patch["target_rating"] is not None else None
        )
        changes["target_rating"] = puzzle.target_rating
    if "source_reference" in patch:
        puzzle.source_reference = patch["source_reference"] or None
        changes["source_reference"] = True
    if "answer_json" in patch or "fen" in patch:
        from app.modules.puzzles.validation import content_hash_for

        puzzle.content_hash = content_hash_for(
            puzzle.exercise_slug, puzzle.fen, puzzle.answer_json or {}
        )
        changes["content_hash"] = True
    if not changes:
        return puzzle
    db.commit()
    db.refresh(puzzle)
    record_audit(
        db,
        actor_id=actor_id,
        action="puzzles.update",
        target_type="puzzle",
        target_id=puzzle.id,
        metadata=changes,
    )
    return puzzle


def validate_puzzle(db: Session, *, actor_id: int, puzzle_id: int) -> tuple[Puzzle, bool, dict]:
    """Run exercise-aware validation. Passing content advances
    draft -> validated; failing content returns to draft. Every run is
    recorded and audited."""
    puzzle = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        raise ValueError("puzzle_not_found")
    status = _puzzle_status(puzzle)
    if status not in (STATUS_DRAFT, STATUS_VALIDATED):
        raise ValueError("invalid_transition")
    outcome = validate_puzzle_fields(
        db,
        exercise_slug=puzzle.exercise_slug,
        fen=puzzle.fen,
        position_json=puzzle.position_json,
        answer_json=puzzle.answer_json,
        difficulty=puzzle.difficulty,
        target_rating=puzzle.target_rating,
        initial_rating=puzzle.initial_rating,
        exclude_puzzle_id=puzzle.id,
    )
    db.add(
        PuzzleValidation(
            puzzle_id=puzzle.id,
            validator_version=CONTENT_VALIDATOR_VERSION,
            status="pass" if outcome.ok else "fail",
            result_json={"errors": outcome.errors},
            validated_by_user_id=actor_id,
        )
    )
    changed = False
    if outcome.ok and status == STATUS_DRAFT:
        _record_transition(db, actor_id=actor_id, puzzle=puzzle, to_status=STATUS_VALIDATED)
        changed = True
    elif not outcome.ok and status == STATUS_VALIDATED:
        _record_transition(
            db, actor_id=actor_id, puzzle=puzzle, to_status=STATUS_DRAFT, reason="re-validation failed"
        )
        changed = True
    else:
        db.flush()
    if outcome.ok:
        puzzle.content_hash = outcome.content_hash
    db.commit()
    db.refresh(puzzle)
    record_audit(
        db,
        actor_id=actor_id,
        action="puzzles.validate",
        target_type="puzzle",
        target_id=puzzle.id,
        metadata={
            "exercise_slug": puzzle.exercise_slug,
            "result": "pass" if outcome.ok else "fail",
            "changed": changed,
        },
        result="ok" if outcome.ok else "fail",
    )
    return puzzle, changed, {"ok": outcome.ok, "errors": outcome.errors}


def review_puzzle(
    db: Session, *, actor_id: int, puzzle_id: int, decision: str, notes: str = ""
) -> tuple[Puzzle, bool]:
    """Explicit human review of validated content. Approve advances to
    reviewed; request_changes/reject return the candidate to draft with
    the decision preserved for traceability."""
    puzzle = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        raise ValueError("puzzle_not_found")
    if decision not in REVIEW_DECISIONS:
        raise ValueError("invalid_decision")
    if _puzzle_status(puzzle) != STATUS_VALIDATED:
        raise ValueError("invalid_transition")
    clean_notes = (notes or "")[:2000]
    db.add(
        PuzzleReview(
            puzzle_id=puzzle.id,
            reviewer_user_id=actor_id,
            decision=decision,
            notes=clean_notes,
        )
    )
    if decision == "approve":
        _record_transition(db, actor_id=actor_id, puzzle=puzzle, to_status=STATUS_REVIEWED)
    else:
        _record_transition(
            db, actor_id=actor_id, puzzle=puzzle, to_status=STATUS_DRAFT, reason=decision
        )
    db.commit()
    db.refresh(puzzle)
    record_audit(
        db,
        actor_id=actor_id,
        action="puzzles.review",
        target_type="puzzle",
        target_id=puzzle.id,
        metadata={"exercise_slug": puzzle.exercise_slug, "decision": decision},
    )
    return puzzle, True


def approve_puzzle(db: Session, *, actor_id: int, puzzle_id: int) -> tuple[Puzzle, bool]:
    """Explicit sign-off of reviewed content. Only approved content may
    be published."""
    puzzle = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        raise ValueError("puzzle_not_found")
    if _puzzle_status(puzzle) != STATUS_REVIEWED:
        raise ValueError("invalid_transition")
    _record_transition(db, actor_id=actor_id, puzzle=puzzle, to_status=STATUS_APPROVED)
    db.commit()
    db.refresh(puzzle)
    record_audit(
        db,
        actor_id=actor_id,
        action="puzzles.approve",
        target_type="puzzle",
        target_id=puzzle.id,
        metadata={"exercise_slug": puzzle.exercise_slug},
    )
    return puzzle, True


def publish_puzzle(db: Session, *, actor_id: int, puzzle_id: int) -> tuple[Puzzle, bool]:
    """Publish approved content. Gates: approved lifecycle state, known
    exercise, non-empty answer, and a final passing validation (guards
    against duplicates that appeared while the puzzle awaited review).
    Idempotent: republishing returns unchanged."""
    puzzle = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        raise ValueError("puzzle_not_found")
    if _puzzle_status(puzzle) == STATUS_RETIRED:
        raise ValueError("puzzle_archived")
    if puzzle.is_published and _puzzle_status(puzzle) == STATUS_PUBLISHED:
        return puzzle, False
    if _puzzle_status(puzzle) != STATUS_APPROVED:
        # Approval must precede production use; there is no shortcut
        # from draft/validated/reviewed to published.
        raise ValueError("invalid_transition")
    if not _known_exercise(db, puzzle.exercise_slug):
        raise ValueError("unknown_exercise")
    if not puzzle.answer_json:
        raise ValueError("puzzle_answer_missing")
    outcome = validate_puzzle_fields(
        db,
        exercise_slug=puzzle.exercise_slug,
        fen=puzzle.fen,
        position_json=puzzle.position_json,
        answer_json=puzzle.answer_json,
        difficulty=puzzle.difficulty,
        target_rating=puzzle.target_rating,
        initial_rating=puzzle.initial_rating,
        exclude_puzzle_id=puzzle.id,
    )
    if not outcome.ok:
        db.add(
            PuzzleValidation(
                puzzle_id=puzzle.id,
                validator_version=CONTENT_VALIDATOR_VERSION,
                status="fail",
                result_json={"errors": outcome.errors, "at": "publish"},
                validated_by_user_id=actor_id,
            )
        )
        db.commit()
        raise ValueError("validation_failed")
    puzzle.content_hash = outcome.content_hash
    _record_transition(db, actor_id=actor_id, puzzle=puzzle, to_status=STATUS_PUBLISHED)
    db.commit()
    db.refresh(puzzle)
    record_audit(
        db,
        actor_id=actor_id,
        action="puzzles.publish",
        target_type="puzzle",
        target_id=puzzle.id,
        metadata={"exercise_slug": puzzle.exercise_slug},
    )
    return puzzle, True


def retire_puzzle(db: Session, *, actor_id: int, puzzle_id: int) -> tuple[Puzzle, bool]:
    """Retire (archive) a puzzle. New delivery stops; historical attempts,
    ratings, and analytics keep referencing the same row. Idempotent."""
    puzzle = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        raise ValueError("puzzle_not_found")
    if _puzzle_status(puzzle) == STATUS_RETIRED:
        return puzzle, False
    from_status = _puzzle_status(puzzle)
    puzzle_service.archive(db, puzzle)
    db.add(
        PuzzleStatusHistory(
            puzzle_id=puzzle.id,
            from_status=from_status,
            to_status=STATUS_RETIRED,
            changed_by_user_id=actor_id,
            reason="retired",
        )
    )
    db.commit()
    db.refresh(puzzle)
    record_audit(
        db,
        actor_id=actor_id,
        action="puzzles.retire",
        target_type="puzzle",
        target_id=puzzle.id,
        metadata={"exercise_slug": puzzle.exercise_slug},
    )
    return puzzle, True


def puzzle_history(db: Session, puzzle_id: int) -> dict:
    """Inspectable lifecycle trail for one puzzle: transitions,
    validation runs, and human reviews (newest last)."""
    puzzle = db.get(Puzzle, puzzle_id)
    if puzzle is None:
        raise ValueError("puzzle_not_found")
    transitions = (
        db.query(PuzzleStatusHistory)
        .filter(PuzzleStatusHistory.puzzle_id == puzzle.id)
        .order_by(PuzzleStatusHistory.id)
        .all()
    )
    validations = (
        db.query(PuzzleValidation)
        .filter(PuzzleValidation.puzzle_id == puzzle.id)
        .order_by(PuzzleValidation.id)
        .all()
    )
    reviews = (
        db.query(PuzzleReview)
        .filter(PuzzleReview.puzzle_id == puzzle.id)
        .order_by(PuzzleReview.id)
        .all()
    )
    return {
        "puzzle_id": puzzle.id,
        "status": _puzzle_status(puzzle),
        "transitions": [
            {
                "id": row.id,
                "from_status": row.from_status,
                "to_status": row.to_status,
                "changed_by_user_id": row.changed_by_user_id,
                "reason": row.reason,
                "created_at": row.created_at,
            }
            for row in transitions
        ],
        "validations": [
            {
                "id": row.id,
                "validator_version": row.validator_version,
                "status": row.status,
                "result": row.result_json or {},
                "validated_by_user_id": row.validated_by_user_id,
                "created_at": row.created_at,
            }
            for row in validations
        ],
        "reviews": [
            {
                "id": row.id,
                "reviewer_user_id": row.reviewer_user_id,
                "decision": row.decision,
                "notes": row.notes,
                "created_at": row.created_at,
            }
            for row in reviews
        ],
    }


# --- generators --------------------------------------------------------------


def list_generators() -> list[dict]:
    """Central generator registry view (code-defined; admins cannot
    introduce arbitrary executable generators)."""
    return [generator_service.generator_view(definition) for definition in generator_service.available_generators()]


def run_generator(
    db: Session,
    *,
    actor_id: int,
    generator_code: str,
    count: int,
    seed: int | None = None,
    target_rating: float | None = None,
    difficulty: int | None = None,
    config: dict | None = None,
) -> GeneratorRun:
    try:
        run = generator_service.run_job(
            db,
            actor_id=actor_id,
            generator_code=generator_code,
            count=count,
            seed=seed,
            target_rating=target_rating,
            difficulty=difficulty,
            config=config,
        )
    except ValueError:
        raise
    record_audit(
        db,
        actor_id=actor_id,
        action="generators.run",
        target_type="generator_run",
        target_id=run.id,
        metadata={
            "generator": run.generator_code,
            "version": run.generator_version,
            "status": run.status,
            "accepted": run.accepted_count,
            "rejected": run.rejected_count,
        },
        result="ok" if run.status == "completed" else "fail",
    )
    return run


def list_generator_runs(
    db: Session,
    *,
    generator: str | None = None,
    exercise: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[GeneratorRun], int]:
    return generator_service.list_runs(
        db, generator=generator, exercise=exercise, status=status, page=page, page_size=page_size
    )


def get_generator_run(db: Session, run_id: int) -> GeneratorRun | None:
    return db.get(GeneratorRun, run_id)


def cancel_generator_run(db: Session, *, actor_id: int, run_id: int) -> tuple[GeneratorRun, bool]:
    run, changed = generator_service.cancel_job(db, actor_id=actor_id, run_id=run_id)
    record_audit(
        db,
        actor_id=actor_id,
        action="generators.cancel",
        target_type="generator_run",
        target_id=run.id,
        metadata={"generator": run.generator_code},
    )
    return run, changed


# --- audit visibility --------------------------------------------------------


def list_audit(
    db: Session,
    *,
    action: str | None = None,
    target_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AuditLog], int]:
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    total = query.count()
    rows = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def audit_view(row: AuditLog) -> dict:
    return {
        "id": row.id,
        "actor_user_id": row.actor_user_id,
        "action": row.action,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "metadata": row.metadata_json or {},
        "result": row.result,
        "created_at": row.created_at,
    }
