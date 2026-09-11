"""Notification schemas (API boundary)."""

from datetime import datetime

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: int
    type: str
    category: str
    title: str
    body: str = ""
    read_at: datetime | None = None
    created_at: datetime


class UnreadCountOut(BaseModel):
    unread_count: int


class PreferenceOut(BaseModel):
    category: str
    channel: str
    enabled: bool
    mandatory: bool


class PreferenceIn(BaseModel):
    category: str = Field(min_length=1, max_length=20)
    channel: str = Field(default="in_app", min_length=1, max_length=20)
    enabled: bool
