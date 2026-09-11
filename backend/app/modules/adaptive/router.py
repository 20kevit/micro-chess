"""Adaptive training routes: thin handlers delegating to the adaptive service.

Authorization on every request is:

```text
capability (dependency below)
+
object authorization (/me scoping for the learner; active relationship
of the matching kind for coach/parent reads)
+
privacy rules (derived signals for the authorized learner only; puzzle
answers never leave the server)
```

The server is authoritative: the client never supplies ratings,
weakness scores, difficulty scores, eligibility decisions, or
recommendation scores — every value derives server-side from
authoritative training history and content state.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.core.pagination import DEFAULT_PAGE_SIZE, PageQuery, PageSizeQuery
from app.modules.adaptive import schemas, service
from app.modules.player import service as player_service
from app.modules.relationships import service as relationships_service
from app.modules.relationships.models import KIND_COACH, KIND_PARENT
from app.modules.users.models import User

me_router = APIRouter(prefix="/me/adaptive", tags=["adaptive"])
coach_router = APIRouter(prefix="/coach", tags=["coach"])
parent_router = APIRouter(prefix="/parent", tags=["parent"])


def _signals_to_out(signals: service.ExerciseSignals) -> schemas.ExerciseSignalsOut:
    return schemas.ExerciseSignalsOut(
        exercise=signals.exercise,
        attempts=signals.attempts,
        accuracy=signals.accuracy,
        recent_accuracy=signals.recent_accuracy,
        recent_failures=signals.recent_failures,
        repeated_mistakes=signals.repeated_mistakes,
        avg_response_ms=signals.avg_response_ms,
        days_since_last=signals.days_since_last,
        rating=signals.rating,
        provisional=signals.provisional,
        games=signals.games,
        rating_trend=signals.rating_trend,
        reason=signals.reason,
    )


def _overview_to_out(result: dict) -> schemas.AdaptiveOverviewOut:
    return schemas.AdaptiveOverviewOut(
        exercises=[_signals_to_out(signals) for signals in result["exercises"]],
        recommended_exercise=result["recommended_exercise"],
        reason=result["reason"],
    )


def _outcome_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code in ("invalid_transition", "invalid_status", "invalid_result"):
        return HTTPException(status_code=422, detail=code)
    return HTTPException(status_code=422, detail=code)


# --- learner endpoints --------------------------------------------------------


@me_router.get("/overview", response_model=schemas.AdaptiveOverviewOut)
def get_adaptive_overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return _overview_to_out(service.overview(db, user.id))


@me_router.get("/next", response_model=schemas.AdaptiveNextOut)
def get_adaptive_next(
    exercise: str,
    seed: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        result = service.next_for_exercise(db, user.id, exercise, seed=seed)
    except ValueError as exc:
        code = str(exc)
        if code == "exercise_not_found":
            raise HTTPException(status_code=404, detail=code)
        if code in ("exercise_not_available", "no_eligible_content"):
            raise HTTPException(status_code=404, detail=code)
        raise HTTPException(status_code=422, detail=code)
    return schemas.AdaptiveNextOut(
        puzzle=result["puzzle"],
        reason=result["reason"],
        ability_rating=result["ability_rating"],
        target_rating=result["target_rating"],
        observed_difficulty=result["observed_difficulty"],
        recommendation_id=result["recommendation_id"],
        fallback=result["fallback"],
    )


@me_router.get("/history", response_model=list[schemas.RecommendationOut])
def list_adaptive_history(
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.list_history(db, user.id, page=page, page_size=page_size)


@me_router.post("/outcomes/{recommendation_id}", response_model=schemas.RecommendationOut)
def post_adaptive_outcome(
    recommendation_id: int,
    body: schemas.OutcomeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        row = service.record_outcome(
            db, user.id, recommendation_id, status=body.status, result=body.result
        )
    except ValueError as exc:
        raise _outcome_error(exc)
    if row is None:
        raise HTTPException(status_code=404, detail="recommendation_not_found")
    return row


# --- related-learner reads (Phase 09 authorization, adaptive state only) ------


def _authorized_student(db: Session, kind: str, mentor: User, student_id: int) -> User:
    student = relationships_service.assert_authorized_student(
        db, kind=kind, mentor=mentor, student_id=student_id
    )
    if student is None:
        raise HTTPException(status_code=404, detail="student_not_found")
    return student


def _register_adaptive_reads(router: APIRouter, kind: str) -> None:
    """Derived adaptive overview for an authorized related learner.

    Read-only by construction (the overview derives signals without
    persisting anything), so viewing a student's adaptive state never
    fabricates their recommendation history. ``next`` issuance and
    outcome recording stay owner-only on ``/me/adaptive``.
    """
    student_path = "/students/{student_id}" if kind == KIND_COACH else "/children/{student_id}"

    @router.get(f"{student_path}/adaptive/overview", response_model=schemas.AdaptiveOverviewOut)
    def get_student_adaptive_overview(
        student_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        student = _authorized_student(db, kind, user, student_id)
        return _overview_to_out(service.overview(db, student.id))

    @router.get(
        f"{student_path}/adaptive/exercises/{{exercise_slug}}",
        response_model=schemas.ExerciseSignalsOut,
    )
    def get_student_adaptive_exercise(
        student_id: int,
        exercise_slug: str,
        db: Session = Depends(get_db),
        user: User = Depends(require_capability(Capability.USERS_READ)),
    ):
        student = _authorized_student(db, kind, user, student_id)
        if not player_service.is_known_exercise(db, exercise_slug):
            raise HTTPException(status_code=404, detail="exercise_not_found")
        return _signals_to_out(service.exercise_signals(db, student.id, exercise_slug))


_register_adaptive_reads(coach_router, KIND_COACH)
_register_adaptive_reads(parent_router, KIND_PARENT)

# The two kind routers share handler names by design (same read shapes,
# separate kind filtering). Keep OpenAPI operation ids unique.
_seen_operation_ids: dict[str, int] = {}
for _route in (*coach_router.routes, *parent_router.routes):
    _seen_operation_ids[_route.name] = _seen_operation_ids.get(_route.name, 0) + 1
    if _seen_operation_ids[_route.name] > 1:
        _route.operation_id = f"{_route.name}_{_seen_operation_ids[_route.name]}"
del _seen_operation_ids, _route
