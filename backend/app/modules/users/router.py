"""User routes. No business logic here, just wiring."""

from fastapi import APIRouter, Depends

from app.core.capabilities import Capability, require_capability, roles_for_user
from app.modules.users.models import User
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_capability(Capability.USERS_READ))) -> UserOut:
    # Authoritative current-account state: identity + persisted roles only.
    # No ratings, XP, relationships, or external identities (later phases).
    return UserOut(
        id=user.id,
        username=user.username or "",
        display_name=user.display_name,
        roles=[role.value for role in roles_for_user(user)],
        created_at=user.created_at,
    )
