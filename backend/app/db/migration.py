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
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Integer, String, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

logger = logging.getLogger("microchess.db")

SCHEMA_VERSION = 1


class SchemaVersion(Base):
    """Infrastructure metadata (not domain data): which schema this DB has."""

    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[str] = mapped_column(String(32), default="")


# Future schema changes append: (target_version, "description", callable).
# Each callable receives the engine and must be idempotent-safe to skip
# when the database is already at or past its version.
MIGRATIONS: list[tuple[int, str, object]] = []


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
