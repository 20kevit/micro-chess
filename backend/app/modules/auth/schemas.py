"""Auth schemas (API boundary). No secrets leave the server."""

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    username: str
    password: str
    display_name: str = ""
    # Optional marketing attribution captured at registration (first-touch
    # source). Best-effort only: registration succeeds even when these are
    # absent or invalid; the billing service validates coupons separately.
    coupon_code: str | None = None
    campaign_slug: str | None = None
    source: str | None = None
    medium: str | None = None
    content: str | None = None
    landing_path: str | None = None
    referrer: str | None = None


class LoginIn(BaseModel):
    username: str
    password: str
    # Optional active-role selection for multi-role accounts. Single-role
    # accounts log in without it (backward compatible); multi-role
    # accounts without it receive 409 role_selection_required.
    role: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ActiveRoleIn(BaseModel):
    role: str = Field(min_length=1)


class ActiveRoleOut(BaseModel):
    active_role: str
    roles: list[str]


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
