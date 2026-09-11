"""Auth schemas (API boundary). No secrets leave the server."""

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    username: str
    password: str
    display_name: str = ""


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GuestTokenOut(BaseModel):
    guest_token: str
    expires_at: datetime


class GuestSessionOut(BaseModel):
    active: bool
    expires_at: datetime


class GuestMigrateIn(BaseModel):
    guest_token: str = Field(min_length=1)


class GuestMigrateOut(BaseModel):
    migrated_attempts: int
    already_migrated: bool
