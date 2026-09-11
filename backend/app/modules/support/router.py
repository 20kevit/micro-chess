"""Support routes: thin wiring over the support service.

Owner endpoints authorize via ``support.create`` / ``support.read_own``
plus per-object ownership in the service (foreign ids read as 404, no
existence leak). Creation and owner replies are rate-limited against
spam; every state change is audited in the service layer.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.pagination import DEFAULT_PAGE_SIZE, PageQuery, PageSizeQuery
from app.core.rate_limit import enforce_support_rate_limit
from app.core.deps import get_db
from app.modules.support import schemas, service
from app.modules.users.models import User

router = APIRouter(tags=["support"])

_NOT_FOUND = {"ticket_not_found"}
_UNPROCESSABLE = {"invalid_subject", "invalid_message", "invalid_status"}
_CONFLICT = {"ticket_closed"}


def _domain_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code in _NOT_FOUND:
        return HTTPException(status_code=404, detail=code)
    if code in _UNPROCESSABLE:
        return HTTPException(status_code=422, detail=code)
    if code in _CONFLICT:
        return HTTPException(status_code=409, detail=code)
    return HTTPException(status_code=400, detail=code)


@router.post(
    "/support/tickets",
    response_model=schemas.SupportTicketDetailOut,
    status_code=201,
)
def create_support_ticket(
    body: schemas.SupportTicketCreateIn,
    request_dep: None = Depends(enforce_support_rate_limit),
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.SUPPORT_CREATE)),
):
    _ = request_dep
    try:
        ticket = service.create_ticket(
            db,
            owner_id=user.id,
            subject=body.subject,
            message=body.message,
            category=body.category,
        )
    except ValueError as exc:
        raise _domain_error(exc)
    return service.ticket_detail(db, ticket)


@router.get("/me/support/tickets", response_model=list[schemas.SupportTicketOut])
def list_my_tickets(
    status: str | None = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.SUPPORT_READ_OWN)),
):
    try:
        rows, _ = service.list_owner_tickets(
            db, owner_id=user.id, status=status, page=page, page_size=page_size
        )
    except ValueError as exc:
        raise _domain_error(exc)
    return [service.ticket_view(row) for row in rows]


@router.get(
    "/me/support/tickets/{ticket_id}", response_model=schemas.SupportTicketDetailOut
)
def get_my_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.SUPPORT_READ_OWN)),
):
    ticket = service.get_ticket(db, ticket_id)
    if ticket is None or ticket.user_id != user.id:
        raise HTTPException(status_code=404, detail="ticket_not_found")
    return service.ticket_detail(db, ticket)


@router.post(
    "/me/support/tickets/{ticket_id}/messages",
    response_model=schemas.SupportMessageOut,
    status_code=201,
)
def reply_to_my_ticket(
    ticket_id: int,
    body: schemas.SupportMessageIn,
    request_dep: None = Depends(enforce_support_rate_limit),
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.SUPPORT_READ_OWN)),
):
    _ = request_dep
    try:
        message = service.add_owner_message(
            db, ticket_id=ticket_id, owner_id=user.id, body=body.body
        )
    except ValueError as exc:
        raise _domain_error(exc)
    return service.message_view(message)
