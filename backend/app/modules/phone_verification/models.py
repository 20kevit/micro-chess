"""Phone verification persistence (P11).

``users`` carries the verified phone attributes (added in migration
v16); ``PhoneOtp`` rows are single-use short-lived challenges. Only the
SHA-256 hash of an OTP is stored; the code value itself never touches
the database or logs.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PhoneOtp(Base):
    __tablename__ = "phone_otps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    # Canonical phone this code was issued for (E.164-ish, e.g. +98912...).
    phone: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    resend_count: Mapped[int] = mapped_column(Integer, default=0)
    # Provider outcome summary only (never the OTP value).
    last_error: Mapped[str] = mapped_column(String(200), default="")
    # True when a real SMS left the provider; test provider counts as sent.
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
