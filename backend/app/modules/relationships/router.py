"""Relationship routes: thin handlers delegating to the relationship service.

Authorization on every request is:

```text
capability (dependency below)
+
active relationship (service, read fresh from the database)
+
object authorization (party membership + kind, service)
+
privacy rules (limited response shapes, service + schemas)
```

A global COACH or PARENT role never grants access by itself: every
student-scoped endpoint resolves the student through an ACTIVE
relationship of the matching kind, and unknown-or-unrelated students
uniformly return 404.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.core.pagination import DEFAULT_PAGE_SIZE, PageQuery, PageSizeQuery
from app.modules.analytics import schemas as analytics_schemas
from app.modules.analytics import service as analytics_service
from app.modules.gamification_engine import service as gamification_service
from app.modules.player import schemas as player_schemas
from app.modules.player import service as player_service
from app.modules.rating_engine import service as ratings_service
from app.modules.relationships import schemas, service
from app.modules.relationships.models import KIND_COACH, KIND_PARENT
from app.modules.rule_engine.base import AttemptMode
from app.modules.users.models import User

router = APIRouter(tags=["relationships"])
coach_router = APIRouter(prefix="/coach", tags=["coach"])
parent_router = APIRouter(prefix="/parent", tags=["parent"])
own_router = APIRouter(prefix="/me", tags=["player"])


def _creation_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code in ("unknown_user", "unknown_exercise"):
        return HTTPException(status_code=404, detail=code)
    if code in ("relationship_exists", "account_inactive"):
        return HTTPException(status_code=409, detail=code)
    if code in ("invalid_role_combination", "self_relationship", "invalid_kind", "due_at_invalid"):
        return HTTPException(status_code=422, detail=code)
    if code in ("accept_forbidden", "update_forbidden", "no_active_relationship"):
        return HTTPException(status_code=403, detail=code)
    if code == "invalid_transition":
        return HTTPException(status_code=409, detail=code)
    if code == "invalid_status":
        return HTTPException(status_code=422, detail=code)
    return HTTPException(status_code=422, detail=code)


def _relationship_out(db: Session, row, viewer: User) -> schemas.RelationshipOut:
    other_id = row.student_user_id if viewer.id == row.mentor_user_id else row.mentor_user_id
    other = db.get(User, other_id)
    username = other.username or "" if other else ""
    display = service.display_name_for(db, other) if other else ""
    return schemas.relationship_to_out(
        row, viewer_id=viewer.id, other_username=username, other_display=display
    )


# --- relationship lifecycle ----------------------------------------------------


@router.post("/relationships", response_model=schemas.RelationshipOut, status_code=201)
def create_relationship(
    body: schemas.RelationshipCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.RELATIONSHIPS_CREATE)),
):
    try:
        row = service.create_relationship(
            db, actor=user, kind=body.kind, other_username=body.other_username
        )
    except ValueError as exc:
        raise _creation_error(exc)
    return _relationship_out(db, row, user)


@router.get("/relationships", response_model=list[schemas.RelationshipOut])
def list_relationships(
    kind: str | None = None,
    status: str | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        rows = service.list_relationships(db, user, kind=kind, status=status, page=page, page_size=page_size)
    except ValueError as exc:
        raise _creation_error(exc)
    return [_relationship_out(db, row, user) for row in rows]


@router.get("/relationships/{relationship_id}", response_model=schemas.RelationshipOut)
def get_relationship(
    relationship_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    row = service.get_relationship(db, user, relationship_id)
    if row is None:
        raise HTTPException(status_code=404, detail="relationship_not_found")
    return _relationship_out(db, row, user)


@router.post("/relationships/{relationship_id}/accept", response_model=schemas.RelationshipOut)
def accept_relationship(
    relationship_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.RELATIONSHIPS_ACCEPT)),
):
    try:
        result = service.accept_relationship(db, actor=user, relationship_id=relationship_id)
    except ValueError as exc:
        raise _creation_error(exc)
    if result is None:
        raise HTTPException(status_code=404, detail="relationship_not_found")
    row, _ = result
    return _relationship_out(db, row, user)


@router.post("/relationships/{relationship_id}/revoke", response_model=schemas.RelationshipOut)
def revoke_relationship(
    relationship_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.RELATIONSHIPS_REVOKE)),
):
    try:
        result = service.revoke_relationship(db, actor=user, relationship_id=relationship_id)
    except ValueError as exc:
        raise _creation_error(exc)
    if result is None:
        raise HTTPException(status_code=404, detail="relationship_not_found")
    row, _ = result
    return _relationship_out(db, row, user)


# --- shared related-student reads (kind-parameterized) --------------------------


def _authorized_student(db: Session, kind: str, mentor: User, student_id: int) -> User:
    student = service.assert_authorized_student(db, kind=kind, mentor=mentor, student_id=student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="student_not_found")
    return student


def _student_identity(db: Session, student: User) -> schemas.RelatedStudentOut:
    return schemas.RelatedStudentOut(
        id=student.id,
        username=student.username or "",
        display_name=service.display_name_for(db, student),
    )


def _gamification_summary(db: Session, student: User) -> player_schemas.GamificationSummaryOut:
    state = gamification_service.get_state(db, student.id)
    total = state.total_xp if state else 0
    level = state.level if state else 1
    in_level, for_next = gamification_service.xp_progress_in_level(total)
    streak = gamification_service.get_streak(db, student.id)
    unlocks = gamification_service.list_unlocks(db, student.id)
    return player_schemas.GamificationSummaryOut(
        xp=player_schemas.GamificationXpOut(
            total=total, level=level, xp_in_level=in_level, xp_for_next=for_next
        ),
        streak=player_schemas.GamificationStreakOut(
            current=streak.current_streak if streak else 0,
            longest=streak.longest_streak if streak else 0,
        ),
        achievements_unlocked=len(unlocks),
        total_achievements=len(gamification_service.ACHIEVEMENTS),
    )


def _analytics_window(period: str, date_from: str | None, date_to: str | None):
    try:
        return analytics_service.resolve_window(period, date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _register_student_reads(router: APIRouter, kind: str) -> None:
    """Attach the permitted related-student read endpoints for one kind.

    Coach and parent expose the same read shapes (progress, history,
    ratings, gamification, analytics) but stay semantically separate:
    each router filters by its own kind, so a coach relationship never
    authorizes parent endpoints and vice versa.
    """

    @router.get("/students" if kind == KIND_COACH else "/children", response_model=list[schemas.RelatedStudentOut])
    def list_students(
        page: PageQuery = 1,
        page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        pairs = service.list_related_students(db, user, kind=kind, page=page, page_size=page_size)
        return [_student_identity(db, student) for _, student in pairs]

    student_path = "/students/{student_id}" if kind == KIND_COACH else "/children/{student_id}"

    @router.get(student_path, response_model=schemas.RelatedStudentOut)
    def get_student(
        student_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        return _student_identity(db, _authorized_student(db, kind, user, student_id))

    @router.get(f"{student_path}/progress", response_model=player_schemas.ProgressOut)
    def get_student_progress(
        student_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        student = _authorized_student(db, kind, user, student_id)
        return player_service.progress_summary(db, student)

    @router.get(f"{student_path}/attempts", response_model=list[player_schemas.HistoryAttemptOut])
    def list_student_attempts(
        student_id: int,
        exercise: str | None = None,
        mode: AttemptMode | None = None,
        correct: bool | None = None,
        page: PageQuery = 1,
        page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        student = _authorized_student(db, kind, user, student_id)
        return player_service.list_attempts(
            db, student, exercise=exercise, mode=mode, correct=correct, page=page, page_size=page_size
        )

    @router.get(f"{student_path}/attempts/{{attempt_id}}", response_model=player_schemas.HistoryAttemptOut)
    def get_student_attempt(
        student_id: int,
        attempt_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        student = _authorized_student(db, kind, user, student_id)
        attempt = player_service.get_attempt(db, student, attempt_id)
        if attempt is None:
            raise HTTPException(status_code=404, detail="attempt_not_found")
        return attempt

    @router.get(f"{student_path}/ratings", response_model=player_schemas.RatingsOut)
    def list_student_ratings(
        student_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        student = _authorized_student(db, kind, user, student_id)
        rows = ratings_service.list_ratings(db, student.id)
        return player_schemas.RatingsOut(
            items=[player_schemas.rating_to_out(row) for row in rows]
        )

    @router.get(f"{student_path}/ratings/{{exercise_slug}}/history", response_model=player_schemas.RatingHistoryOut)
    def get_student_rating_history(
        student_id: int,
        exercise_slug: str,
        page: PageQuery = 1,
        page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        student = _authorized_student(db, kind, user, student_id)
        if not player_service.is_known_exercise(db, exercise_slug):
            raise HTTPException(status_code=404, detail="exercise_not_found")
        rows = ratings_service.list_history(
            db, student.id, exercise_slug, page=page, page_size=page_size
        )
        return player_schemas.RatingHistoryOut(
            items=[player_schemas.rating_event_to_out(row) for row in rows]
        )

    @router.get(f"{student_path}/gamification", response_model=player_schemas.GamificationSummaryOut)
    def get_student_gamification(
        student_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        student = _authorized_student(db, kind, user, student_id)
        return _gamification_summary(db, student)

    @router.get(f"{student_path}/achievements", response_model=player_schemas.AchievementsOut)
    def list_student_achievements(
        student_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        student = _authorized_student(db, kind, user, student_id)
        unlocked = {row.achievement_code: row for row in gamification_service.list_unlocks(db, student.id)}
        return player_schemas.AchievementsOut(
            items=[
                player_schemas.AchievementOut(
                    code=definition.code,
                    unlocked=definition.code in unlocked,
                    unlocked_at=unlocked[definition.code].unlocked_at
                    if definition.code in unlocked
                    else None,
                )
                for definition in gamification_service.ACHIEVEMENTS
            ]
        )

    @router.get(f"{student_path}/analytics", response_model=analytics_schemas.PlayerAnalyticsOut)
    def get_student_analytics(
        student_id: int,
        period: str = "7d",
        date_from: str | None = None,
        date_to: str | None = None,
        exercise: str | None = None,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        student = _authorized_student(db, kind, user, student_id)
        window = _analytics_window(period, date_from, date_to)
        if exercise is not None and not player_service.is_known_exercise(db, exercise):
            raise HTTPException(status_code=404, detail="exercise_not_found")
        return analytics_service.player_overview(db, student.id, window, exercise)


_register_student_reads(coach_router, KIND_COACH)
_register_student_reads(parent_router, KIND_PARENT)

# The two kind routers share handler names by design (same read shapes,
# separate kind filtering). Keep OpenAPI operation ids unique.
_seen_operation_ids: dict[str, int] = {}
for _route in (*coach_router.routes, *parent_router.routes):
    _seen_operation_ids[_route.name] = _seen_operation_ids.get(_route.name, 0) + 1
    if _seen_operation_ids[_route.name] > 1:
        _route.operation_id = f"{_route.name}_{_seen_operation_ids[_route.name]}"
del _seen_operation_ids, _route


# --- assignments -----------------------------------------------------------------


@coach_router.post("/assignments", response_model=schemas.AssignmentOut, status_code=201)
def create_coach_assignment(
    body: schemas.AssignmentCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        return service.create_assignment(
            db,
            coach=user,
            student_id=body.student_id,
            exercise_slug=body.exercise_slug,
            note=body.note,
            due_at=body.due_at,
        )
    except ValueError as exc:
        raise _creation_error(exc)


@coach_router.get("/assignments", response_model=list[schemas.AssignmentOut])
def list_coach_assignments(
    student_id: int | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.list_assignments_for_coach(db, user, student_id=student_id, page=page, page_size=page_size)


@coach_router.patch("/assignments/{assignment_id}", response_model=schemas.AssignmentOut)
def update_coach_assignment(
    assignment_id: int,
    body: schemas.AssignmentUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        result = service.update_assignment(db, actor=user, assignment_id=assignment_id, status=body.status)
    except ValueError as exc:
        raise _creation_error(exc)
    if result is None:
        raise HTTPException(status_code=404, detail="assignment_not_found")
    row, _ = result
    return row


@parent_router.get("/children/{student_id}/assignments", response_model=list[schemas.AssignmentOut])
def list_child_assignments(
    student_id: int,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    """Read-only assignment visibility for an authorized parent."""
    rows = service.list_assignments_for_parent(db, parent=user, student_id=student_id, page=page, page_size=page_size)
    if rows is None:
        raise HTTPException(status_code=404, detail="student_not_found")
    return rows


@own_router.get("/assignments", response_model=list[schemas.AssignmentOut])
def list_own_assignments(
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.list_assignments_for_student(db, user, page=page, page_size=page_size)


@own_router.patch("/assignments/{assignment_id}", response_model=schemas.AssignmentOut)
def update_own_assignment(
    assignment_id: int,
    body: schemas.AssignmentUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    """A student may mark their own assignment completed (never cancelled)."""
    try:
        result = service.update_assignment(db, actor=user, assignment_id=assignment_id, status=body.status)
    except ValueError as exc:
        raise _creation_error(exc)
    if result is None:
        raise HTTPException(status_code=404, detail="assignment_not_found")
    row, _ = result
    return row
