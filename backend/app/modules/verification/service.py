"""Phone verification via Telegram/Bale contact sharing.

Phone verification is NOT authentication: Telegram/Bale never become a
MicroChess login identity (username + password stay the only login).
They are verification channels that prove ownership of a phone number
through the platform's official contact-sharing capability.

Flow (same for both channels):

1. ``create_session`` — authenticated user asks for a channel; the
   server mints a short-lived, single-use, user-bound session and
   shows a 6-digit pairing code. The code travels user-to-bot as typed
   text, never in a URL; the internal random token never leaves the
   server.
2. The user opens the bot (plain deep link, no secret) and sends the
   pairing code. ``claim_with_code`` binds the provider chat to the
   session and the bot replies with the official Share Contact button.
3. The user presses Share Contact. The provider delivers
   ``contact{phone_number, user_id}`` plus the sender id. The webhook
   requires ``contact.user_id == sender id`` (ownership proof),
   normalizes the phone, rejects phones verified on another account
   (without revealing anything about that account), then
   ``consume_with_contact`` marks the session used, stores the
   provider identity (stable platform id, never the username), links
   the channel address, and sets ``user.phone/phone_verified``.

Every security-sensitive failure fails closed. Replay, expiry,
wrong-user, cross-channel, and duplicate-phone cases are rejected.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.notify.models import ChannelLink, ChannelLinkToken
from app.modules.player.models import PlayerExternalIdentity
from app.modules.users.models import User
from app.modules.verification import bots

CHANNELS = ("telegram", "bale")

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_phone(raw: object) -> str:
    """Canonicalize an Iranian/international phone number.

    Accepts Persian/Arabic digits, spaces, dashes, parens. Iranian
    mobiles (09xxxxxxxx, 989xxxxxxxxx, +989xxxxxxxxx) normalize to
    +989xxxxxxxxx. Other international numbers must be +<7..15 digits>.
    Raises ValueError("phone_invalid"). Single canonical point: the
    SMS-OTP predecessor is removed; verification uses provider
    contacts normalized here.
    """
    if not isinstance(raw, str):
        raise ValueError("phone_invalid")
    text = raw.translate(_FA_DIGITS).translate(_AR_DIGITS).strip()
    cleaned = "".join(ch for ch in text if ch.isdigit() or ch == "+")
    digits = "".join(ch for ch in cleaned if ch.isdigit())
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
    if cleaned.startswith("+") and 7 <= len(digits) <= 15:
        return f"+{digits}"
    raise ValueError("phone_invalid")

SESSION_TTL = timedelta(minutes=15)
PAIRING_DIGITS = 6
MAX_SESSION_ATTEMPTS = 5


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_pairing_code() -> str:
    return f"{secrets.randbelow(10 ** PAIRING_DIGITS):06d}"


def _check_channel(channel: str) -> str:
    channel = (channel or "").strip().lower()
    if channel not in CHANNELS:
        raise ValueError("unknown_channel")
    return channel


def mask_phone(phone: str | None) -> str:
    """Owner-safe display: +98912***6789 (never the full number in lists)."""
    if not phone:
        return ""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 7:
        return "***"
    return f"+{digits[:5]}***{digits[-4:]}"


def verification_state(db: Session, user: User) -> dict:
    """Current verification state for the owner (masked phone)."""
    identity = (
        db.query(PlayerExternalIdentity)
        .filter(
            PlayerExternalIdentity.user_id == user.id,
            PlayerExternalIdentity.provider.in_(CHANNELS),
            PlayerExternalIdentity.is_verified.is_(True),
        )
        .order_by(PlayerExternalIdentity.verified_at.desc())
        .first()
    )
    return {
        "verified": bool(user.phone_verified),
        "phone_masked": mask_phone(user.phone),
        "channel": identity.provider if identity else None,
    }


def create_session(db: Session, user: User, channel: str) -> dict:
    """Mint a one-time verification session (rate-limited by the router).

    Returns the pairing code + public bot address. The internal token
    hash is stored; the token itself is never returned.
    """
    from app.modules.notify import service as notify_service

    channel = _check_channel(channel)
    if user.phone_verified:
        raise ValueError("already_verified")
    # One live session per (user, channel): invalidate older ones so a
    # refresh never leaves two valid codes around.
    now = _utcnow()
    for stale in (
        db.query(ChannelLinkToken)
        .filter(
            ChannelLinkToken.user_id == user.id,
            ChannelLinkToken.channel == channel,
            ChannelLinkToken.used_at.is_(None),
        )
        .all()
    ):
        stale.used_at = now
    token = secrets.token_urlsafe(24)
    code = _new_pairing_code()
    for _ in range(5):
        clash = (
            db.query(ChannelLinkToken)
            .filter(
                ChannelLinkToken.pairing_code == code,
                ChannelLinkToken.used_at.is_(None),
                ChannelLinkToken.expires_at > now,
            )
            .first()
        )
        if clash is None:
            break
        code = _new_pairing_code()
    row = ChannelLinkToken(
        user_id=user.id,
        channel=channel,
        token_hash=_hash_token(token),
        expires_at=now + SESSION_TTL,
        pairing_code=code,
        attempts=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    try:
        notify_service.track(db, user_id=user.id, type="verification_started",
                             props={"channel": channel})
    except Exception:
        pass
    return {
        "channel": channel,
        "pairing_code": code,
        "bot_username": bots.bot_username(channel),
        "bot_url": bots.bot_url(channel),
        "expires_at": row.expires_at,
    }


def _live_session_for_code(db: Session, channel: str, code: str) -> ChannelLinkToken:
    code = (code or "").strip()
    now = _utcnow()
    row = (
        db.query(ChannelLinkToken)
        .filter(
            ChannelLinkToken.channel == channel,
            ChannelLinkToken.pairing_code == code,
            ChannelLinkToken.used_at.is_(None),
        )
        .first()
    )
    if row is None:
        raise ValueError("session_invalid")
    if row.expires_at <= now:
        row.used_at = now
        db.commit()
        raise ValueError("session_expired")
    if (row.attempts or 0) >= MAX_SESSION_ATTEMPTS:
        row.used_at = now
        db.commit()
        raise ValueError("session_invalid")
    return row


def claim_with_code(db: Session, *, channel: str, pairing_code: str,
                    chat_id: str) -> ChannelLinkToken:
    """Bind a provider chat to a live session (bot path, code typed by user)."""
    from app.modules.notify import service as notify_service

    channel = _check_channel(channel)
    chat_id = (chat_id or "").strip()[:100]
    if not chat_id:
        raise ValueError("session_invalid")
    try:
        row = _live_session_for_code(db, channel, pairing_code)
    except ValueError as exc:
        if str(exc) == "session_invalid":
            # Count attempts only against a found-but-wrong row is
            # impossible without the code; brute force is bounded by
            # code space + webhook rate limiting instead.
            pass
        raise
    if row.chat_id and row.chat_id != chat_id:
        row.attempts = (row.attempts or 0) + 1
        db.commit()
        raise ValueError("session_invalid")
    row.chat_id = chat_id
    db.commit()
    db.refresh(row)
    try:
        owner = db.get(User, row.user_id)
        notify_service.track(db, user_id=row.user_id, type="verification_channel_selected",
                             props={"channel": channel})
        _ = owner
    except Exception:
        pass
    return row


def _phone_taken(db: Session, *, phone: str, exclude_user_id: int) -> bool:
    return (
        db.query(User).filter(User.phone == phone, User.id != exclude_user_id).first()
        is not None
    )


def consume_with_contact(
    db: Session, *, channel: str, chat_id: str, sender_id: str,
    contact_user_id: str, phone_raw: str, display_name: str = "",
) -> dict:
    """Consume the chat-bound session with a verified provider contact.

    ``contact_user_id`` must equal ``sender_id`` (the provider's own
    ownership proof: the shared contact belongs to the sender). The
    phone is normalized server-side; phones verified on another
    account are rejected without revealing that account.
    """
    from app.modules.notify import service as notify_service

    channel = _check_channel(channel)
    now = _utcnow()
    row = (
        db.query(ChannelLinkToken)
        .filter(
            ChannelLinkToken.channel == channel,
            ChannelLinkToken.chat_id == (chat_id or "").strip()[:100],
            ChannelLinkToken.used_at.is_(None),
        )
        .first()
    )
    if row is None or row.expires_at <= now:
        if row is not None:
            row.used_at = now
            db.commit()
        raise ValueError("session_expired")
    if str(contact_user_id or "").strip() != str(sender_id or "").strip() or not sender_id:
        _fail(row, db, user_id=row.user_id, channel=channel, reason="identity_mismatch")
        raise ValueError("contact_not_owned")
    try:
        phone = normalize_phone(phone_raw)
    except ValueError:
        _fail(row, db, user_id=row.user_id, channel=channel, reason="phone_invalid")
        raise ValueError("contact_not_owned")
    user = db.get(User, row.user_id)
    if user is None:
        raise ValueError("session_invalid")
    if _phone_taken(db, phone=phone, exclude_user_id=user.id):
        _fail(row, db, user_id=user.id, channel=channel, reason="phone_taken")
        raise ValueError("phone_taken")
    platform_id = str(contact_user_id).strip()[:100]
    # Stable platform id must never collide across accounts (takeover
    # protection); usernames/display names are never identity keys.
    clash = (
        db.query(PlayerExternalIdentity)
        .filter(
            PlayerExternalIdentity.provider == channel,
            PlayerExternalIdentity.provider_user_id == platform_id,
            PlayerExternalIdentity.user_id != user.id,
        )
        .first()
    )
    if clash is not None:
        _fail(row, db, user_id=user.id, channel=channel, reason="identity_taken")
        raise ValueError("phone_taken")
    identity = (
        db.query(PlayerExternalIdentity)
        .filter(
            PlayerExternalIdentity.user_id == user.id,
            PlayerExternalIdentity.provider == channel,
        )
        .first()
    )
    if identity is None:
        identity = PlayerExternalIdentity(
            user_id=user.id, provider=channel, external_username=platform_id,
        )
        db.add(identity)
        db.flush()
    identity.provider_user_id = platform_id
    identity.external_username = platform_id
    identity.display_name = (display_name or "").strip()[:100]
    identity.is_verified = True
    identity.verified_at = now
    user.phone = phone
    user.phone_verified = True
    row.used_at = now
    link = (
        db.query(ChannelLink)
        .filter(ChannelLink.user_id == user.id, ChannelLink.channel == channel)
        .first()
    )
    if link is None:
        link = ChannelLink(user_id=user.id, channel=channel, external_id=platform_id)
        db.add(link)
    else:
        link.external_id = platform_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("phone_taken")
    try:
        notify_service.track(db, user_id=user.id, type="verification_completed",
                             props={"channel": channel})
    except Exception:
        pass
    return {"verified": True, "channel": channel}


def _fail(row: ChannelLinkToken, db: Session, *, user_id: int, channel: str, reason: str) -> None:
    from app.modules.notify import service as notify_service

    row.attempts = (row.attempts or 0) + 1
    if row.attempts >= MAX_SESSION_ATTEMPTS:
        row.used_at = _utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
    try:
        notify_service.track(db, user_id=user_id, type="verification_failed",
                             props={"channel": channel, "reason": reason})
    except Exception:
        pass
