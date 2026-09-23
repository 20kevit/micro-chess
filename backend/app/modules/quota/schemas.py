"""Quota schemas (API boundary). No internal ratings or billing internals."""

from pydantic import BaseModel


class QuotaOut(BaseModel):
    used: int
    limit: int
    remaining: int
    plan: str
    local_date: str
    can_practice: bool
    upgrade_available: bool
