"""Auth routes: thin handlers delegating to service."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import audit_event
from app.core.deps import get_current_user_optional, get_db
from app.core.rate_limit import enforce_auth_rate_limit
from app.core.security import create_access_token
from app.modules.auth import schemas, service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
def register(
    body: schemas.RegisterIn,
    db: Session = Depends(get_db),
    _limited: None = Depends(enforce_auth_rate_limit),
):
    try:
        user = service.register_user(db, body.email, body.password, body.display_name)
    except ValueError as exc:
        audit_event(action="auth.register", result="failed")
        if str(exc) == "email_taken":
            raise HTTPException(status_code=400, detail="email_taken")
        raise HTTPException(status_code=422, detail=str(exc))
    audit_event(action="auth.register", actor=user.id)
    return schemas.TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=schemas.TokenOut)
def login(
    body: schemas.LoginIn,
    db: Session = Depends(get_db),
    _limited: None = Depends(enforce_auth_rate_limit),
):
    user = service.authenticate(db, body.email, body.password)
    if user is None:
        # Generic failure: never reveal whether the email exists.
        audit_event(action="auth.login", result="failed")
        raise HTTPException(status_code=401, detail="invalid_credentials")
    audit_event(action="auth.login", actor=user.id)
    return schemas.TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user=Depends(get_current_user_optional)):
    # Stateless JWT foundation: the client discards its token. Server-side
    # session revocation arrives with persisted sessions in Phase 2.
    audit_event(action="auth.logout", actor=user.id if user else None)
    return None
