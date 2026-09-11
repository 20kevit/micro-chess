"""Auth service: user creation and credential checking."""

from sqlalchemy.orm import Session

from app.core.security import hash_password, validate_password, verify_password
from app.modules.users.models import User


def normalize_email(email: str) -> str:
    """Single normalization point so registration and login agree."""
    return email.strip().lower()


def register_user(db: Session, email: str, password: str, display_name: str) -> User:
    validate_password(password)
    address = normalize_email(email)
    existing = db.query(User).filter(User.email == address).first()
    if existing:
        raise ValueError("email_taken")
    user = User(email=address, password_hash=hash_password(password), display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == normalize_email(email)).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
