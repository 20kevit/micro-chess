"""Support application service (Phase 11).

Business rules live here; routers stay thin (auth context, capability
checks, validation, response mapping). Every state-changing operation
records a persistent audit row (secret-free, via the Phase 6 audit
helper).

Staff responses emit a ``support.response`` notification event and
ticket closure emits ``support.closed`` through the notification service
(event -> decision -> persistence -> delivery). Emission is best-effort:
a notification failure never fails the support operation.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.admin.models import AuditLog
from app.modules.support.models import (
    MAX_CATEGORY_LEN,
    MAX_MESSAGE_LEN,
    MAX_SUBJECT_LEN,
    STATUS_ANSWERED,
    STATUS_CLOSED,
    STATUS_OPEN,
    SupportMessage,
    SupportTicket,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _record_audit(
    db: Session, *, actor_id: int | None, action: str, target_id: int, metadata: dict
) -> None:
    row = AuditLog(
        actor_user_id=actor_id,
        action=action,
        target_type="support_ticket",
        target_id=str(target_id),
        metadata_json=dict(metadata),
        result="ok",
    )
    db.add(row)
    db.commit()


def _notify(db: Session, *, user_id: int, type: str, title: str, body: str, dedup_key: str) -> None:
    """Best-effort notification emission (never fails the caller)."""
    try:
        from app.modules.notifications import service as notifications

        notifications.emit_event(
            db, user_id=user_id, type=type, title=title, body=body, dedup_key=dedup_key
        )
    except Exception:  # noqa: BLE001 - notification must not break support
        db.rollback()


def create_ticket(
    db: Session, *, owner_id: int, subject: str, message: str, category: str = ""
) -> SupportTicket:
    """Open a ticket with its initial owner message (one commit)."""
    clean_subject = (subject or "").strip()
    clean_message = (message or "").strip()
    if not clean_subject:
        raise ValueError("invalid_subject")
    if not clean_message:
        raise ValueError("invalid_message")
    ticket = SupportTicket(
        user_id=owner_id,
        subject=clean_subject[:MAX_SUBJECT_LEN],
        category=(category or "").strip()[:MAX_CATEGORY_LEN],
        status=STATUS_OPEN,
    )
    db.add(ticket)
    db.flush()
    db.add(
        SupportMessage(
            ticket_id=ticket.id,
            author_user_id=owner_id,
            author_is_staff=False,
            body=clean_message[:MAX_MESSAGE_LEN],
        )
    )
    db.commit()
    db.refresh(ticket)
    _record_audit(
        db,
        actor_id=owner_id,
        action="support.create",
        target_id=ticket.id,
        metadata={"subject": ticket.subject},
    )
    return ticket


def get_ticket(db: Session, ticket_id: int) -> SupportTicket | None:
    return db.get(SupportTicket, ticket_id)


def list_owner_tickets(
    db: Session, *, owner_id: int, status: str | None = None, page: int = 1, page_size: int = 50
) -> tuple[list[SupportTicket], int]:
    from app.modules.support.models import STATUSES

    if status is not None and status not in STATUSES:
        raise ValueError("invalid_status")
    query = db.query(SupportTicket).filter(SupportTicket.user_id == owner_id)
    if status is not None:
        query = query.filter(SupportTicket.status == status)
    total = query.count()
    rows = (
        query.order_by(SupportTicket.created_at.desc(), SupportTicket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def list_all_tickets(
    db: Session,
    *,
    status: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[SupportTicket], int]:
    from app.modules.support.models import STATUSES

    if status is not None and status not in STATUSES:
        raise ValueError("invalid_status")
    query = db.query(SupportTicket)
    if status is not None:
        query = query.filter(SupportTicket.status == status)
    if category:
        query = query.filter(SupportTicket.category == category[:50])
    total = query.count()
    rows = (
        query.order_by(SupportTicket.created_at.desc(), SupportTicket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def ticket_messages(db: Session, ticket_id: int) -> list[SupportMessage]:
    return (
        db.query(SupportMessage)
        .filter(SupportMessage.ticket_id == ticket_id)
        .order_by(SupportMessage.id)
        .all()
    )


def add_owner_message(
    db: Session, *, ticket_id: int, owner_id: int, body: str
) -> SupportMessage:
    """Owner follow-up on an open ticket. Moves answered -> open (needs
    staff attention again). Closed tickets reject follow-ups."""
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.user_id != owner_id:
        raise ValueError("ticket_not_found")
    if ticket.status == STATUS_CLOSED:
        raise ValueError("ticket_closed")
    clean = (body or "").strip()
    if not clean:
        raise ValueError("invalid_message")
    message = SupportMessage(
        ticket_id=ticket.id,
        author_user_id=owner_id,
        author_is_staff=False,
        body=clean[:MAX_MESSAGE_LEN],
    )
    db.add(message)
    if ticket.status == STATUS_ANSWERED:
        ticket.status = STATUS_OPEN
    db.commit()
    db.refresh(message)
    _record_audit(
        db,
        actor_id=owner_id,
        action="support.reply",
        target_id=ticket.id,
        metadata={},
    )
    return message


def add_staff_message(
    db: Session, *, ticket_id: int, staff_id: int, body: str
) -> SupportMessage:
    """Staff response. Moves open -> answered and records the assignee.
    Closed tickets reject responses. Emits a support.response event."""
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise ValueError("ticket_not_found")
    if ticket.status == STATUS_CLOSED:
        raise ValueError("ticket_closed")
    clean = (body or "").strip()
    if not clean:
        raise ValueError("invalid_message")
    message = SupportMessage(
        ticket_id=ticket.id,
        author_user_id=staff_id,
        author_is_staff=True,
        body=clean[:MAX_MESSAGE_LEN],
    )
    db.add(message)
    ticket.status = STATUS_ANSWERED
    if ticket.assigned_admin_id is None:
        ticket.assigned_admin_id = staff_id
    db.commit()
    db.refresh(message)
    _record_audit(
        db,
        actor_id=staff_id,
        action="support.respond",
        target_id=ticket.id,
        metadata={},
    )
    _notify(
        db,
        user_id=ticket.user_id,
        type="support.response",
        title=ticket.subject,
        body=clean[:500],
        dedup_key=f"support-message:{message.id}",
    )
    return message


def close_ticket(db: Session, *, ticket_id: int, staff_id: int) -> tuple[SupportTicket, bool]:
    """Close an open ticket (terminal; idempotent). Emits support.closed."""
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise ValueError("ticket_not_found")
    if ticket.status == STATUS_CLOSED:
        return ticket, False
    ticket.status = STATUS_CLOSED
    ticket.closed_at = _utcnow()
    if ticket.assigned_admin_id is None:
        ticket.assigned_admin_id = staff_id
    db.commit()
    db.refresh(ticket)
    _record_audit(
        db,
        actor_id=staff_id,
        action="support.close",
        target_id=ticket.id,
        metadata={},
    )
    _notify(
        db,
        user_id=ticket.user_id,
        type="support.closed",
        title=ticket.subject,
        body="",
        dedup_key=f"support-closed:{ticket.id}",
    )
    return ticket, True


def ticket_view(ticket: SupportTicket, *, include_owner: bool = False) -> dict:
    """Owner view (default) carries no admin identities; the staff view
    adds owner + assignee ids for operational use."""
    view: dict = {
        "id": ticket.id,
        "subject": ticket.subject,
        "category": ticket.category,
        "status": ticket.status,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "closed_at": ticket.closed_at,
    }
    if include_owner:
        view["user_id"] = ticket.user_id
        view["assigned_admin_id"] = ticket.assigned_admin_id
    return view


def message_view(message: SupportMessage) -> dict:
    return {
        "id": message.id,
        "author": "staff" if message.author_is_staff else "user",
        "body": message.body,
        "created_at": message.created_at,
    }


def ticket_detail(
    db: Session, ticket: SupportTicket, *, include_owner: bool = False
) -> dict:
    return {
        **ticket_view(ticket, include_owner=include_owner),
        "messages": [message_view(row) for row in ticket_messages(db, ticket.id)],
    }
