"""User routes. No business logic here, just wiring."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, active_role_for_session, require_capability, roles_for_user
from app.core.deps import get_current_session_optional, get_db
from app.modules.auth.models import AuthSession
from app.modules.users.models import User
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(
    user: User = Depends(require_capability(Capability.USERS_READ)),
    session: AuthSession | None = Depends(get_current_session_optional),
    db: Session = Depends(get_db),
) -> UserOut:
    # Authoritative current-account state: identity + persisted roles +
    # this session's active role (resolved server-side, never trusted
    # from the client). No ratings, XP, relationships, or external
    # identities (later phases).
    _ = db
    active = active_role_for_session(session, user)
    if active is None:  # pragma: no cover - require_capability already fails closed
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="active_role_revoked")
    return UserOut(
        id=user.id,
        username=user.username or "",
        display_name=user.display_name,
        roles=[role.value for role in roles_for_user(user)],
        active_role=active.value,
        created_at=user.created_at,
    )
