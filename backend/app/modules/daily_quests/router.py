"""Daily journey routes: thin wiring over the quest service."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.modules.daily_quests import schemas, service
from app.modules.daily_quests.models import STATUS_COMPLETED
from app.modules.users.models import User

router = APIRouter(tags=["journey"])


def _today_out(day, quests) -> dict:
    views = [service.quest_view(day, q) for q in quests]
    done = sum(1 for q in quests if q.status == STATUS_COMPLETED)
    return {
        "local_date": day.local_date,
        "timezone": day.timezone,
        "completed_count": done,
        "total": len(views),
        "is_complete": bool(views) and done == len(views),
        "quests": views,
    }


@router.get("/me/journey/today", response_model=schemas.TodayOut)
def get_today(
    timezone: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    out = service.get_today(db, user.id, tz_name=timezone)
    return _today_out(out["day"], out["quests"])


@router.post("/me/journey/quests/{quest_id}/start", response_model=schemas.QuestOut)
def start_quest(
    quest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        quest = service.start_quest(db, user.id, quest_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    day = service.db_get_day(db, quest.day_id) if hasattr(service, "db_get_day") else None
    if day is None:
        from app.modules.daily_quests.models import DailyQuestDay

        day = db.get(DailyQuestDay, quest.day_id)
    return service.quest_view(day, quest)


@router.post("/me/journey/quests/{quest_id}/complete", response_model=schemas.QuestOut)
def complete_quest(
    quest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        quest = service.complete_quest(db, user.id, quest_id)
    except ValueError as exc:
        code = str(exc)
        if code == "quest_not_found":
            raise HTTPException(status_code=404, detail=code)
        raise HTTPException(status_code=422, detail=code)
    from app.modules.daily_quests.models import DailyQuestDay

    day = db.get(DailyQuestDay, quest.day_id)
    return service.quest_view(day, quest)
