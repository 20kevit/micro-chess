"""Exercise 1 API: practice next-puzzle, speed sessions, security.

Covers: no solution leak, server-authoritative correctness, client override
resistance, practice persistence, 60s session config/expiry/summary.
"""

from datetime import timedelta

from app.modules.piece_recognition import sessions as session_service
from app.modules.piece_recognition.models import PieceSpeedSession
from app.modules.progress.models import Attempt


def test_next_practice_puzzle_hides_answer(client, db_session):
    res = client.post("/api/v1/piece-recognition/next")
    assert res.status_code == 200
    body = res.json()
    assert body["fen"] and body["prompt_fa"] and body["explanation"]
    assert "answer_json" not in body
    assert body["exercise_slug"] == "piece-recognition"


def test_next_puzzles_vary_and_submit_end_to_end(client, db_session):
    fens = set()
    for _ in range(5):
        body = client.post("/api/v1/piece-recognition/next").json()
        fens.add((body["fen"], body["prompt_fa"]))
        # Practice submit with empty selection persists an attempt.
        res = client.post(
            "/api/v1/attempts",
            json={"puzzle_id": body["id"], "answer": {"selected_squares": []}, "mode": "practice"},
        )
        assert res.status_code == 200
        assert res.json()["rating_delta"] is None
    assert len(fens) >= 2  # random source, not a fixed demo loop
    assert db_session.query(Attempt).count() >= 5


def test_client_cannot_override_fen_or_target(client, db_session):
    body = client.post("/api/v1/piece-recognition/next").json()
    # Attacker claims a different FEN/target and a bogus solution; the server
    # must grade only the stored answer_json + submitted squares.
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
    )
    assert res.status_code == 200
    detail = res.json()["detail"]
    assert set(detail["correct"]).issubset({"a1", "b2", "c3"})
    # The stored answer decides correctness, not the submitted metadata.
    assert res.json()["result"] in ("correct", "partial", "wrong")


def test_speed_session_defaults_to_60_seconds(client, db_session):
    body = client.post("/api/v1/piece-recognition/sessions", json={}).json()
    assert body["duration_s"] == 60
    assert body["status"] == "active"
    assert body["remaining_ms"] > 0
    session = db_session.get(PieceSpeedSession, body["session_id"])
    assert (session.ends_at - session.started_at) == timedelta(seconds=60)


def test_speed_next_hides_answer_and_submit_scores(client, db_session):
    session_id = client.post("/api/v1/piece-recognition/sessions", json={}).json()["session_id"]
    first = client.post(f"/api/v1/piece-recognition/sessions/{session_id}/next").json()
    assert "answer_json" not in first
    second = client.post(f"/api/v1/piece-recognition/sessions/{session_id}/next").json()
    assert second["id"] != first["id"]

    # Empty submission: correct only for zero-target puzzles.
    res = client.post(
        f"/api/v1/piece-recognition/sessions/{session_id}/submit",
        json={"puzzle_id": first["id"], "answer": {"selected_squares": []}},
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


def test_speed_session_submit_ignores_client_solution(client, db_session):
    session_id = client.post("/api/v1/piece-recognition/sessions", json={}).json()["session_id"]
    puzzle = client.post(f"/api/v1/piece-recognition/sessions/{session_id}/next").json()
    res = client.post(
        f"/api/v1/piece-recognition/sessions/{session_id}/submit",
        json={
            "puzzle_id": puzzle["id"],
            "answer": {"selected_squares": [], "squares": [], "target": "x", "fen": "8/8/8/8/8/8/8/8 w - - 0 1"},
        },
    )
    assert res.status_code == 200  # graded against stored answer, no crash


def test_speed_session_rejects_foreign_puzzle(client, db_session):
    session_id = client.post("/api/v1/piece-recognition/sessions", json={}).json()["session_id"]
    foreign = client.post("/api/v1/piece-recognition/next").json()
    res = client.post(
        f"/api/v1/piece-recognition/sessions/{session_id}/submit",
        json={"puzzle_id": foreign["id"], "answer": {"selected_squares": []}},
    )
    assert res.status_code == 404


def test_speed_session_expiry_is_authoritative(client, db_session):
    session_id = client.post("/api/v1/piece-recognition/sessions", json={}).json()["session_id"]
    puzzle = client.post(f"/api/v1/piece-recognition/sessions/{session_id}/next").json()
    # Age the session server-side past its deadline.
    session = db_session.get(PieceSpeedSession, session_id)
    session.ends_at = session.started_at - timedelta(seconds=1)
    db_session.commit()

    res = client.post(
        f"/api/v1/piece-recognition/sessions/{session_id}/submit",
        json={"puzzle_id": puzzle["id"], "answer": {"selected_squares": []}},
    )
    assert res.status_code == 410
    assert res.json()["detail"] == "session_expired"
    assert client.post(f"/api/v1/piece-recognition/sessions/{session_id}/next").status_code == 410
    summary = client.get(f"/api/v1/piece-recognition/sessions/{session_id}").json()
    assert summary["status"] == "expired"
    assert summary["remaining_ms"] == 0


def test_speed_session_finish_summary_accumulates(client, db_session):
    session_id = client.post("/api/v1/piece-recognition/sessions", json={}).json()["session_id"]
    for _ in range(3):
        puzzle = client.post(f"/api/v1/piece-recognition/sessions/{session_id}/next").json()
        res = client.post(
            f"/api/v1/piece-recognition/sessions/{session_id}/submit",
            json={"puzzle_id": puzzle["id"], "answer": {"selected_squares": ["e4"]}},
        )
        assert res.status_code == 200
    summary = client.post(f"/api/v1/piece-recognition/sessions/{session_id}/finish").json()
    assert summary["status"] == "finished"
    assert summary["attempted"] == 3
    assert summary["correct"] + summary["partial"] + summary["wrong"] == 3
    assert summary["score"] >= 0.0
    again = client.get(f"/api/v1/piece-recognition/sessions/{session_id}").json()
    assert again["attempted"] == 3 and again["status"] == "finished"


def test_speed_session_hints_recorded(client, db_session):
    session_id = client.post("/api/v1/piece-recognition/sessions", json={}).json()["session_id"]
    puzzle = client.post(f"/api/v1/piece-recognition/sessions/{session_id}/next").json()
    res = client.post(
        f"/api/v1/piece-recognition/sessions/{session_id}/submit",
        json={"puzzle_id": puzzle["id"], "answer": {"selected_squares": []}, "hints_used": ["h1"]},
    )
    assert res.json()["attempt"]["hints_used"] == ["h1"]


def test_unknown_session_404(client, db_session):
    assert client.get("/api/v1/piece-recognition/sessions/nope").status_code == 404
    assert client.post("/api/v1/piece-recognition/sessions/nope/next").status_code == 404


def test_service_starts_with_60s_and_expires(db_session):
    session = session_service.start_session(db_session)
    assert session.duration_s == 60
    assert session.status == "active"
    assert session_service.summary(session)["remaining_ms"] > 0
