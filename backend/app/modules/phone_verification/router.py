"""Phone verification routes: thin wiring over the service."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.modules.phone_verification import schemas, service
from app.modules.users.models import User

router = APIRouter(tags=["phone"])


def _domain_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code in ("code_invalid", "code_expired", "resend_cooldown", "phone_missing"):
        return HTTPException(status_code=422, detail=code)
    if code in ("phone_invalid",):
        return HTTPException(status_code=422, detail=code)
    if code in ("phone_taken",):
        return HTTPException(status_code=409, detail=code)
    return HTTPException(status_code=400, detail=code)


@router.get("/me/phone", response_model=schemas.PhoneStatusOut)
def get_phone_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    _ = db
    return service.status_of(user)


@router.post("/me/phone/start", response_model=schemas.OtpSentOut)
def start_phone(
    body: schemas.PhoneStartIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        return service.start_verification(db, user, body.phone)
    except ValueError as exc:
        raise _domain_error(exc)


@router.post("/me/phone/resend", response_model=schemas.OtpSentOut)
def resend_phone(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        return service.resend(db, user)
    except ValueError as exc:
        raise _domain_error(exc)


@router.post("/me/phone/verify", response_model=schemas.PhoneStatusOut)
def verify_phone(
    body: schemas.PhoneVerifyIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    try:
        return service.verify(db, user, body.code)
    except ValueError as exc:
        raise _domain_error(exc)
