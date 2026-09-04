"""User schemas (API boundary)."""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
