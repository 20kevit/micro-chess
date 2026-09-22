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
from app.modules.users.models import CANONICAL_ROLES, User, UserRole

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30
_USERNAME_RE = re.compile(r"^[a-z0-9_]+$")


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- active roles (Phase 12) -------------------------------------------------
#
# A user may hold several assigned roles; each session carries exactly one
# active role, always a member of the assigned set. The active role selects
# which role-based capability set applies to the session (see
# app.core.capabilities); object-level checks are unchanged.


def assigned_role_codes(user: User) -> list[str]:
    """Canonical assigned roles for an account, resolved from the DB.

    Unknown codes are ignored (fail closed); accounts with no role row
    act as PLAYER (same fallback as ``roles_for_user``).
    """
    codes = [row.role for row in (user.roles or []) if row.role in CANONICAL_ROLES]
    ordered = sorted(set(codes), key=CANONICAL_ROLES.index)
    return ordered or ["PLAYER"]


def normalize_role(role: object) -> str:
    """Validate a client-supplied role code against the canonical set."""
    if not isinstance(role, str):
        raise ValueError("invalid_role")
    code = role.strip().upper()
    if code not in CANONICAL_ROLES:
        raise ValueError("invalid_role")
    return code


def validate_session_role(user: User, role: str) -> str:
    """Confirm a canonical role belongs to this user's assigned set."""
    if role not in assigned_role_codes(user):
        raise ValueError("invalid_role")
    return role


def active_role_for(session: AuthSession, user: User) -> str | None:
    """The session's authoritative active role, or None when the invariant
    ``active_role in assigned roles`` no longer holds (fail closed: the
    caller must reject the session, never auto-pick another role)."""
    code = getattr(session, "active_role", None)
    if not isinstance(code, str) or code not in CANONICAL_ROLES:
        return None
    if code not in assigned_role_codes(user):
        return None
    return code


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


def create_user_session(db: Session, user: User, active_role: str) -> tuple[AuthSession, str]:
    """Create a fresh server-side session (fixation-safe: always new).

    ``active_role`` must belong to the user's assigned roles; anything
    else raises ``invalid_role`` (fail closed, never default silently).
    """
    validate_session_role(user, normalize_role(active_role))
    session = AuthSession(
        public_id=_new_public_id(),
        user_id=user.id,
        token_hash="",
        active_role=normalize_role(active_role),
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


def register_user(db: Session, username: str, password: str, display_name: str, phone: str | None = None) -> tuple[User, str]:
    """Validate → create account → assign PLAYER → open an authenticated session."""
    validate_password(password)
    name = validate_username(username)
    if db.query(User).filter(User.username == name).first():
        raise ValueError("username_taken")
    clean_display = (display_name or "").strip()[:100]
    canonical_phone: str | None = None
    if phone:
        from app.modules.phone_verification.service import normalize_phone as _normalize_phone

        try:
            canonical_phone = _normalize_phone(phone)
        except ValueError:
            raise ValueError("phone_invalid")
        if db.query(User).filter(User.phone == canonical_phone).first():
            raise ValueError("phone_taken")
    user = User(
        username=name,
        email=None,
        password_hash=hash_password(password),
        display_name=clean_display or name,
        phone=canonical_phone,
        phone_verified=False,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role="PLAYER"))
    _, token = create_user_session(db, user, "PLAYER")
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


def login_user(db: Session, user: User, role: str | None = None) -> tuple[str, list[str]]:
    """Open a fresh session for an already-authenticated account.

    Returns ``(token, assigned_roles)``. Single-role accounts log in
    directly (an explicit matching role is accepted; a mismatched one is
    rejected). Multi-role accounts must select a valid role: ``role``
    missing raises ``role_selection_required`` (the router reports the
    assigned set back to the already-authenticated caller); an
    unassigned or unknown role raises ``invalid_role``.
    """
    assigned = assigned_role_codes(user)
    if role is None:
        if len(assigned) != 1:
            raise ValueError("role_selection_required")
        chosen = assigned[0]
    else:
        chosen = validate_session_role(user, normalize_role(role))
    _, token = create_user_session(db, user, chosen)
    db.commit()
    return token, assigned


def switch_session_role(db: Session, session: AuthSession, user: User, role: str) -> str:
    """Change the active role of the current session only.

    The requested role must belong to the user; nothing else changes:
    assigned roles, other sessions, relationships, and capabilities are
    untouched. Returns the new active role.
    """
    chosen = validate_session_role(user, normalize_role(role))
    session.active_role = chosen
    db.commit()
    return chosen


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
