"""Notification routes: thin wiring over the notification service.

All endpoints are owner-scoped (``users.read`` + ``user_id`` from the
server session). Foreign notification ids read as 404. Preferences are
evaluated server-side in the service; mandatory categories can never be
disabled.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.core.pagination import DEFAULT_PAGE_SIZE, PageQuery, PageSizeQuery
from app.modules.notifications import schemas, service
from app.modules.users.models import User

router = APIRouter(tags=["notifications"])

_NOT_FOUND = {"notification_not_found"}
_UNPROCESSABLE = {
    "unknown_category",
    "unknown_channel",
    "unknown_event_type",
    "mandatory_notification",
}


def _domain_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code in _NOT_FOUND:
        return HTTPException(status_code=404, detail=code)
    if code in _UNPROCESSABLE:
        return HTTPException(status_code=422, detail=code)
    return HTTPException(status_code=400, detail=code)


@router.get("/me/notifications", response_model=list[schemas.NotificationOut])
def list_my_notifications(
    unread_only: bool = False,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    rows, _ = service.list_notifications(
        db, user_id=user.id, unread_only=unread_only, page=page, page_size=page_size
    )
    return [service.notification_view(row) for row in rows]


@router.get("/me/notifications/unread-count", response_model=schemas.UnreadCountOut)
def get_unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return {"unread_count": service.unread_count(db, user_id=user.id)}


@router.post("/me/notifications/{notification_id}/read", response_model=schemas.NotificationOut)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        row = service.mark_read(db, user_id=user.id, notification_id=notification_id)
    except ValueError as exc:
        raise _domain_error(exc)
    return service.notification_view(row)


@router.get("/me/notification-preferences", response_model=list[schemas.PreferenceOut])
def get_my_preferences(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.get_preferences(db, user_id=user.id)


@router.patch("/me/notification-preferences", response_model=schemas.PreferenceOut)
def update_my_preference(
    body: schemas.PreferenceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        return service.set_preference(
            db,
            user_id=user.id,
            category=body.category.strip().lower(),
            channel=body.channel.strip().lower(),
            enabled=body.enabled,
        )
    except ValueError as exc:
        raise _domain_error(exc)
