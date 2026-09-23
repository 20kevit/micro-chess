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

SCHEMA_VERSION = 17


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
                    text(
                        f"INSERT INTO users ({cols}, phone, phone_verified, timezone) "
                        f"SELECT {cols}, NULL, 0, 'Asia/Tehran' FROM users_legacy_v1"
                    )
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


def _migrate_v6_admin(conn) -> None:
    """Phase 6 administration: persistent audit log.

    The ``audit_logs`` table is created by ``ensure_schema`` via
    ``Base.metadata.create_all`` on fresh and existing databases alike;
    no data backfill exists (audit history starts with Phase 6, no
    historical records are fabricated). This step exists so the version
    history records the change explicitly.
    """
    _ = conn


def _migrate_v7_content(conn) -> None:
    """Phase 7 content & generators: lifecycle columns on puzzles.

    New tables (``generator_runs``, ``puzzle_status_history``,
    ``puzzle_validations``, ``puzzle_reviews``) are created by
    ``ensure_schema`` via ``Base.metadata.create_all`` on fresh and
    existing databases alike. This step adds the lifecycle columns to
    existing ``puzzles`` tables idempotently and backfills them:

    * ``status`` from the legacy visibility flags (archived -> retired,
      published -> published, else draft)
    * ``source`` defaults to manual (runtime practice rows predate
      provenance tracking; managed content records provenance going
      forward)
    * ``content_hash`` canonical dedup hash for rows carrying an answer
    """
    import json as _json

    insp = inspect(conn)
    tables = set(insp.get_table_names())
    if "puzzles" not in tables:
        return
    puzzle_cols = {c["name"] for c in insp.get_columns("puzzles")}
    # New columns are nullable on upgraded databases (fresh boots get
    # the model nullability via create_all); every row is backfilled
    # below, and new writes always set these fields explicitly.
    if "status" not in puzzle_cols:
        conn.execute(text("ALTER TABLE puzzles ADD COLUMN status VARCHAR(20)"))
    if "source" not in puzzle_cols:
        conn.execute(text("ALTER TABLE puzzles ADD COLUMN source VARCHAR(20)"))
    if "source_reference" not in puzzle_cols:
        conn.execute(text("ALTER TABLE puzzles ADD COLUMN source_reference VARCHAR(255)"))
    if "generator_run_id" not in puzzle_cols:
        conn.execute(text("ALTER TABLE puzzles ADD COLUMN generator_run_id INTEGER"))
    if "difficulty" not in puzzle_cols:
        conn.execute(text("ALTER TABLE puzzles ADD COLUMN difficulty INTEGER"))
    if "target_rating" not in puzzle_cols:
        conn.execute(text("ALTER TABLE puzzles ADD COLUMN target_rating FLOAT"))
    if "content_hash" not in puzzle_cols:
        conn.execute(text("ALTER TABLE puzzles ADD COLUMN content_hash VARCHAR(64)"))
    if "retired_at" not in puzzle_cols:
        conn.execute(text("ALTER TABLE puzzles ADD COLUMN retired_at DATETIME"))
    # Backfill lifecycle state from the legacy visibility projection.
    # Only NULL rows are touched, so re-running this step can never
    # demote content that already advanced through the Phase 07
    # lifecycle (validated/reviewed/approved rows keep draft-like
    # visibility flags by design).
    conn.execute(
        text(
            "UPDATE puzzles SET status = CASE "
            "WHEN is_archived THEN 'retired' "
            "WHEN is_published THEN 'published' "
            "ELSE 'draft' END "
            "WHERE status IS NULL"
        )
    )
    conn.execute(text("UPDATE puzzles SET source = 'manual' WHERE source IS NULL"))
    # Backfill canonical dedup hashes (best-effort; rows that cannot be
    # canonicalized keep NULL and are simply skipped by dedup checks).
    from app.modules.puzzles.validation import content_hash_for

    rows = conn.execute(
        text("SELECT id, exercise_slug, fen, answer_json FROM puzzles WHERE content_hash IS NULL")
    ).fetchall()
    for pid, slug, fen, answer in rows:
        try:
            parsed = answer
            if isinstance(answer, str):
                parsed = _json.loads(answer) if answer else {}
            if not isinstance(parsed, dict):
                continue
            digest = content_hash_for(slug or "", fen, parsed)
        except Exception:
            continue
        conn.execute(
            text("UPDATE puzzles SET content_hash = :h WHERE id = :i"), {"h": digest, "i": pid}
        )
    for index_sql in (
        "CREATE INDEX IF NOT EXISTS ix_puzzles_status ON puzzles (status)",
        "CREATE INDEX IF NOT EXISTS ix_puzzles_content_hash ON puzzles (content_hash)",
        "CREATE INDEX IF NOT EXISTS ix_puzzles_generator_run_id ON puzzles (generator_run_id)",
        "CREATE INDEX IF NOT EXISTS ix_generator_runs_generator_code ON generator_runs (generator_code)",
        "CREATE INDEX IF NOT EXISTS ix_generator_runs_status ON generator_runs (status)",
    ):
        try:
            conn.execute(text(index_sql))
        except Exception:
            # Indexes also ship via create_all on fresh boots; a missing
            # index must never block an upgrade.
            logger.warning("content migration: could not ensure index %s", index_sql)


