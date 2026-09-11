"""Player platform logic: profile, external identities, history, progress.

All reads/writes are scoped to the authenticated account: callers pass the
server-resolved ``User`` and never a client-supplied user id, so one player
can never reach another player's data (IDOR-safe by construction).

History and progress read the authoritative ``attempts`` rows owned by the
progress domain; nothing is duplicated or recalculated here. Practice
attempts never carry a rating delta and no rating math lives in this
module (ratings belong to Phase 4).
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.exercises import registry
from app.modules.exercises.models import Exercise
from app.modules.player.models import PROVIDERS, PlayerExternalIdentity, PlayerProfile
from app.modules.progress.models import Attempt
from app.modules.rule_engine.base import AttemptMode

# Validation bounds (single canonical point; also enforced by schemas).
DISPLAY_NAME_MAX = 100
BIO_MAX = 500
AVATAR_REFERENCE_MAX = 255
EXTERNAL_USERNAME_MAX = 100
RATING_TYPE_MAX = 30
RATING_MIN = 0
RATING_MAX = 5000
RECENT_LIMIT = 5


def _clean(value: object, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        raise ValueError("profile_field_too_long")
    return text


def normalize_provider(provider: object) -> str:
    """Strict allowlist: only the canonical providers are accepted."""
    code = str(provider or "").strip().lower()
    if code not in PROVIDERS:
        raise ValueError("unknown_provider")
    return code


def normalize_external_username(username: object) -> str:
    name = str(username or "").strip().lower()
    if not name or len(name) > EXTERNAL_USERNAME_MAX:
        raise ValueError("external_username_invalid")
    return name


# --- profile ---------------------------------------------------------------


def get_or_create_profile(db: Session, user) -> PlayerProfile:
    """Return the account's profile, creating it lazily on first read.

    Lazy creation keeps the v3 migration a pure table creation: existing
    Phase 2 accounts gain a profile on first access instead of via a
    data backfill.
    """
    profile = db.query(PlayerProfile).filter(PlayerProfile.user_id == user.id).first()
    if profile is None:
        profile = PlayerProfile(
            user_id=user.id,
            display_name=(user.display_name or user.username or "")[:DISPLAY_NAME_MAX],
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(
    db: Session,
    user,
    *,
    display_name: str | None = None,
    bio: str | None = None,
    avatar_reference: str | None = None,
) -> PlayerProfile:
    """Update only the editable profile fields. Account security state
    (roles, status, credentials) is never writable here."""
    profile = get_or_create_profile(db, user)
    if display_name is not None:
        clean = _clean(display_name, DISPLAY_NAME_MAX)
        if not clean:
            raise ValueError("display_name_invalid")
        profile.display_name = clean
    if bio is not None:
        profile.bio = _clean(bio, BIO_MAX)
    if avatar_reference is not None:
        clean = _clean(avatar_reference, AVATAR_REFERENCE_MAX)
        if ".." in clean or "\\" in clean:
            raise ValueError("avatar_reference_invalid")
        profile.avatar_reference = clean
    db.commit()
    db.refresh(profile)
    return profile


# --- external chess identities ----------------------------------------------


def list_identities(db: Session, user) -> list[PlayerExternalIdentity]:
    return (
        db.query(PlayerExternalIdentity)
        .filter(PlayerExternalIdentity.user_id == user.id)
        .order_by(PlayerExternalIdentity.id)
        .all()
    )


def _validate_identity_fields(
    *,
    rating: int | None,
    rating_type: str | None,
) -> tuple[int | None, str | None]:
    clean_rating: int | None = None
    if rating is not None:
        if isinstance(rating, bool) or not isinstance(rating, int):
            raise ValueError("external_rating_invalid")
        if rating < RATING_MIN or rating > RATING_MAX:
            raise ValueError("external_rating_invalid")
        clean_rating = rating
    clean_type: str | None = None
    if rating_type is not None:
        clean_type = _clean(rating_type, RATING_TYPE_MAX) or None
    return clean_rating, clean_type


def add_identity(
    db: Session,
    user,
    *,
    provider: str,
    username: str,
    rating: int | None = None,
    rating_type: str | None = None,
) -> PlayerExternalIdentity:
    """Link a self-reported external identity. Uniqueness is enforced by
    the database (owner+provider and provider+account); application checks
    give a clean conflict error first."""
    code = normalize_provider(provider)
    name = normalize_external_username(username)
    clean_rating, clean_type = _validate_identity_fields(rating=rating, rating_type=rating_type)
    if (
        db.query(PlayerExternalIdentity)
        .filter(
            PlayerExternalIdentity.user_id == user.id,
            PlayerExternalIdentity.provider == code,
        )
        .first()
    ):
        raise ValueError("identity_exists")
    if (
        db.query(PlayerExternalIdentity)
        .filter(
            PlayerExternalIdentity.provider == code,
            PlayerExternalIdentity.external_username == name,
        )
        .first()
    ):
        raise ValueError("identity_taken")
    identity = PlayerExternalIdentity(
        user_id=user.id,
        provider=code,
        external_username=name,
        rating=clean_rating,
        rating_type=clean_type,
        is_verified=False,
        verified_at=None,
    )
    db.add(identity)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("identity_taken") from exc
    db.refresh(identity)
    return identity


def update_identity(
    db: Session,
    user,
    identity_id: int,
    *,
    username: str | None = None,
    username_set: bool = False,
    rating: int | None = None,
    rating_set: bool = False,
    rating_type: str | None = None,
    rating_type_set: bool = False,
) -> PlayerExternalIdentity | None:
    """Update the editable fields of an owned identity. Returns None when
    the identity does not exist or belongs to another account (callers map
    both to 404 so existence never leaks). Verification state is never
    client-settable. Explicit null clears the optional rating fields."""
    identity = (
        db.query(PlayerExternalIdentity)
        .filter(
            PlayerExternalIdentity.id == identity_id,
            PlayerExternalIdentity.user_id == user.id,
        )
        .first()
    )
    if identity is None:
        return None
    if username_set and username is not None:
        name = normalize_external_username(username)
        clash = (
            db.query(PlayerExternalIdentity)
            .filter(
                PlayerExternalIdentity.provider == identity.provider,
                PlayerExternalIdentity.external_username == name,
                PlayerExternalIdentity.id != identity.id,
            )
            .first()
        )
        if clash is not None:
            raise ValueError("identity_taken")
        identity.external_username = name
    if rating_set:
        if rating is None:
            identity.rating = None
        else:
            clean_rating, _ = _validate_identity_fields(rating=rating, rating_type=None)
            identity.rating = clean_rating
    if rating_type_set:
        if rating_type is None:
            identity.rating_type = None
        else:
            _, clean_type = _validate_identity_fields(rating=None, rating_type=rating_type)
            identity.rating_type = clean_type
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("identity_taken") from exc
    db.refresh(identity)
    return identity


def delete_identity(db: Session, user, identity_id: int) -> bool:
    """Remove an owned identity. False when missing or foreign (→ 404)."""
    identity = (
        db.query(PlayerExternalIdentity)
        .filter(
            PlayerExternalIdentity.id == identity_id,
            PlayerExternalIdentity.user_id == user.id,
        )
        .first()
    )
    if identity is None:
        return False
    db.delete(identity)
    db.commit()
    return True


# --- training history --------------------------------------------------------


def _history_query(
    db: Session,
    user,
    *,
    exercise: str | None = None,
    mode: AttemptMode | None = None,
    correct: bool | None = None,
):
    q = db.query(Attempt).filter(Attempt.user_id == user.id)
    if exercise:
        q = q.filter(Attempt.exercise_slug == exercise)
    if mode is not None:
        q = q.filter(Attempt.mode == mode.value)
    if correct is True:
        q = q.filter(Attempt.result == "correct")
    elif correct is False:
        q = q.filter(Attempt.result != "correct")
    return q.order_by(Attempt.id.desc())


def list_attempts(
    db: Session,
    user,
    *,
    exercise: str | None = None,
    mode: AttemptMode | None = None,
    correct: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[Attempt]:
    return (
        _history_query(db, user, exercise=exercise, mode=mode, correct=correct)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def get_attempt(db: Session, user, attempt_id: int) -> Attempt | None:
    """One owned attempt, or None when missing/foreign (→ 404 either way)."""
    return (
        db.query(Attempt)
        .filter(Attempt.id == attempt_id, Attempt.user_id == user.id)
        .first()
    )


# --- progress -----------------------------------------------------------------


def _known_exercise_slugs(db: Session) -> set[str]:
    slugs = set(registry.registered_slugs())
    for (slug,) in db.query(Exercise.slug).all():
        slugs.add(slug)
    return slugs


def is_known_exercise(db: Session, slug: str) -> bool:
    """True when the slug names a registered or catalogued exercise."""
    return slug in _known_exercise_slugs(db)


def progress_summary(db: Session, user) -> dict:
    """Basic personal summary (all-time): totals plus per-exercise
    attempts/correct/accuracy/last-practiced. Straightforward queries over
    authoritative attempts — no analytics warehouse, no time ranges."""
    rows = db.query(Attempt).filter(Attempt.user_id == user.id).order_by(Attempt.id.desc()).all()
    total = len(rows)
    correct = sum(1 for row in rows if row.result == "correct")
    by_exercise: dict[str, dict] = {}
    for row in rows:
        entry = by_exercise.setdefault(
            row.exercise_slug,
            {"exercise": row.exercise_slug, "attempts": 0, "correct": 0, "last_practiced_at": None},
        )
        entry["attempts"] += 1
        if row.result == "correct":
            entry["correct"] += 1
        if entry["last_practiced_at"] is None and row.created_at is not None:
            entry["last_practiced_at"] = row.created_at
    exercises = []
    for entry in sorted(by_exercise.values(), key=lambda e: e["exercise"]):
        attempts = entry["attempts"]
        exercises.append(
            {
                **entry,
                "accuracy": (entry["correct"] / attempts) if attempts else 0.0,
            }
        )
    return {
        "attempts": total,
        "correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "exercises": exercises,
    }


def exercise_progress(db: Session, user, slug: str) -> dict | None:
    """Progress for one exercise, or None when the slug is unknown."""
    if slug not in _known_exercise_slugs(db):
        return None
    rows = (
        db.query(Attempt)
        .filter(Attempt.user_id == user.id, Attempt.exercise_slug == slug)
        .order_by(Attempt.id.desc())
        .all()
    )
    total = len(rows)
    correct = sum(1 for row in rows if row.result == "correct")
    return {
        "exercise": slug,
        "attempts": total,
        "correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "last_practiced_at": rows[0].created_at if rows else None,
    }


# --- dashboard ------------------------------------------------------------------


def dashboard(db: Session, user) -> dict:
    """Player home read model: profile + progress + recent activity.

    A read model only — every number derives from the functions above, so
    there is no second source of truth. No ratings, XP, streaks, or
    achievements (later phases)."""
    profile = get_or_create_profile(db, user)
    summary = progress_summary(db, user)
    recent = _history_query(db, user).limit(RECENT_LIMIT).all()
    return {"profile": profile, "progress": summary, "recent_attempts": recent}
