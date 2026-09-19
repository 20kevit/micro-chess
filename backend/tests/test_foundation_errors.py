"""Foundation: API error contract and versioning.

Every error response carries a machine-readable ``error.code`` envelope
while preserving the legacy ``detail`` field existing clients rely on.
"""

from app.core.api import API_V1_PREFIX


def test_api_prefix_is_versioned():
    assert API_V1_PREFIX == "/api/v1"


def test_unknown_route_has_error_envelope(client):
    res = client.get("/api/v1/does-not-exist")
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "HTTP_404"
    assert "detail" in body


def test_puzzle_404_maps_detail_to_code(client):
    res = client.get("/api/v1/puzzles/999999")
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "PUZZLE_NOT_AVAILABLE"
    assert body["detail"] == "puzzle_not_available"


def test_rated_without_auth_maps_detail_to_code(client, db_session):
    from app.modules.piece_recognition import seed as seed_mod
    from app.modules.piece_recognition.validator import SLUG
    from app.modules.puzzles.models import Puzzle

    seed_mod.seed_db(db_session)
    puzzle = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).order_by(Puzzle.id).first()
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {}, "mode": "rated"},
    )
    # Guest/anonymous practice is disabled: unauthenticated submits of any
    # mode are rejected before reaching validation.
    assert res.status_code == 401
    body = res.json()
    assert body["error"]["code"] == "AUTH_REQUIRED"
    assert body["detail"] == "auth_required"


def test_validation_error_has_envelope_without_internals(client, db_session):
    from tests.conftest import make_auth_headers

    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": "not-an-int", "answer": {}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 422
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(body["error"]["details"]["errors"], list)
    assert "traceback" not in res.text.lower()
