"""Administration routes: thin wiring over the admin service.

Every endpoint enforces its capability server-side; frontend route
guards are UX only. Responses never carry auth secrets.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import (
    Capability,
    ensure_capability,
    require_capability,
)
from app.core.deps import get_current_session_optional, get_current_user_optional, get_db
from app.core.pagination import DEFAULT_PAGE_SIZE, PageQuery, PageSizeQuery
from app.modules.admin import schemas, service
from app.modules.analytics import schemas as analytics_schemas
from app.modules.analytics import service as analytics_service
from app.modules.support import schemas as support_schemas
from app.modules.support import service as support_service
from app.modules.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"])

_NOT_FOUND = {
    "user_not_found": ("user_not_found", 404),
    "exercise_not_found": ("exercise_not_found", 404),
    "puzzle_not_found": ("puzzle_not_found", 404),
    "audit_not_found": ("audit_not_found", 404),
    "generator_run_not_found": ("generator_run_not_found", 404),
}
_UNPROCESSABLE = {
    "invalid_role",
    "invalid_status",
    "invalid_sort",
    "invalid_order",
    "invalid_title",
    "invalid_sort_order",
    "unknown_exercise",
    "unknown_generator",
    "invalid_count",
    "invalid_seed",
    "invalid_target_rating",
    "invalid_initial_rating",
    "invalid_difficulty",
    "invalid_source",
    "invalid_config",
    "unsupported_config",
    "invalid_decision",
}
_CONFLICT = {
    "last_admin",
    "puzzle_immutable",
    "puzzle_archived",
    "puzzle_answer_missing",
    "validation_failed",
    "invalid_transition",
    "exercise_not_implemented",
}


def _domain_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code in _NOT_FOUND:
        detail, status = _NOT_FOUND[code]
        return HTTPException(status_code=status, detail=detail)
    if code in _UNPROCESSABLE:
        return HTTPException(status_code=422, detail=code)
    if code in _CONFLICT:
        return HTTPException(status_code=409, detail=code)
    return HTTPException(status_code=400, detail=code)


# --- overview ---------------------------------------------------------------


@router.get("/dashboard", response_model=schemas.OverviewOut)
def get_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.ADMIN_OVERVIEW)),
):
    _ = user
    return service.overview(db)


# --- users ------------------------------------------------------------------


@router.get("/users", response_model=list[schemas.AdminUserOut])
def list_users(
    search: str | None = None,
    role: str | None = None,
    status: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    # NOTE: USERS_MANAGE, not USERS_READ — every account holds USERS_READ
    # for its own /me endpoints, so the admin cross-user list must use an
    # admin-held capability (see USER_MANAGEMENT.md least-privilege rule).
    user: User = Depends(require_capability(Capability.USERS_MANAGE)),
):
    _ = user
    try:
        rows, _ = service.list_users(
            db, search=search, role=role, status=status,
            page=page, page_size=page_size, sort=sort, order=order,
        )
    except ValueError as exc:
        raise _domain_error(exc)
    return [service.user_public(row) for row in rows]


@router.get("/users/{user_id}", response_model=schemas.AdminUserDetailOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ_PRIVATE)),
):
    _ = user
    target = service.get_user(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    return service.user_detail(db, target)


@router.post("/users/{user_id}/suspend", response_model=schemas.AdminUserOut)
def suspend_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_SUSPEND)),
):
    try:
        target, _ = service.suspend_user(db, actor_id=user.id, target_id=user_id)
    except ValueError as exc:
        raise _domain_error(exc)
    return service.user_public(target)


@router.post("/users/{user_id}/reactivate", response_model=schemas.AdminUserOut)
def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_REACTIVATE)),
):
    try:
        target, _ = service.reactivate_user(db, actor_id=user.id, target_id=user_id)
    except ValueError as exc:
        raise _domain_error(exc)
    return service.user_public(target)


@router.get("/users/{user_id}/roles", response_model=schemas.RolesOut)
def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ_PRIVATE)),
):
    _ = user
    target = service.get_user(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    return {"roles": service.list_user_roles(target)}


@router.post("/users/{user_id}/roles", response_model=schemas.RolesOut)
def assign_user_role(
    user_id: int,
    body: schemas.RoleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.ROLES_ASSIGN)),
):
    try:
        roles, _ = service.assign_role(db, actor_id=user.id, target_id=user_id, role=body.role)
    except ValueError as exc:
        raise _domain_error(exc)
    return {"roles": roles}


@router.delete("/users/{user_id}/roles/{role}", response_model=schemas.RolesOut)
def revoke_user_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.ROLES_REVOKE)),
):
    try:
        roles, _ = service.revoke_role(db, actor_id=user.id, target_id=user_id, role=role)
    except ValueError as exc:
        raise _domain_error(exc)
    return {"roles": roles}


# --- exercises --------------------------------------------------------------


@router.get("/exercises", response_model=list[schemas.ExerciseAdminOut])
def list_exercises(
    db: Session = Depends(get_db),
    # NOTE: EXERCISES_MANAGE — EXERCISES_READ is held by every player
    # for the public catalog; the admin full-catalog view is privileged.
    user: User = Depends(require_capability(Capability.EXERCISES_MANAGE)),
):
    _ = user
    return service.list_exercises_admin(db)


@router.get("/exercises/{exercise_slug}", response_model=schemas.ExerciseAdminDetailOut)
def get_exercise(
    exercise_slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.EXERCISES_MANAGE)),
):
    _ = user
    exercise = service.get_exercise_admin(db, exercise_slug)
    if exercise is None:
        raise HTTPException(status_code=404, detail="exercise_not_found")
    return service.exercise_admin_view(db, exercise)


@router.patch("/exercises/{exercise_slug}", response_model=schemas.ExerciseAdminDetailOut)
def patch_exercise(
    exercise_slug: str,
    body: schemas.ExerciseUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_optional),
    session=Depends(get_current_session_optional),
):
    # Per-field least privilege: metadata needs exercises.update,
    # availability flips need exercises.enable / exercises.disable.
    # Capabilities resolve from the session's active role (server-side).
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=422, detail="empty_patch")
    metadata_keys = {"title_fa", "title_en", "description", "sort_order"}
    if any(key in patch for key in metadata_keys):
        ensure_capability(user, Capability.EXERCISES_UPDATE, session)
    if patch.get("is_active") is True:
        ensure_capability(user, Capability.EXERCISES_ENABLE, session)
    if patch.get("is_active") is False:
        ensure_capability(user, Capability.EXERCISES_DISABLE, session)
    try:
        exercise = service.update_exercise(db, actor_id=user.id, slug=exercise_slug, patch=patch)
    except ValueError as exc:
        raise _domain_error(exc)
    return service.exercise_admin_view(db, exercise)


# --- puzzles ----------------------------------------------------------------


@router.get("/puzzles", response_model=list[schemas.PuzzleAdminOut])
def list_puzzles(
    exercise: str | None = None,
    status: str | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    # NOTE: PUZZLES_MANAGE — the admin view includes definitive answers,
    # which must never be reachable with the player-held PUZZLES_READ.
    user: User = Depends(require_capability(Capability.PUZZLES_MANAGE)),
):
    _ = user
    try:
        rows, _ = service.list_puzzles_admin(
            db, exercise=exercise, status=status, page=page, page_size=page_size
        )
    except ValueError as exc:
        raise _domain_error(exc)
    return [service.puzzle_admin_view(row) for row in rows]


@router.get("/puzzles/{puzzle_id}", response_model=schemas.PuzzleAdminOut)
def get_puzzle(
    puzzle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_MANAGE)),
):
    _ = user
    puzzle = db.get(service.Puzzle, puzzle_id)
    if puzzle is None:
        raise HTTPException(status_code=404, detail="puzzle_not_found")
    return service.puzzle_admin_view(puzzle)


@router.post("/puzzles", response_model=schemas.PuzzleAdminOut, status_code=201)
def create_puzzle(
    body: schemas.PuzzleCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_CREATE)),
):
    try:
        puzzle = service.create_puzzle_draft(db, actor_id=user.id, fields=body.model_dump())
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


@router.patch("/puzzles/{puzzle_id}", response_model=schemas.PuzzleAdminOut)
def patch_puzzle(
    puzzle_id: int,
    body: schemas.PuzzleUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_UPDATE)),
):
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=422, detail="empty_patch")
    try:
        puzzle = service.update_puzzle(db, actor_id=user.id, puzzle_id=puzzle_id, patch=patch)
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


@router.post("/puzzles/{puzzle_id}/publish", response_model=schemas.PuzzleAdminOut)
def publish_puzzle(
    puzzle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_PUBLISH)),
):
    try:
        puzzle, _ = service.publish_puzzle(db, actor_id=user.id, puzzle_id=puzzle_id)
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


@router.post("/puzzles/{puzzle_id}/validate", response_model=schemas.PuzzleAdminOut)
def validate_puzzle(
    puzzle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_VALIDATE)),
):
    try:
        puzzle, _, _ = service.validate_puzzle(db, actor_id=user.id, puzzle_id=puzzle_id)
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


@router.post("/puzzles/{puzzle_id}/review", response_model=schemas.PuzzleAdminOut)
def review_puzzle(
    puzzle_id: int,
    body: schemas.PuzzleReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_REVIEW)),
):
    try:
        puzzle, _ = service.review_puzzle(
            db, actor_id=user.id, puzzle_id=puzzle_id,
            decision=body.decision.strip().lower(), notes=body.notes,
        )
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


@router.post("/puzzles/{puzzle_id}/approve", response_model=schemas.PuzzleAdminOut)
def approve_puzzle(
    puzzle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_APPROVE)),
):
    try:
        puzzle, _ = service.approve_puzzle(db, actor_id=user.id, puzzle_id=puzzle_id)
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


@router.get("/puzzles/{puzzle_id}/history", response_model=schemas.PuzzleHistoryOut)
def get_puzzle_history(
    puzzle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_MANAGE)),
):
    _ = user
    try:
        return service.puzzle_history(db, puzzle_id)
    except ValueError as exc:
        raise _domain_error(exc)


@router.post("/puzzles/{puzzle_id}/retire", response_model=schemas.PuzzleAdminOut)
def retire_puzzle(
    puzzle_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_RETIRE)),
):
    try:
        puzzle, _ = service.retire_puzzle(db, actor_id=user.id, puzzle_id=puzzle_id)
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


# P1 safety transitions. Quarantine/reject/release reuse the existing
# PUZZLES_RETIRE capability (ADMIN-held privileged content-removal
# scope); restore reuses PUZZLES_PUBLISH (it returns content to servable
# standing). No capability-registry or role-mapping change is required;
# the distinct audit actions (puzzles.quarantine/release/reject/restore)
# keep them distinguishable in the audit trail.
@router.post("/puzzles/{puzzle_id}/quarantine", response_model=schemas.PuzzleAdminOut)
def quarantine_puzzle(
    puzzle_id: int,
    body: schemas.PuzzleLifecycleIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_RETIRE)),
):
    try:
        puzzle, _ = service.quarantine_puzzle(
            db, actor_id=user.id, puzzle_id=puzzle_id, reason=(body.reason if body else "")
        )
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


@router.post("/puzzles/{puzzle_id}/release", response_model=schemas.PuzzleAdminOut)
def release_puzzle(
    puzzle_id: int,
    body: schemas.PuzzleLifecycleIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_RETIRE)),
):
    try:
        puzzle, _ = service.release_puzzle(
            db, actor_id=user.id, puzzle_id=puzzle_id, reason=(body.reason if body else "")
        )
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


@router.post("/puzzles/{puzzle_id}/reject", response_model=schemas.PuzzleAdminOut)
def reject_puzzle(
    puzzle_id: int,
    body: schemas.PuzzleLifecycleIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_RETIRE)),
):
    try:
        puzzle, _ = service.reject_puzzle(
            db, actor_id=user.id, puzzle_id=puzzle_id, reason=(body.reason if body else "")
        )
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


@router.post("/puzzles/{puzzle_id}/restore", response_model=schemas.PuzzleAdminOut)
def restore_puzzle(
    puzzle_id: int,
    body: schemas.PuzzleLifecycleIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.PUZZLES_PUBLISH)),
):
    try:
        puzzle, _ = service.restore_puzzle(
            db, actor_id=user.id, puzzle_id=puzzle_id, reason=(body.reason if body else "")
        )
    except ValueError as exc:
        raise _domain_error(exc)
    return service.puzzle_admin_view(puzzle)


# --- generators ------------------------------------------------------------


@router.get("/generators", response_model=list[schemas.GeneratorOut])
def list_generators(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.GENERATORS_READ)),
):
    _ = db
    _ = user
    return service.list_generators()


@router.post(
    "/generators/{generator_code}/runs",
    response_model=schemas.GeneratorRunOut,
    status_code=201,
)
def run_generator(
    generator_code: str,
    body: schemas.GeneratorRunCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.GENERATORS_RUN)),
):
    try:
        run = service.run_generator(
            db,
            actor_id=user.id,
            generator_code=generator_code,
            count=body.count,
            seed=body.seed,
            target_rating=body.target_rating,
            difficulty=body.difficulty,
            config=body.config,
        )
    except ValueError as exc:
        raise _domain_error(exc)
    from app.modules.generators import service as generator_service

    return generator_service.run_view(run)


@router.get("/generator-runs", response_model=list[schemas.GeneratorRunOut])
def list_generator_runs(
    generator: str | None = None,
    exercise: str | None = None,
    status: str | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.GENERATORS_READ)),
):
    _ = user
    from app.modules.generators import service as generator_service

    rows, _ = service.list_generator_runs(
        db, generator=generator, exercise=exercise, status=status,
        page=page, page_size=page_size,
    )
    return [generator_service.run_view(row) for row in rows]


@router.get("/generator-runs/{run_id}", response_model=schemas.GeneratorRunOut)
def get_generator_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.GENERATORS_READ)),
):
    _ = user
    from app.modules.generators import service as generator_service

    run = service.get_generator_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="generator_run_not_found")
    return generator_service.run_view(run)


@router.post("/generator-runs/{run_id}/cancel", response_model=schemas.GeneratorRunOut)
def cancel_generator_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.GENERATORS_CANCEL)),
):
    try:
        run, _ = service.cancel_generator_run(db, actor_id=user.id, run_id=run_id)
    except ValueError as exc:
        raise _domain_error(exc)
    from app.modules.generators import service as generator_service

    return generator_service.run_view(run)


# --- analytics (Phase 8, read-only derived metrics) -----------------------------


def _analytics_window(period: str, date_from: str | None, date_to: str | None):
    try:
        return analytics_service.resolve_window(period, date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/analytics", response_model=analytics_schemas.PlatformAnalyticsOut)
def get_platform_analytics(
    period: str = "7d",
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.ANALYTICS_READ_PLATFORM)),
):
    _ = user
    window = _analytics_window(period, date_from, date_to)
    return analytics_service.platform_overview(db, window)


@router.get(
    "/analytics/exercises",
    response_model=list[analytics_schemas.AdminExerciseAnalyticsOut],
)
def list_exercise_analytics(
    period: str = "7d",
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.ANALYTICS_READ_EXERCISE)),
):
    _ = user
    window = _analytics_window(period, date_from, date_to)
    return analytics_service.exercise_overview(db, window)


@router.get(
    "/analytics/exercises/{exercise_slug}",
    response_model=analytics_schemas.AdminExerciseDetailOut,
)
def get_exercise_analytics(
    exercise_slug: str,
    period: str = "7d",
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.ANALYTICS_READ_EXERCISE)),
):
    _ = user
    window = _analytics_window(period, date_from, date_to)
    detail = analytics_service.exercise_detail(db, exercise_slug, window)
    if detail is None:
        raise HTTPException(status_code=404, detail="exercise_not_found")
    return detail


@router.get(
    "/analytics/puzzles",
    response_model=list[analytics_schemas.PuzzleAnalyticsOut],
)
def list_puzzle_analytics(
    period: str = "7d",
    date_from: str | None = None,
    date_to: str | None = None,
    exercise: str | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.ANALYTICS_READ_PUZZLE)),
):
    _ = user
    window = _analytics_window(period, date_from, date_to)
    return analytics_service.puzzle_list(
        db, window, exercise=exercise, page=page, page_size=page_size
    )


@router.get(
    "/analytics/puzzles/{puzzle_id}",
    response_model=analytics_schemas.PuzzleAnalyticsDetailOut,
)
def get_puzzle_analytics(
    puzzle_id: int,
    period: str = "7d",
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.ANALYTICS_READ_PUZZLE)),
):
    _ = user
    window = _analytics_window(period, date_from, date_to)
    detail = analytics_service.puzzle_detail(db, puzzle_id, window)
    if detail is None:
        raise HTTPException(status_code=404, detail="puzzle_not_found")
    return detail


# --- support (Phase 11, staff workflows over the support service) ---------


def _support_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code in ("ticket_not_found",):
        return HTTPException(status_code=404, detail=code)
    if code in ("invalid_message", "invalid_status"):
        return HTTPException(status_code=422, detail=code)
    if code in ("ticket_closed",):
        return HTTPException(status_code=409, detail=code)
    return HTTPException(status_code=400, detail=code)


@router.get("/support/tickets", response_model=list[support_schemas.SupportTicketStaffOut])
def list_support_tickets(
    status: str | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.SUPPORT_READ)),
):
    _ = user
    try:
        rows, _ = support_service.list_all_tickets(
            db, status=status, page=page, page_size=page_size
        )
    except ValueError as exc:
        raise _support_error(exc)
    return [support_service.ticket_view(row, include_owner=True) for row in rows]


@router.get(
    "/support/tickets/{ticket_id}",
    response_model=support_schemas.SupportTicketStaffDetailOut,
)
def get_support_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.SUPPORT_READ)),
):
    _ = user
    ticket = support_service.get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket_not_found")
    return support_service.ticket_detail(db, ticket, include_owner=True)


@router.post(
    "/support/tickets/{ticket_id}/messages",
    response_model=support_schemas.SupportMessageOut,
    status_code=201,
)
def respond_to_support_ticket(
    ticket_id: int,
    body: support_schemas.SupportMessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.SUPPORT_RESPOND)),
):
    try:
        message = support_service.add_staff_message(
            db, ticket_id=ticket_id, staff_id=user.id, body=body.body
        )
    except ValueError as exc:
        raise _support_error(exc)
    return support_service.message_view(message)


@router.post(
    "/support/tickets/{ticket_id}/close",
    response_model=support_schemas.SupportTicketStaffOut,
)
def close_support_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.SUPPORT_CLOSE)),
):
    try:
        ticket, _ = support_service.close_ticket(
            db, ticket_id=ticket_id, staff_id=user.id
        )
    except ValueError as exc:
        raise _support_error(exc)
    return support_service.ticket_view(ticket, include_owner=True)


# --- audit ------------------------------------------------------------------


@router.get("/audit", response_model=list[schemas.AuditOut])
def list_audit(
    action: str | None = None,
    target_type: str | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.AUDIT_VIEW)),
):
    _ = user
    rows, _ = service.list_audit(db, action=action, target_type=target_type, page=page, page_size=page_size)
    return [service.audit_view(row) for row in rows]


@router.get("/audit/{audit_id}", response_model=schemas.AuditOut)
def get_audit(
    audit_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.AUDIT_VIEW)),
):
    _ = user
    row = db.get(service.AuditLog, audit_id)
    if row is None:
        raise HTTPException(status_code=404, detail="audit_not_found")
    return service.audit_view(row)
