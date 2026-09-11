"""Password hashing and JWT helpers. Auth only, no business logic.

Password storage uses a mature adaptive hash. The default scheme is
pbkdf2_sha256 (stdlib-backed, no native dependency); legacy bcrypt
hashes still verify where the bcrypt backend loads. Passwords are
never truncated and never logged.
"""

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


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        return str(sub) if sub else None
    except Exception:
        return None
