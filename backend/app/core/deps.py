"""Shared FastAPI dependencies (DB session, current user)."""

from collections.abc import Generator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from typing import TYPE_CHECKING

from app.core.security import decode_access_token
from app.db.session import SessionLocal

if TYPE_CHECKING:
    from app.modules.users.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> "User | None":
    # Optional auth: anonymous requests allowed. Rated attempts require a user;
    # callers enforce that. This keeps anonymous-local-progress migration possible later.
    from app.modules.users.models import User

    if creds is None:
        return None
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        return None
    return db.get(User, int(user_id))
