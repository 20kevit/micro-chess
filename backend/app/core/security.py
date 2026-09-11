"""Password hashing and token helpers. Auth only, no business logic.

Password storage uses a mature adaptive hash. The default scheme is
pbkdf2_sha256 (stdlib-backed, no native dependency); legacy bcrypt
hashes still verify where the bcrypt backend loads. Passwords are
never truncated and never logged.

Phase 2 tokens are server-bound: every user token carries a ``sid``
claim pointing at an ``auth_sessions`` row, and every guest token
carries ``guest:<sid>`` pointing at a ``guest_sessions`` row. The
signature alone never authenticates; the session row must also be
present, unrevoked, unexpired, and hash-bound to the bearer string.
"""

import hashlib
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def validate_password(password: str) -> None:
    """Centralized password policy (see docs/platform/SECURITY.md section 11)."""
    if not isinstance(password, str):
        raise ValueError("password_invalid")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("password_too_short")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("password_too_long")


def hash_password(password: str) -> str:
    validate_password(password)
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bool(pwd_context.verify(plain, hashed))
    except Exception:
        # Unknown hash format or unavailable backend: fail closed.
        return False


def hash_token(token: str) -> str:
    """Bind a bearer string to its session row without storing a secret."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _encode(payload: dict, minutes: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode(
        {**payload, "exp": expire}, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def create_access_token(
    subject: str, *, session_id: str | None = None, expires_minutes: int | None = None
) -> str:
    payload: dict = {"sub": subject}
    if session_id is not None:
        payload["sid"] = session_id
    return _encode(
        payload,
        settings.jwt_expire_minutes if expires_minutes is None else expires_minutes,
    )


def create_guest_token(session_id: str, *, expires_minutes: int) -> str:
    return _encode({"sub": f"guest:{session_id}", "sid": session_id}, expires_minutes)


def decode_access_token(token: str) -> dict | None:
    """Return ``{"sub": ..., "sid": ...}`` or None. Signature/expiry only;
    session-row validation happens in app.core.deps (fail closed)."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        if not sub:
            return None
        return {"sub": str(sub), "sid": payload.get("sid")}
    except Exception:
        return None
