"""Database migration foundation.

Strategy (portable across SQLite dev and future PostgreSQL):

* ``ensure_schema(engine)`` is idempotent: safe on fresh databases and
  safe to re-run on existing ones. It imports every module's models
  (previously only a subset was imported, so fresh databases could miss
  exercise tables), creates missing tables, then records SCHEMA_VERSION.
* Future schema changes add a numbered step to ``MIGRATIONS`` that runs
  exactly once inside a transaction, guarded by the ``schema_version``
  row. Alembic adoption is deferred until the PostgreSQL move requires
  it; the version row migrates with the data.
* Downgrade protection: a database stamped newer than this code refuses
  to boot instead of misbehaving.

Only portable SQLAlchemy column types are used, so the same steps run
on both backends.
"""

import importlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Integer, String, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

logger = logging.getLogger("microchess.db")

SCHEMA_VERSION = 5


class SchemaVersion(Base):
    """Infrastructure metadata (not domain data): which schema this DB has."""

    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[str] = mapped_column(String(32), default="")


# Future schema changes append: (target_version, "description", callable).
# Each callable receives the engine and must be idempotent-safe to skip
# when the database is already at or past its version.
def _derive_username_base(email: object, user_id: object) -> str:
    """Deterministic Phase 1 email -> username backfill (migration only)."""
    local = str(email or "").split("@")[0].strip().lower()
    base = re.sub(r"[^a-z0-9_]", "_", local).strip("_") or f"user{user_id}"
    if len(base) < 3:
        base = (base + "xxx")[:3]
    return base[:30]


def _migrate_v2_accounts(conn) -> None:
    """Phase 2 accounts: username identity, roles, sessions, guests.

    Idempotent: every step checks current state first. Existing rows are
    preserved; Phase 1 emails backfill canonical usernames.
    """
    insp = inspect(conn)
    tables = set(insp.get_table_names())

    if "users" in tables:
        user_cols = {c["name"]: c for c in insp.get_columns("users")}
        if "username" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(30)"))
            user_cols = {c["name"]: c for c in insp.get_columns("users")}
        # Backfill every row lacking a username (Phase 1 email -> username).
        rows = conn.execute(text("SELECT id, email FROM users WHERE username IS NULL")).fetchall()
        used = {
            r[0]
            for r in conn.execute(text("SELECT username FROM users WHERE username IS NOT NULL"))
        }
        for uid, email in rows:
            base = _derive_username_base(email, uid)
            candidate, n = base, 0
            while candidate in used:
                n += 1
                candidate = f"{base[:27]}_{n}"[:30]
            used.add(candidate)
            conn.execute(
                text("UPDATE users SET username = :u WHERE id = :i"), {"u": candidate, "i": uid}
            )
        # Relax the Phase 1 email NOT NULL so new accounts carry no email.
        email_col = {c["name"]: c for c in insp.get_columns("users")}.get("email")
        rebuilt = False
        if email_col is not None and not email_col.get("nullable", True):
            if conn.dialect.name == "sqlite":
                # SQLite cannot ALTER nullability: rebuild via the v2 model DDL
                # (which already carries the username unique index).
                from app.modules.users.models import User

                conn.execute(text("ALTER TABLE users RENAME TO users_legacy_v1"))
                User.__table__.create(bind=conn)
                cols = "id, username, email, password_hash, display_name, is_active, created_at"
                conn.execute(
                    text(f"INSERT INTO users ({cols}) SELECT {cols} FROM users_legacy_v1")
                )
                conn.execute(text("DROP TABLE users_legacy_v1"))
                rebuilt = True
            else:
                conn.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))
        if not rebuilt:
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)")
            )

    if "attempts" in tables:
        attempt_cols = {c["name"] for c in insp.get_columns("attempts")}
        if "guest_session_id" not in attempt_cols:
            conn.execute(text("ALTER TABLE attempts ADD COLUMN guest_session_id INTEGER"))

    # Every account holds at least the default PLAYER role.
    if "users" in tables and "user_roles" in tables:
        conn.execute(
            text(
                "INSERT INTO user_roles (user_id, role, created_at) "
                "SELECT u.id, 'PLAYER', CURRENT_TIMESTAMP FROM users u "
                "WHERE NOT EXISTS (SELECT 1 FROM user_roles r WHERE r.user_id = u.id)"
            )
        )


def _migrate_v3_player(conn) -> None:
    """Phase 3 player platform: profile + external-identity tables.

    No data backfill is required: ``ensure_schema`` already creates the
    new tables via ``Base.metadata.create_all`` (fresh and existing DBs
    alike), and profiles are created lazily on first access, so Phase 2
    accounts gain a profile without touching existing rows. This step
    exists so the version history records the change explicitly.
    """
    _ = conn


