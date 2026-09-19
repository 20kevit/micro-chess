"""Exercise 1 API: practice next-puzzle, speed sessions, report, security.

Lifecycle: open (preparing, no clock) -> prepare >= 20 -> start (60s clock)
-> submit loop -> finish/report. Backend stays authoritative for scoring,
correctness, expiration, and the final report.
"""

from datetime import timedelta

import pytest

from app.modules.piece_recognition import sessions as session_service
from app.modules.piece_recognition.models import PieceSpeedSession
from app.modules.positions import repository as positions_repo
from app.modules.progress.models import Attempt
from tests.conftest import make_auth_headers


@pytest.fixture(autouse=True)
def small_source_db(tmp_path, monkeypatch):
    """Pin a tiny puzzles.db so API tests exercise the real read path fast
    instead of scanning a multi-GB Lichess dump if one is present."""
    import sqlite3

    path = tmp_path / "puzzles.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        'CREATE TABLE "puzzles" ("PuzzleId" TEXT, "FEN" TEXT, "Rating" INTEGER, "Themes" TEXT, "Moves" TEXT)'
    )
    for i, fen in enumerate(positions_repo.FALLBACK_FENS):
        conn.execute(
            "INSERT INTO puzzles (PuzzleId, FEN, Rating, Themes, Moves) VALUES (?, ?, ?, ?, ?)",
            (f"p{i}", fen, 1500, "t", "e2e4"),
        )
    conn.commit()
    conn.close()
    monkeypatch.setenv(positions_repo.SOURCE_ENV_VAR, str(path))
    return path


def _open(client):
    body = client.post("/api/v1/piece-recognition/sessions", json={}).json()
    assert body["status"] == "preparing"
    return body["session_id"]


def _prepare(client, session_id, count=20):
    res = client.post(
        f"/api/v1/piece-recognition/sessions/{session_id}/puzzles", json={"count": count}
    )
    assert res.status_code == 200, res.text
    return res.json()


def _start(client, session_id):
    res = client.post(f"/api/v1/piece-recognition/sessions/{session_id}/start")
    assert res.status_code == 200, res.text
    return res.json()


def _ready_session(client, count=20):
    sid = _open(client)
    puzzles = _prepare(client, sid, count)
    started = _start(client, sid)
    return sid, puzzles, started


