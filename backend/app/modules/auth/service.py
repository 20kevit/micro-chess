"""Account lifecycle: registration, login, sessions, guests, migration.

Canonical identity is ``username`` (normalized strip + lower, unique).
Business rules live here; routers stay thin.
"""

import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_guest_token,
    decode_access_token,
    hash_password,
    hash_token,
    validate_password,
    verify_password,
)
from app.modules.auth.models import AuthSession, GuestSession
from app.modules.progress.models import Attempt
from app.modules.users.models import User, UserRole

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30
_USERNAME_RE = re.compile(r"^[a-z0-9_]+$")


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_username(username: str) -> str:
    """Single canonical normalization point for register/login/lookup."""
    return username.strip().lower()


def validate_username(username: str) -> str:
    """Validate against the canonical policy; return the normalized form."""
    if not isinstance(username, str):
        raise ValueError("username_invalid")
    name = normalize_username(username)
    if (
        len(name) < USERNAME_MIN_LENGTH
        or len(name) > USERNAME_MAX_LENGTH
        or _USERNAME_RE.match(name) is None
    ):
        raise ValueError("username_invalid")
    return name


def _new_public_id() -> str:
    return secrets.token_urlsafe(24)


def _session_expiry() -> datetime:
    return _utcnow_naive() + timedelta(minutes=settings.jwt_expire_minutes)


def create_user_session(db: Session, user: User) -> tuple[AuthSession, str]:
    """Create a fresh server-side session (fixation-safe: always new)."""
    session = AuthSession(
        public_id=_new_public_id(),
        user_id=user.id,
        token_hash="",
        created_at=_utcnow_naive(),
        expires_at=_session_expiry(),
    )
    db.add(session)
    db.flush()
    token = create_access_token(str(user.id), session_id=session.public_id)
    session.token_hash = hash_token(token)
    return session, token


def revoke_session(db: Session, session: AuthSession) -> None:
    session.revoked_at = _utcnow_naive()
    db.commit()


def register_user(db: Session, username: str, password: str, display_name: str) -> tuple[User, str]:
    """Validate → create account → assign PLAYER → open an authenticated session."""
    validate_password(password)
    name = validate_username(username)
    if db.query(User).filter(User.username == name).first():
        raise ValueError("username_taken")
    clean_display = (display_name or "").strip()[:100]
    user = User(
        username=name,
        email=None,
        password_hash=hash_password(password),
        display_name=clean_display or name,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role="PLAYER"))
    _, token = create_user_session(db, user)
    db.commit()
    db.refresh(user)
    return user, token


def authenticate(db: Session, username: str, password: str) -> User | None:
    """Generic result: unknown user, wrong password, and suspended account
    are indistinguishable (enumeration resistance)."""
    if not isinstance(username, str) or not isinstance(password, str):
        return None
    user = db.query(User).filter(User.username == normalize_username(username)).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def login_user(db: Session, user: User) -> str:
    """Open a fresh session for an already-authenticated account."""
    _, token = create_user_session(db, user)
    db.commit()
    return token


def create_guest_session(db: Session) -> tuple[GuestSession, str]:
    guest = GuestSession(
        public_id=_new_public_id(),
        token_hash="",
        status="ACTIVE",
        created_at=_utcnow_naive(),
        expires_at=_utcnow_naive() + timedelta(days=settings.guest_session_expire_days),
    )
    db.add(guest)
    db.flush()
    token = create_guest_token(
        guest.public_id,
        expires_minutes=settings.guest_session_expire_days * 24 * 60,
    )
    guest.token_hash = hash_token(token)
    db.commit()
    db.refresh(guest)
    return guest, token


def get_guest_session(db: Session, token: str) -> GuestSession | None:
    """Resolve the guest source identity from the server-issued credential."""
    if not isinstance(token, str) or not token:
        return None
    claims = decode_access_token(token)
    if claims is None:
        return None
    sub = str(claims.get("sub") or "")
    sid = str(claims.get("sid") or "")
    if not sub.startswith("guest:") or sub[len("guest:") :] != sid:
        return None
    guest = db.query(GuestSession).filter(GuestSession.public_id == sid).first()
    if guest is None or guest.status != "ACTIVE":
        return None
    if guest.expires_at is not None and guest.expires_at <= _utcnow_naive():
        return None
    try:
        import secrets as _secrets

        if not _secrets.compare_digest(guest.token_hash, hash_token(token)):
            return None
    except Exception:
        return None
    return guest


def migrate_guest_to_user(db: Session, guest_token: str, user: User) -> dict:
    """Move guest-owned attempts to the authenticated account.

    Atomic (single commit), idempotent (a completed migration replays to
    the same account without duplicating), replay-resistant (the guest
    reaches a terminal MIGRATED state).
    """
    guest = get_guest_session(db, guest_token)
    if guest is None:
        # A migrated guest no longer resolves as ACTIVE; report the
        # terminal outcome idempotently instead of a bare failure.
        completed = _find_completed_migration(db, guest_token)
        if completed is not None and completed.migrated_to_user_id == user.id:
            return {"migrated_attempts": 0, "already_migrated": True}
        if completed is not None:
            raise ValueError("guest_already_migrated")
        raise ValueError("invalid_guest_session")
    moved = (
        db.query(Attempt)
        .filter(Attempt.guest_session_id == guest.id, Attempt.user_id.is_(None))
        .update(
            {Attempt.user_id: user.id, Attempt.guest_session_id: None},
            synchronize_session=False,
        )
    )
    guest.status = "MIGRATED"
    guest.migrated_to_user_id = user.id
    guest.migrated_at = _utcnow_naive()
    db.commit()
    return {"migrated_attempts": int(moved), "already_migrated": False}


def _find_completed_migration(db: Session, token: str) -> GuestSession | None:
    claims = decode_access_token(token)
    if claims is None:
        return None
    sid = str(claims.get("sid") or "")
    if not sid:
        return None
    guest = db.query(GuestSession).filter(GuestSession.public_id == sid).first()
    if guest is None or guest.status != "MIGRATED":
        return None
    try:
        import secrets as _secrets

        if not _secrets.compare_digest(guest.token_hash, hash_token(token)):
            return None
    except Exception:
        return None
    return guest
