"""Auth routes: thin handlers delegating to service."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.audit import audit_event
from app.core.capabilities import Capability, require_capability
from app.core.deps import (
    get_current_session_optional,
    get_current_user_optional,
    get_db,
    require_guest_session,
)
from app.core.errors import error_body
from app.core.rate_limit import enforce_auth_rate_limit
from app.modules.auth import schemas, service
from app.modules.auth.models import AuthSession, GuestSession
from app.modules.users.models import User

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
def register(
    body: schemas.RegisterIn,
    db: Session = Depends(get_db),
    _limited: None = Depends(enforce_auth_rate_limit),
):
    try:
        user, token = service.register_user(db, body.username, body.password, body.display_name)
    except ValueError as exc:
        audit_event(action="auth.register", result="failed")
        if str(exc) == "username_taken":
            raise HTTPException(status_code=400, detail="username_taken")
        raise HTTPException(status_code=422, detail=str(exc))
    audit_event(action="auth.register", actor=user.id)
    return schemas.TokenOut(access_token=token)


@router.post("/auth/login", response_model=schemas.TokenOut)
def login(
    body: schemas.LoginIn,
    db: Session = Depends(get_db),
    _limited: None = Depends(enforce_auth_rate_limit),
):
    user = service.authenticate(db, body.username, body.password)
    if user is None:
        # Generic failure: never reveal whether the username exists,
        # the password was wrong, or the account is suspended.
        audit_event(action="auth.login", result="failed")
        raise HTTPException(status_code=401, detail="invalid_credentials")
    try:
        token, _ = service.login_user(db, user, role=body.role)
    except ValueError as exc:
        code = str(exc)
        if code == "role_selection_required":
            # The credentials were valid (already authenticated above),
            # so reporting this account's own assigned roles is safe:
            # nothing about any other user is revealed.
            roles = service.assigned_role_codes(user)
            audit_event(action="auth.login", actor=user.id, result="role_selection_required")
            return JSONResponse(
                status_code=409,
                content=error_body(
                    code="ROLE_SELECTION_REQUIRED",
                    message="This account holds several roles; select one for this session.",
                    details={"roles": roles},
                    legacy_detail="role_selection_required",
                ),
            )
        audit_event(action="auth.login", actor=user.id, result="failed")
        raise HTTPException(status_code=422, detail=code)
    audit_event(action="auth.login", actor=user.id)
    return schemas.TokenOut(access_token=token)


@router.post("/auth/active-role", response_model=schemas.ActiveRoleOut)
def switch_active_role(
    body: schemas.ActiveRoleIn,
    db: Session = Depends(get_db),
    session: AuthSession | None = Depends(get_current_session_optional),
    user: User | None = Depends(get_current_user_optional),
):
    # Switch the active role of the current session only. The requested
    # role must belong to the authenticated user; nothing else changes.
    if session is None or user is None:
        raise HTTPException(status_code=401, detail="auth_required")
    try:
        active_role = service.switch_session_role(db, session, user, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    audit_event(action="auth.active_role_switched", actor=user.id, extra={"role": active_role})
    return schemas.ActiveRoleOut(active_role=active_role, roles=service.assigned_role_codes(user))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: Session = Depends(get_db),
    session: AuthSession | None = Depends(get_current_session_optional),
):
    # Revoke the current server-side session; the token dies with it.
    # Idempotent: an already-invalid credential still yields 204.
    if session is not None:
        service.revoke_session(db, session)
        audit_event(action="auth.logout", actor=session.user_id)
    else:
        audit_event(action="auth.logout", result="no_session")
    return None


@router.post(
    "/guest/session",
    response_model=schemas.GuestTokenOut,
    status_code=status.HTTP_201_CREATED,
)
def create_guest_session(
    db: Session = Depends(get_db),
    _limited: None = Depends(enforce_auth_rate_limit),
):
    guest, token = service.create_guest_session(db)
    audit_event(action="guest.session_created", target_type="guest_session", target_id=guest.id)
    return schemas.GuestTokenOut(guest_token=token, expires_at=guest.expires_at)


@router.get("/guest/session", response_model=schemas.GuestSessionOut)
def get_guest_session(guest: GuestSession = Depends(require_guest_session)):
    return schemas.GuestSessionOut(active=True, expires_at=guest.expires_at)


@router.post("/guest/migrate", response_model=schemas.GuestMigrateOut)
def migrate_guest(
    body: schemas.GuestMigrateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.GUEST_MIGRATE)),
    _limited: None = Depends(enforce_auth_rate_limit),
):
    try:
        outcome = service.migrate_guest_to_user(db, body.guest_token, user)
    except ValueError as exc:
        code = str(exc)
        if code == "guest_already_migrated":
            raise HTTPException(status_code=409, detail=code)
        raise HTTPException(status_code=401, detail="invalid_guest_session")
    audit_event(
        action="guest.migration_completed",
        actor=user.id,
        extra={"migrated_attempts": outcome["migrated_attempts"]},
    )
    return schemas.GuestMigrateOut(**outcome)