def _migrate_v8_relationships(conn) -> None:
    """Phase 9 relationships: relationship + assignment tables.

    The ``relationships`` and ``assignments`` tables are created by
    ``ensure_schema`` via ``Base.metadata.create_all`` on fresh and
    existing databases alike; no data backfill exists (relationship
    history starts with Phase 9, no historical edges are fabricated).
    This step exists so the version history records the change
    explicitly.
    """
    _ = conn


def _migrate_v9_adaptive(conn) -> None:
    """Phase 10 adaptive training: recommendation history.

    The ``adaptive_recommendations`` table is created by
    ``ensure_schema`` via ``Base.metadata.create_all`` on fresh and
    existing databases alike; no data backfill exists (recommendation
    history starts with Phase 10, no historical suggestions are
    fabricated). This step exists so the version history records the
    change explicitly.
    """
    _ = conn


def _migrate_v10_support(conn) -> None:
    """Phase 11 support & notifications: tickets, messages, notifications,
    deliveries, preferences.

    The new tables are created by ``ensure_schema`` via
    ``Base.metadata.create_all`` on fresh and existing databases alike;
    no data backfill exists (support/notification history starts with
    Phase 11, no historical records are fabricated). This step exists so
    the version history records the change explicitly.
    """
    _ = conn


def _migrate_v11_active_roles(conn) -> None:
    """Phase 12 active roles: per-session active role on auth_sessions.

    Adds the nullable ``active_role`` column idempotently, then backfills
    every NULL row deterministically to the session owner's first
    canonical assigned role (PLAYER when the account holds no role row,
    matching the ``roles_for_user`` fallback). Existing sessions stay
    valid: single-role users keep exactly their role, and no session
    gains a role the user does not hold. Only NULL rows are touched, so
    re-running this step can never overwrite a role chosen after the
    upgrade.
    """
    insp = inspect(conn)
    tables = set(insp.get_table_names())
    if "auth_sessions" not in tables:
        return
    session_cols = {c["name"] for c in insp.get_columns("auth_sessions")}
    if "active_role" not in session_cols:
        conn.execute(text("ALTER TABLE auth_sessions ADD COLUMN active_role VARCHAR(20)"))
    # Backfill every NULL row to the session owner's first canonical
    # assigned role; accounts with no role row fall back to PLAYER
    # (matching the ``roles_for_user`` fallback). Only NULL rows are
    # touched, so re-running this step can never overwrite a role
    # chosen after the upgrade.
    conn.execute(
        text(
            "UPDATE auth_sessions SET active_role = ("
            "SELECT r.role FROM user_roles r "
            "WHERE r.user_id = auth_sessions.user_id "
            "AND r.role IN ('PLAYER','COACH','PARENT','ADMIN') "
            "ORDER BY CASE r.role "
            "WHEN 'PLAYER' THEN 0 WHEN 'COACH' THEN 1 "
            "WHEN 'PARENT' THEN 2 WHEN 'ADMIN' THEN 3 ELSE 4 END "
            "LIMIT 1) "
            "WHERE active_role IS NULL"
        )
    )
    conn.execute(text("UPDATE auth_sessions SET active_role = 'PLAYER' WHERE active_role IS NULL"))


