"""Shared pytest fixtures: isolated in-memory DB + test client."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.db.base import Base


@pytest.fixture()
def db_session():
    from app.modules.captures import models as _cap  # noqa: F401
    from app.modules.exercises import models as _ex  # noqa: F401
    from app.modules.give_check import models as _gc  # noqa: F401
    from app.modules.legal_destinations import models as _ld  # noqa: F401
    from app.modules.pathfinding import models as _pf  # noqa: F401
    from app.modules.piece_recognition import models as _pr1  # noqa: F401
    from app.modules.progress import models as _pr  # noqa: F401
    from app.modules.puzzles import models as _pz  # noqa: F401
    from app.modules.undefended_pieces import models as _up  # noqa: F401
    from app.modules.users import models as _u  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    from app.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
