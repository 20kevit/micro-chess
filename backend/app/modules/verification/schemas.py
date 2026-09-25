"""Verification schemas (API boundary). No tokens, phones, or secrets leave the server."""

from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreateIn(BaseModel):
    channel: str = Field(min_length=1, max_length=20)


class SessionOut(BaseModel):
    channel: str
    pairing_code: str
    bot_username: str
    bot_url: str
    expires_at: datetime


class VerificationStatusOut(BaseModel):
    verified: bool
    phone_masked: str
    channel: str | None
    available_channels: list[str]