def _migrate_v4_ratings(conn) -> None:
    """Phase 4 ratings: snapshot columns on attempts.

    New tables (``player_ratings``, ``rating_events``) are created by
    ``ensure_schema`` via ``Base.metadata.create_all`` on fresh and
    existing databases alike; profiles stay lazy and old attempts are
    never rewritten. SQLite ``ALTER TABLE ... ADD COLUMN`` cannot add a
    non-NULL column without a default, and the rating snapshot is
    legitimately NULL for all pre-rating rows, so plain nullable columns
    are added idempotently when missing.
    """
    insp = inspect(conn)
    tables = set(insp.get_table_names())
    if "attempts" in tables:
        attempt_cols = {c["name"] for c in insp.get_columns("attempts")}
        if "rating_before" not in attempt_cols:
            conn.execute(text("ALTER TABLE attempts ADD COLUMN rating_before FLOAT"))
        if "rating_after" not in attempt_cols:
            # ``rating_delta`` already exists (nullable since Phase 1).
            conn.execute(text("ALTER TABLE attempts ADD COLUMN rating_after FLOAT"))


def _migrate_v5_gamification(conn) -> None:
    """Phase 5 gamification: XP snapshot column on attempts.

    New tables (``player_gamification_state``, ``xp_events``,
    ``player_streaks``, ``player_achievements``) are created by
    ``ensure_schema`` via ``Base.metadata.create_all`` on fresh and
    existing databases alike, and existing attempts/ratings are never
    rewritten (no backfill, no fabricated XP history). SQLite
    ``ALTER TABLE ... ADD COLUMN`` cannot add a non-NULL column without
    a default, and the XP snapshot is legitimately NULL for all
    pre-gamification rows, so a plain nullable column is added
    idempotently when missing.
    """
    insp = inspect(conn)
    tables = set(insp.get_table_names())
    if "attempts" in tables:
        attempt_cols = {c["name"] for c in insp.get_columns("attempts")}
        if "xp_awarded" not in attempt_cols:
            conn.execute(text("ALTER TABLE attempts ADD COLUMN xp_awarded INTEGER"))


MIGRATIONS: list[tuple[int, str, object]] = [
    (2, "phase-02 accounts: username identity, roles, sessions, guests", _migrate_v2_accounts),
    (3, "phase-03 player platform: profiles, external identities", _migrate_v3_player),
    (4, "phase-04 ratings: attempt rating snapshot columns", _migrate_v4_ratings),
    (5, "phase-05 gamification: attempt XP snapshot column", _migrate_v5_gamification),
]


def import_models() -> list[str]:
    """Import every app.modules.*.models so metadata is complete.

    Returns the imported module names (useful for startup logs/tests).
    """
    modules_dir = Path(__file__).resolve().parent.parent / "modules"
    imported: list[str] = []
    for child in sorted(modules_dir.iterdir()):
        if not child.is_dir() or not (child / "models.py").exists():
            continue
        name = f"app.modules.{child.name}.models"
        importlib.import_module(name)
        imported.append(name)
    return imported


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_schema_version(engine: Engine) -> int | None:
    if not inspect(engine).has_table(SchemaVersion.__tablename__):
        return None
    with engine.connect() as conn:
        row = conn.execute(SchemaVersion.__table__.select().order_by(SchemaVersion.version.desc())).first()
    return int(row[0]) if row else None


def _stamp(engine: Engine, version: int) -> None:
    from sqlalchemy.orm import sessionmaker

    session = sessionmaker(bind=engine)()
    try:
        current = session.get(SchemaVersion, version)
        if current is None:
            session.add(SchemaVersion(version=version, applied_at=_utcnow_str()))
            session.commit()
    finally:
        session.close()


def ensure_schema(engine: Engine) -> int:
    """Bring the database to SCHEMA_VERSION. Returns the resulting version."""
    import_models()
    stored = get_schema_version(engine)
    if stored is not None and stored > SCHEMA_VERSION:
        raise RuntimeError(
            f"database schema v{stored} is newer than supported v{SCHEMA_VERSION}; refusing to boot"
        )
    Base.metadata.create_all(bind=engine)
    for target, description, step in MIGRATIONS:
        current = get_schema_version(engine) or 0
        if current >= target:
            continue
        logger.info("applying migration v%s: %s", target, description)
        assert callable(step)
        with engine.begin() as conn:
            step(conn)
        _stamp(engine, target)
    _stamp(engine, SCHEMA_VERSION)
    version = get_schema_version(engine)
    assert version == SCHEMA_VERSION
    return version
