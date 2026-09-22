"""Phone verification service (P11).

Rules: canonical normalization, secure OTP (secrets module, hashed at
rest, 5-minute expiry, single-use, 5 attempt limit, 60s resend
cooldown), safe responses (no OTP value in logs/responses, no
enumeration leak beyond the authenticated owner), transactional
consistency, resend without duplicates, phone change before verify.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.modules.phone_verification.models import PhoneOtp
from app.modules.sms import ports as sms_ports
from app.modules.users.models import User

OTP_TTL = timedelta(minutes=5)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS = 5
OTP_DIGITS = 6

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_phone(raw: object) -> str:
    """Canonicalize an Iranian/international phone number.

    Accepts Persian/Arabic digits, spaces, dashes, parens. Iranian
    mobiles (09xxxxxxxx, 989xxxxxxxxx, +989xxxxxxxxx) normalize to
    +989xxxxxxxxx. Other international numbers must be +<7..15 digits>.
    Raises ValueError("phone_invalid").
    """
    if not isinstance(raw, str):
        raise ValueError("phone_invalid")
    text = raw.translate(_FA_DIGITS).translate(_AR_DIGITS).strip()
    cleaned = "".join(ch for ch in text if ch.isdigit() or ch == "+")
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    # Iranian mobile forms.
    if digits.startswith("0098"):
        digits = digits[4:]
    if len(digits) == 11 and digits.startswith("09"):
        national = digits[1:]
        if len(national) != 10 or not national.startswith("9"):
            raise ValueError("phone_invalid")
        return f"+98{national}"
    if len(digits) == 12 and digits.startswith("989"):
        return f"+{digits}"
    if cleaned.startswith("+") and digits.startswith("98") and len(digits) == 12:
        return f"+{digits}"
    # Generic international fallback.
    if cleaned.startswith("+") and 7 <= len(digits) <= 15:
        return f"+{digits}"
    raise ValueError("phone_invalid")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _new_code() -> str:
    return f"{secrets.randbelow(10**OTP_DIGITS):06d}"


def _otp_text_fa(code: str) -> str:
    # Persian UX; the code digits stay Latin so entry is unambiguous.
    return f"کد تأیید میکروچس: {code}\nاین کد ۵ دقیقه اعتبار دارد."


def _active_otp(db: Session, user_id: int) -> PhoneOtp | None:
    return (
        db.query(PhoneOtp)
        .filter(PhoneOtp.user_id == user_id, PhoneOtp.consumed_at.is_(None))
        .order_by(PhoneOtp.id.desc())
        .first()
    )


def _phone_taken(db: Session, *, phone: str, exclude_user_id: int) -> bool:
    return (
        db.query(User)
        .filter(User.phone == phone, User.id != exclude_user_id)
        .first()
        is not None
    )


def start_verification(db: Session, user: User, raw_phone: str) -> dict:
    """Set (or change) the account phone and issue a fresh OTP.

    Invalidates any previous unconsumed OTP (single active challenge).
    Changing the number before verification resets verified state.
    Sends via the configured SMS provider exactly once per call; on
    provider failure the OTP row persists with sent=False so the client
    can retry via resend (no duplicate send inside this call).
    """
    phone = normalize_phone(raw_phone)
    if _phone_taken(db, phone=phone, exclude_user_id=user.id):
        raise ValueError("phone_taken")
    now = _utcnow()
    # Changing number resets verification (even to the same unverified one).
    if user.phone != phone:
        user.phone = phone
        user.phone_verified = False
        db.flush()
    # Invalidate previous challenges.
    for row in (
        db.query(PhoneOtp)
        .filter(PhoneOtp.user_id == user.id, PhoneOtp.consumed_at.is_(None))
        .all()
    ):
        row.consumed_at = now
    code = _new_code()
    row = PhoneOtp(
        user_id=user.id,
        phone=phone,
        code_hash=_hash_code(code),
        expires_at=now + OTP_TTL,
        attempts=0,
        max_attempts=MAX_ATTEMPTS,
        last_sent_at=now,
        resend_count=0,
        sent=False,
    )
    db.add(row)
    db.flush()
    result = sms_ports.get_provider().send_otp(to=phone, text=_otp_text_fa(code))
    row.sent = bool(result.ok)
    row.last_error = "" if result.ok else result.error[:200]
    db.commit()
    db.refresh(row)
    return {"phone": phone, "expires_at": row.expires_at, "sent": row.sent}


def resend(db: Session, user: User) -> dict:
    """Issue a replacement OTP respecting the resend cooldown."""
    if not user.phone:
        raise ValueError("phone_missing")
    now = _utcnow()
    current = _active_otp(db, user.id)
    if current is not None:
        if current.expires_at > now and (now - current.last_sent_at) < RESEND_COOLDOWN:
            raise ValueError("resend_cooldown")
        current.consumed_at = now
    code = _new_code()
    row = PhoneOtp(
        user_id=user.id,
        phone=user.phone,
        code_hash=_hash_code(code),
        expires_at=now + OTP_TTL,
        attempts=0,
        max_attempts=MAX_ATTEMPTS,
        last_sent_at=now,
        resend_count=(current.resend_count + 1) if current else 0,
        sent=False,
    )
    db.add(row)
    db.flush()
    result = sms_ports.get_provider().send_otp(to=user.phone, text=_otp_text_fa(code))
    row.sent = bool(result.ok)
    row.last_error = "" if result.ok else result.error[:200]
    db.commit()
    db.refresh(row)
    return {"phone": user.phone, "expires_at": row.expires_at, "sent": row.sent}


def verify(db: Session, user: User, code: str) -> dict:
    """Verify the active OTP. Single-use, attempt-limited, expiring.

    Wrong/expired responses are generic ("code_invalid"/"code_expired")
    and never reveal the expected value. Exceeding attempts consumes the
    challenge (replay-safe).
    """
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code_invalid")
    candidate = code.strip()
    row = _active_otp(db, user.id)
    now = _utcnow()
    if row is None:
        raise ValueError("code_invalid")
    if row.expires_at <= now:
        row.consumed_at = now
        db.commit()
        raise ValueError("code_expired")
    if (row.attempts or 0) >= (row.max_attempts or MAX_ATTEMPTS):
        row.consumed_at = now
        db.commit()
        raise ValueError("code_invalid")
    if not secrets.compare_digest(row.code_hash, _hash_code(candidate)):
        row.attempts = (row.attempts or 0) + 1
        if row.attempts >= (row.max_attempts or MAX_ATTEMPTS):
            row.consumed_at = now
        db.commit()
        raise ValueError("code_invalid")
    # Success: single-use + verified status persisted transactionally.
    row.consumed_at = now
    if user.phone and row.phone == user.phone:
        user.phone_verified = True
    else:
        # Phone changed out-of-band; bind the verified number explicitly.
        if _phone_taken(db, phone=row.phone, exclude_user_id=user.id):
            db.commit()
            raise ValueError("phone_taken")
        user.phone = row.phone
        user.phone_verified = True
    db.commit()
    return {"phone": user.phone or row.phone, "verified": True}


def status_of(user: User) -> dict:
    return {"phone": user.phone, "verified": bool(user.phone_verified)}
