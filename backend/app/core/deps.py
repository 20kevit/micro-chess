"""Shared FastAPI dependencies (DB session, current user/session)."""

import secrets
from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from typing import TYPE_CHECKING

from app.core.security import decode_access_token, hash_token
from app.db.session import SessionLocal

if TYPE_CHECKING:
    from app.modules.auth.models import AuthSession, GuestSession
    from app.modules.users.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _raw_token(creds: HTTPAuthorizationCredentials | None) -> str | None:
    if creds is None or not creds.credentials:
        return None
    return creds.credentials


def get_current_session_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> "AuthSession | None":
    """Validate the bearer token against its server-side session row.

    Accepts only user tokens bound to a live session: correct user,
    matching token hash, unrevoked, unexpired, active account. Anything
    else (guest tokens, legacy sid-less tokens, tampered tokens) yields
    None — fail closed, never raise here.
    """
    from app.modules.auth.models import AuthSession
    from app.modules.users.models import User

    token = _raw_token(creds)
    if token is None:
        return None
    try:
        claims = decode_access_token(token)
        if claims is None or claims.get("sid") is None:
            return None
        try:
            user_id = int(claims["sub"])
        except (TypeError, ValueError):
            return None
        session = (
            db.query(AuthSession)
            .filter(AuthSession.public_id == str(claims["sid"]), AuthSession.user_id == user_id)
            .first()
        )
        if session is None or session.revoked_at is not None:
            return None
        if session.expires_at is not None and session.expires_at <= _utcnow_naive():
            return None
        if not secrets.compare_digest(session.token_hash, hash_token(token)):
            return None
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        return session
    except Exception:
        return None


def get_current_user_optional(
    db: Session = Depends(get_db),
    session: "AuthSession | None" = Depends(get_current_session_optional),
) -> "User | None":
    # Optional auth: anonymous requests allowed. Rated attempts require a user;
    # callers enforce that. Suspended accounts resolve to None (no access).
    from app.modules.users.models import User

    if session is None:
        return None
    return db.get(User, session.user_id)


def get_guest_session_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> "GuestSession | None":
    """Validate a guest bearer token against its guest session row."""
    from app.modules.auth.models import GuestSession

    token = _raw_token(creds)
    if token is None:
        return None
    try:
        claims = decode_access_token(token)
        if claims is None:
            return None
        sub = str(claims.get("sub") or "")
        sid = str(claims.get("sid") or "")
        if not sub.startswith("guest:") or sub[len("guest:") :] != sid:
            return None
        guest = db.query(GuestSession).filter(GuestSession.public_id == sid).first()
        if guest is None or guest.status != "ACTIVE":
            return None
        if guest.expires_at is not None and guest.expires_at <= _utcnow_naive():
            return None
        if not secrets.compare_digest(guest.token_hash, hash_token(token)):
            return None
        return guest
    except Exception:
        return None


def require_guest_session(
    guest: "GuestSession | None" = Depends(get_guest_session_optional),
) -> "GuestSession":
    if guest is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_guest_session")
    return guest
