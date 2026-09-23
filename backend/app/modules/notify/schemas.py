"""Notify schemas (API boundary). No secrets or tokens leak."""

from datetime import datetime

from pydantic import BaseModel, Field


class PushSubscribeIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=500)
    p256dh: str = ""
    auth: str = ""


class PushUnsubscribeIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=500)


class PushSubscriptionOut(BaseModel):
    endpoint: str
    created_at: datetime | None = None


class ChannelLinkOut(BaseModel):
    channel: str
    linked: bool


class PreferenceOut(BaseModel):
    category: str
    channel: str
    enabled: bool
    mandatory: bool


class PreferenceIn(BaseModel):
    category: str
    channel: str
    enabled: bool


class AnalyticsIn(BaseModel):
    type: str = Field(min_length=1, max_length=60)
    props: dict = {}
