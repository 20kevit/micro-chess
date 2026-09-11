"""Support schemas (API boundary)."""

from datetime import datetime

from pydantic import BaseModel, Field


class SupportTicketCreateIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="", max_length=50)


class SupportMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class SupportMessageOut(BaseModel):
    id: int
    author: str
    body: str
    created_at: datetime


class SupportTicketOut(BaseModel):
    id: int
    subject: str
    category: str = ""
    status: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class SupportTicketDetailOut(SupportTicketOut):
    messages: list[SupportMessageOut] = []


class SupportTicketStaffOut(SupportTicketOut):
    user_id: int
    assigned_admin_id: int | None = None


class SupportTicketStaffDetailOut(SupportTicketStaffOut):
    messages: list[SupportMessageOut] = []