def test_next_practice_puzzle_hides_answer(client, db_session):
    res = client.post("/api/v1/piece-recognition/next", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["fen"] and body["prompt_fa"] and body["explanation"]
    assert "answer_json" not in body
    assert body["exercise_slug"] == "piece-recognition"


def test_next_practice_exclude_ids_avoids_repeat(client, db_session):
    first = client.post("/api/v1/piece-recognition/next", json={}).json()
    seen = {first["id"]}
    for _ in range(10):
        body = client.post(
            "/api/v1/piece-recognition/next", json={"exclude_ids": sorted(seen)}
        ).json()
        if body["id"] not in seen:
            seen.add(body["id"])
            break
    assert len(seen) >= 2


def test_next_puzzles_vary_and_submit_end_to_end(client, db_session):
    headers = make_auth_headers(db_session)
    fens = set()
    for _ in range(5):
        body = client.post("/api/v1/piece-recognition/next", json={}).json()
        fens.add((body["fen"], body["prompt_fa"]))
        res = client.post(
            "/api/v1/attempts",
            json={"puzzle_id": body["id"], "answer": {"selected_squares": []}, "mode": "practice"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["rating_delta"] is None
    assert len(fens) >= 2  # random source, not a fixed demo loop
    assert db_session.query(Attempt).count() >= 5


def test_client_cannot_override_fen_or_target(client, db_session):
    body = client.post("/api/v1/piece-recognition/next", json={}).json()
    res = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": body["id"],
            "answer": {
                "selected_squares": ["a1", "b2", "c3"],
                "fen": "8/8/8/8/8/8/8/8 w - - 0 1",
                "squares": ["a1", "b2", "c3"],
                "target": "white-queen",
            },
            "mode": "practice",
        },
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 200
    detail = res.json()["detail"]
    assert set(detail["correct"]).issubset({"a1", "b2", "c3"})
    assert res.json()["result"] in ("correct", "partial", "wrong")


def test_speed_session_opens_without_running_clock(client, db_session):
    body = client.post("/api/v1/piece-recognition/sessions", json={}).json()
    assert body["duration_s"] == 60
    assert body["status"] == "preparing"
    assert body["expires_at"] is None
    assert body["remaining_ms"] == 60000
    assert body["buffered"] == 0


def test_speed_start_requires_minimum_buffer(client, db_session):
    sid = _open(client)
    res = client.post(f"/api/v1/piece-recognition/sessions/{sid}/start")
    assert res.status_code == 409
    assert res.json()["detail"] == "buffer_not_ready"
    _prepare(client, sid, 19)
    res = client.post(f"/api/v1/piece-recognition/sessions/{sid}/start")
    assert res.status_code == 409
    _prepare(client, sid, 1)
    started = _start(client, sid)
    assert started["status"] == "active"
    assert started["expires_at"] is not None
    assert started["buffered"] == 20


def test_speed_submit_before_start_refused(client, db_session):
    sid = _open(client)
    puzzles = _prepare(client, sid, 20)
    res = client.post(
        f"/api/v1/piece-recognition/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 409


def test_speed_prepare_hides_answers_and_refills(client, db_session):
    sid = _open(client)
    first = _prepare(client, sid, 20)
    assert len(first) == 20
    assert all("answer_json" not in p for p in first)
    assert len({p["id"] for p in first}) == 20  # buffer stays duplicate-free
    _start(client, sid)
    more = _prepare(client, sid, 5)
    assert len(more) == 5
    summary = client.get(f"/api/v1/piece-recognition/sessions/{sid}").json()
    assert summary["buffered"] == 25


def test_speed_submit_scores_per_square_and_accumulates(client, db_session):
    headers = make_auth_headers(db_session)
    sid, puzzles, _ = _ready_session(client)
    res = client.post(
        f"/api/v1/piece-recognition/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}},
        headers=headers,
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["attempt"]["mode"] == "practice"
    assert payload["attempt"]["rating_delta"] is None
    assert payload["session"]["attempted"] == 1
    total = (
        payload["session"]["correct"] + payload["session"]["partial"] + payload["session"]["wrong"]
    )
    assert total == 1
    assert db_session.query(Attempt).count() == 1

    second = client.post(
        f"/api/v1/piece-recognition/sessions/{sid}/next",
        json={},
    )
    assert second.status_code == 200
    res2 = client.post(
        f"/api/v1/piece-recognition/sessions/{sid}/submit",
        json={"puzzle_id": second.json()["id"], "answer": {"selected_squares": ["e4", "d5"]}},
        headers=headers,
    )
    assert res2.json()["session"]["attempted"] == 2


def test_speed_report_rebuilt_from_stored_attempts(client, db_session):
    headers = make_auth_headers(db_session)
    sid, puzzles, _ = _ready_session(client)
    for p in puzzles[:3]:
        res = client.post(
            f"/api/v1/piece-recognition/sessions/{sid}/submit",
            json={"puzzle_id": p["id"], "answer": {"selected_squares": ["e4"]}},
            headers=headers,
        )
        assert res.status_code == 200
    report = client.get(f"/api/v1/piece-recognition/sessions/{sid}/report").json()
    assert report["session"]["attempted"] == 3
    assert len(report["entries"]) == 3
    for entry, puzzle in zip(report["entries"], puzzles[:3]):
        assert entry["puzzle_id"] == puzzle["id"]
        assert entry["prompt_fa"] == puzzle["prompt_fa"]
        assert entry["result"] in ("correct", "partial", "wrong")
        assert set(entry) >= {"correct", "missed", "wrong", "score", "fen"}
    # Report matches the persisted attempts exactly.
    attempts = db_session.query(Attempt).order_by(Attempt.id).all()
    assert [a.id for a in attempts] == [e["attempt_id"] for e in report["entries"]]
    assert sum(a.score for a in attempts) == report["session"]["score"]


def test_speed_report_empty_session(client, db_session):
    sid, _, _ = _ready_session(client)
    report = client.get(f"/api/v1/piece-recognition/sessions/{sid}/report").json()
    assert report["entries"] == []
    assert report["session"]["attempted"] == 0


def test_speed_session_submit_ignores_client_solution(client, db_session):
    sid, puzzles, _ = _ready_session(client)
    res = client.post(
        f"/api/v1/piece-recognition/sessions/{sid}/submit",
        json={
            "puzzle_id": puzzles[0]["id"],
            "answer": {"selected_squares": [], "squares": [], "target": "x", "fen": "8/8/8/8/8/8/8/8 w - - 0 1"},
        },
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 200  # graded against stored answer, no crash


def test_speed_session_rejects_foreign_puzzle(client, db_session):
    from app.modules.puzzles.models import Puzzle

    sid, _, _ = _ready_session(client)
    # A genuinely foreign row: unique FEN/target, never issued to the session.
    foreign = Puzzle(
        exercise_slug="piece-recognition",
        fen="k7/8/8/8/8/8/8/7K w - - 0 1",
        position_json={"target": "white-king"},
        answer_json={"squares": ["h1"], "target": "white-king"},
        hint_json={},
        prompt_fa="x",
        explanation="",
        is_published=True,
        is_archived=False,
    )
    db_session.add(foreign)
    db_session.commit()
    db_session.refresh(foreign)
    res = client.post(
        f"/api/v1/piece-recognition/sessions/{sid}/submit",
        json={"puzzle_id": foreign.id, "answer": {"selected_squares": []}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 404


def test_speed_session_expiry_is_authoritative(client, db_session):
    sid, puzzles, _ = _ready_session(client)
    # Age the session server-side past its deadline.
    session = db_session.get(PieceSpeedSession, sid)
    session.ends_at = session.started_at - timedelta(seconds=1)
    db_session.commit()

    res = client.post(
        f"/api/v1/piece-recognition/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 410
    assert res.json()["detail"] == "session_expired"
    assert client.post(f"/api/v1/piece-recognition/sessions/{sid}/next", json={}).status_code == 410
    summary = client.get(f"/api/v1/piece-recognition/sessions/{sid}").json()
    assert summary["status"] == "expired"
    assert summary["remaining_ms"] == 0


def test_speed_session_finish_summary_accumulates(client, db_session):
    headers = make_auth_headers(db_session)
    sid, puzzles, _ = _ready_session(client)
    for p in puzzles[:3]:
        res = client.post(
            f"/api/v1/piece-recognition/sessions/{sid}/submit",
            json={"puzzle_id": p["id"], "answer": {"selected_squares": ["e4"]}},
            headers=headers,
        )
        assert res.status_code == 200
    summary = client.post(f"/api/v1/piece-recognition/sessions/{sid}/finish").json()
    assert summary["status"] == "finished"
    assert summary["attempted"] == 3
    assert summary["correct"] + summary["partial"] + summary["wrong"] == 3
    again = client.get(f"/api/v1/piece-recognition/sessions/{sid}").json()
    assert again["attempted"] == 3 and again["status"] == "finished"


def test_speed_session_hints_recorded(client, db_session):
    sid, puzzles, _ = _ready_session(client)
    res = client.post(
        f"/api/v1/piece-recognition/sessions/{sid}/submit",
        json={"puzzle_id": puzzles[0]["id"], "answer": {"selected_squares": []}, "hints_used": ["h1"]},
        headers=make_auth_headers(db_session),
    )
    assert res.json()["attempt"]["hints_used"] == ["h1"]


def test_unknown_session_404(client, db_session):
    assert client.get("/api/v1/piece-recognition/sessions/nope").status_code == 404
    assert client.post("/api/v1/piece-recognition/sessions/nope/next", json={}).status_code == 404
    assert client.get("/api/v1/piece-recognition/sessions/nope/report").status_code == 404


def test_service_lifecycle_preparing_then_active(db_session):
    session = session_service.start_session(db_session)
    assert session.duration_s == 60
    assert session.status == "preparing"
    assert session.ends_at is None
    with pytest.raises(session_service.BufferNotReadyError):
        session_service.begin_session(db_session, session.id)
    made = session_service.prepare_puzzles(db_session, session.id, 20)
    assert len(made) == 20
    live = session_service.begin_session(db_session, session.id)
    assert live.status == "active" and live.ends_at is not None
    assert session_service.summary(live)["remaining_ms"] > 0
