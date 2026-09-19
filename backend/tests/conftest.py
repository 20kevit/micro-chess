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
    from app.modules.admin import models as _admin  # noqa: F401
    from app.modules.adaptive import models as _adapt  # noqa: F401
    from app.modules.assessments import models as _assess  # noqa: F401
    from app.modules.auth import models as _auth  # noqa: F401
    from app.modules.balance_scale import models as _bs  # noqa: F401
    from app.modules.blindfold_calculation import models as _bc  # noqa: F401
    from app.modules.blindfold_square_vision import models as _bsv  # noqa: F401
    from app.modules.captures import models as _cap  # noqa: F401
    from app.modules.chinese_board import models as _cb  # noqa: F401
    from app.modules.exercises import models as _ex  # noqa: F401
    from app.modules.gamification_engine import models as _g  # noqa: F401
    from app.modules.generators import models as _gen  # noqa: F401
    from app.modules.get_out_of_check import models as _goc  # noqa: F401
    from app.modules.give_check import models as _gc  # noqa: F401
    from app.modules.legal_destinations import models as _ld  # noqa: F401
    from app.modules.material_comparison import models as _hs  # noqa: F401
    from app.modules.pathfinding import models as _pf  # noqa: F401
    from app.modules.pathfinding_obstacles import models as _pfo  # noqa: F401
    from app.modules.piece_recognition import models as _pr1  # noqa: F401
    from app.modules.player import models as _player  # noqa: F401
    from app.modules.notifications import models as _notif  # noqa: F401
    from app.modules.progress import models as _pr  # noqa: F401
    from app.modules.puzzles import models as _pz  # noqa: F401
    from app.modules.relationships import models as _rel  # noqa: F401
    from app.modules.support import models as _sup  # noqa: F401
    from app.modules.trapped_pieces import models as _tp  # noqa: F401
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


@pytest.fixture(autouse=True)
def _reset_auth_limiter():
    """Isolate the in-memory auth/support rate limiters between tests."""
    from app.core.rate_limit import auth_limiter, support_limiter

    auth_limiter.reset()
    support_limiter.reset()
    yield
    auth_limiter.reset()
    support_limiter.reset()


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


_auth_user_counter = 0


def make_auth_headers(db_session, username=None):
    """Bearer headers for an authenticated PLAYER session (test-only).

    Guest/anonymous practice is disabled product-wide: attempt-creating
    endpoints require authentication, so API tests submit with these
    headers. Direct row inserts avoid the password-hashing env issue;
    the token stays bound to a real server-side session. Usernames
    auto-increment so several calls fit in one test DB.
    """
    global _auth_user_counter
    _auth_user_counter += 1
    username = username or f"player_{_auth_user_counter}"
    from app.modules.auth import service as auth_service
    from app.modules.users.models import User

    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="not-verified",
        display_name=username,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _, token = auth_service.create_user_session(db_session, user, "PLAYER")
    db_session.commit()
    return {"Authorization": f"Bearer {token}"}
