"""Phone verification schemas (API boundary). No OTP values leave the server."""

from datetime import datetime

from pydantic import BaseModel, Field


class PhoneStartIn(BaseModel):
    phone: str = Field(min_length=1, max_length=30)


class PhoneVerifyIn(BaseModel):
    code: str = Field(min_length=1, max_length=12)


class PhoneStatusOut(BaseModel):
    phone: str | None
    verified: bool


class OtpSentOut(BaseModel):
    phone: str
    expires_at: datetime
    sent: bool