def _migrate_v13_p2(conn) -> None:
    """P2 mistake taxonomy + evidence: validator detail snapshot on attempts.

    The new ``evidence`` table (plus its indexes/constraints) is created
    by ``ensure_schema`` via ``Base.metadata.create_all`` on fresh and
    existing databases alike, so this step only adds the nullable
    ``validation_detail`` JSON column to pre-P2 ``attempts`` tables
    idempotently. No backfill is performed in either direction: pre-P2
    attempts keep NULL detail and gain no historical evidence (P2 policy:
    the original validator observation is not available exactly as it
    happened, since detail was never persisted). Only portable types.
    """
    insp = inspect(conn)
    tables = set(insp.get_table_names())
    if "attempts" in tables:
        attempt_cols = {c["name"] for c in insp.get_columns("attempts")}
        if "validation_detail" not in attempt_cols:
            conn.execute(text("ALTER TABLE attempts ADD COLUMN validation_detail JSON"))


def _migrate_v12_p1(conn) -> None:
    """P1 attempt context: historical difficulty/rating snapshot columns.

    New ``attempts`` columns (``puzzle_rating_snapshot``,
    ``difficulty_snapshot``) are created by ``ensure_schema`` via
    ``Base.metadata.create_all`` on fresh databases; this step adds them
    idempotently to upgraded databases. No backfill is performed: P1
    policy forbids fabricating historical context, so every pre-P1 row
    legitimately keeps NULL snapshots. Only portable column types.
    """
    insp = inspect(conn)
    tables = set(insp.get_table_names())
    if "attempts" not in tables:
        return
    attempt_cols = {c["name"] for c in insp.get_columns("attempts")}
    if "puzzle_rating_snapshot" not in attempt_cols:
        conn.execute(text("ALTER TABLE attempts ADD COLUMN puzzle_rating_snapshot FLOAT"))
    if "difficulty_snapshot" not in attempt_cols:
        conn.execute(text("ALTER TABLE attempts ADD COLUMN difficulty_snapshot INTEGER"))


def _migrate_v14_p6(conn) -> None:
    """P6 assignment & assessment: context links on attempts, origin/goal on assignments.

    The new ``assessments`` table (plus its indexes/constraints) is
    created by ``ensure_schema`` via ``Base.metadata.create_all`` on
    fresh and existing databases alike, so this step only adds the
    nullable columns idempotently. No backfill is performed except the
    ``source`` default: every pre-P6 assignment row was written by the
    coach-only ``create_assignment`` path, so ``coach_direct`` states a
    fact rather than inferring one. Goals and attempt links never
    existed before P6 and stay NULL on old rows (P6 policy: historical
    truth is never fabricated). Only portable types.
    """
    insp = inspect(conn)
    tables = set(insp.get_table_names())
    if "assignments" in tables:
        assignment_cols = {c["name"] for c in insp.get_columns("assignments")}
        if "source" not in assignment_cols:
            conn.execute(text("ALTER TABLE assignments ADD COLUMN source VARCHAR(30)"))
        if "goal" not in assignment_cols:
            conn.execute(text("ALTER TABLE assignments ADD COLUMN goal VARCHAR(500)"))
        conn.execute(
            text("UPDATE assignments SET source = 'coach_direct' WHERE source IS NULL")
        )
    if "attempts" in tables:
        attempt_cols = {c["name"] for c in insp.get_columns("attempts")}
        if "assignment_id" not in attempt_cols:
            conn.execute(text("ALTER TABLE attempts ADD COLUMN assignment_id INTEGER"))
        if "assessment_id" not in attempt_cols:
            conn.execute(text("ALTER TABLE attempts ADD COLUMN assessment_id INTEGER"))


