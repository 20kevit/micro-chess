"""User routes. No business logic here, just wiring."""

from fastapi import APIRouter, Depends

from app.core.deps import require_user
from app.modules.users.models import User
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_user)) -> User:
    return user
