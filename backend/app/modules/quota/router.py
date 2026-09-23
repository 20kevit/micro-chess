"""Quota routes: thin wiring over the quota service."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.capabilities import Capability, require_capability
from app.core.deps import get_db
from app.modules.quota import schemas, service
from app.modules.users.models import User

router = APIRouter(tags=["quota"])


@router.get("/me/quota", response_model=schemas.QuotaOut)
def get_my_quota(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability(Capability.USERS_READ)),
):
    return service.usage_for(db, user.id)