def _migrate_v15_billing(conn) -> None:
    """Billing domain: plans, prices, subscriptions, coupons, attribution, payments.

    The new ``billing_*`` tables are created by ``ensure_schema`` via
    ``Base.metadata.create_all`` on fresh and existing databases alike;
    no data backfill exists (commercial history starts with v15, no
    historical subscriptions or redemptions are fabricated). Existing
    accounts gain their free-beta subscription lazily on first
    entitlement resolution, so the upgrade never blocks login. This
    step exists so the version history records the change explicitly.
    """
    _ = conn


def _migrate_v16_p11(conn) -> None:
    """P11 onboarding/journey/notifications: phone columns on users.

    New tables (``phone_otps``, ``onboarding_profiles``,
    ``daily_quest_days``, ``daily_quests``, ``push_subscriptions``,
    ``channel_links``, ``channel_link_tokens``, ``analytics_events``,
    ``reminder_logs``) are created by ``ensure_schema`` via
    ``Base.metadata.create_all`` on fresh and existing databases alike;
    this step only adds the nullable ``users`` columns idempotently. No
    backfill: pre-P11 accounts legitimately hold NULL phones and
    default to unverified; timezone defaults to Asia/Tehran for new
    writes (existing rows keep NULL and resolve to the same default in
    service logic). Only portable types.
    """
    insp = inspect(conn)
    tables = set(insp.get_table_names())
    if "users" in tables:
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "phone" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(20)"))
        if "phone_verified" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone_verified BOOLEAN"))
            conn.execute(text("UPDATE users SET phone_verified = 0 WHERE phone_verified IS NULL"))
        if "timezone" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN timezone VARCHAR(60)"))
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)"))
        except Exception:
            logger.warning("p11 migration: could not ensure index ix_users_phone")


