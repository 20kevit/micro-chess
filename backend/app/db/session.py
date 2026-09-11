"""Engine/session factory. SQLite by default; PostgreSQL via DATABASE_URL later."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Future PostgreSQL migration: only DATABASE_URL changes. Models use
# portable column types (no SQLite-specific DDL). Schema evolution goes
# through app.db.migration steps, guarded by the schema_version row.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from app.db.migration import ensure_schema

    ensure_schema(engine)
