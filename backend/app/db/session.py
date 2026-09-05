"""Engine/session factory. SQLite by default; PostgreSQL via DATABASE_URL later."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base

# Future PostgreSQL migration: only DATABASE_URL changes. Models use
# portable column types (no SQLite-specific DDL). Add Alembic then.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    # Import models so metadata is populated before create_all.
    from app.modules.exercises import models as _ex  # noqa: F401
    from app.modules.piece_recognition import models as _pr1  # noqa: F401
    from app.modules.progress import models as _pr  # noqa: F401
    from app.modules.puzzles import models as _pz  # noqa: F401
    from app.modules.users import models as _u  # noqa: F401

    Base.metadata.create_all(bind=engine)