def _migrate_v17_verification_quota(conn) -> None:
    """Phone verification via Telegram/Bale + daily quota usage.

    * ``daily_usage`` is created by ``ensure_schema`` via
      ``Base.metadata.create_all`` (fresh and existing DBs alike).
    * ``channel_link_tokens`` gains nullable ``pairing_code``,
      ``attempts``, ``chat_id`` columns idempotently (verification
      sessions reuse this table; legacy pure link tokens keep NULLs).
    * ``player_external_identities`` gains nullable
      ``provider_user_id``/``display_name`` and admits
      ``telegram``/``bale`` providers. SQLite cannot ALTER a CHECK
      constraint, so the table is rebuilt on SQLite (data preserved,
      new columns defaulted); other backends get idempotent ADD
      COLUMNs plus a constraint replacement. Pre-existing
      fide/lichess/chess_com rows are copied verbatim.
    Only portable types. No backfill is fabricated.
    """
    insp = inspect(conn)
    tables = set(insp.get_table_names())
    if "channel_link_tokens" in tables:
        token_cols = {c["name"] for c in insp.get_columns("channel_link_tokens")}
        if "pairing_code" not in token_cols:
            conn.execute(text("ALTER TABLE channel_link_tokens ADD COLUMN pairing_code VARCHAR(12)"))
        if "attempts" not in token_cols:
            conn.execute(text("ALTER TABLE channel_link_tokens ADD COLUMN attempts INTEGER"))
            conn.execute(
                text("UPDATE channel_link_tokens SET attempts = 0 WHERE attempts IS NULL")
            )
        if "chat_id" not in token_cols:
            conn.execute(text("ALTER TABLE channel_link_tokens ADD COLUMN chat_id VARCHAR(100)"))
        try:
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_channel_link_tokens_pairing_code "
                     "ON channel_link_tokens (pairing_code)")
            )
        except Exception:
            logger.warning("v17 migration: could not ensure pairing_code index")
    if "player_external_identities" in tables:
        identity_cols = {c["name"] for c in insp.get_columns("player_external_identities")}
        if conn.dialect.name == "sqlite":
            if "provider_user_id" not in identity_cols:
                from app.modules.player.models import PlayerExternalIdentity

                conn.execute(text("ALTER TABLE player_external_identities RENAME TO identities_legacy_v16"))
                PlayerExternalIdentity.__table__.create(bind=conn)
                cols = ("id, user_id, provider, external_username, rating, rating_type, "
                        "is_verified, verified_at, created_at, updated_at")
                conn.execute(
                    text(
                        f"INSERT INTO player_external_identities ({cols}) "
                        f"SELECT {cols} FROM identities_legacy_v16"
                    )
                )
                conn.execute(text("DROP TABLE identities_legacy_v16"))
        else:
            if "provider_user_id" not in identity_cols:
                conn.execute(
                    text("ALTER TABLE player_external_identities ADD COLUMN provider_user_id VARCHAR(100)")
                )
            if "display_name" not in identity_cols:
                conn.execute(
                    text("ALTER TABLE player_external_identities ADD COLUMN display_name VARCHAR(100)")
                )
            try:
                conn.execute(text("ALTER TABLE player_external_identities "
                                  "DROP CONSTRAINT ck_external_identity_provider"))
            except Exception:
                logger.warning("v17 migration: could not drop legacy provider check")
            # The model CHECK ships via create_all on fresh boots; upgraded
            # PostgreSQL databases rely on service-layer provider validation
            # (single canonical allowlist) rather than a re-added CHECK.


MIGRATIONS: list[tuple[int, str, object]] = [
    (2, "phase-02 accounts: username identity, roles, sessions, guests", _migrate_v2_accounts),
    (3, "phase-03 player platform: profiles, external identities", _migrate_v3_player),
    (4, "phase-04 ratings: attempt rating snapshot columns", _migrate_v4_ratings),
    (5, "phase-05 gamification: attempt XP snapshot column", _migrate_v5_gamification),
    (6, "phase-06 administration: persistent audit log", _migrate_v6_admin),
    (7, "phase-07 content & generators: puzzle lifecycle, provenance, generator jobs", _migrate_v7_content),
    (8, "phase-09 relationships: coach/parent relationships, assignments", _migrate_v8_relationships),
    (9, "phase-10 adaptive training: recommendation history", _migrate_v9_adaptive),
    (10, "phase-11 support & notifications: tickets, messages, deliveries, preferences", _migrate_v10_support),
    (11, "phase-12 active roles: per-session active_role on auth_sessions", _migrate_v11_active_roles),
    (12, "p1 attempt context: nullable puzzle_rating/difficulty snapshot columns", _migrate_v12_p1),
    (13, "p2 evidence: evidence table via create_all + nullable validation_detail column", _migrate_v13_p2),
    (14, "p6 assignment & assessment: assessments table via create_all + nullable assignment/assessment links and source/goal columns", _migrate_v14_p6),
    (15, "billing: plans, prices, subscriptions, coupons, attribution, payments via create_all", _migrate_v15_billing),
    (16, "p11 onboarding/journey/notifications: nullable phone/phone_verified/timezone on users; new tables via create_all", _migrate_v16_p11),
    (17, "verification via telegram/bale + daily quota: token session columns, identity providers/uid columns, daily_usage via create_all", _migrate_v17_verification_quota),
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
