"""User schemas (API boundary). Never expose hashes or session material."""

from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    roles: list[str]
    # Active role of the current session (Phase 12): always a member of
    # ``roles``. Clients render it; the server remains authoritative.
    active_role: str
    created_at: datetime

    model_config = {"from_attributes": True}
