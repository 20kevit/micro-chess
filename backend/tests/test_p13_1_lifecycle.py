import random

import pytest

from app.modules.piece_recognition import generator, seed
from app.modules.puzzles import service
from app.modules.puzzles.models import Puzzle, PuzzleStatusHistory, PuzzleValidation
from tests.conftest import publish_staged_puzzles


def _assert_staged(db_session, row: Puzzle, *, source: str, reference: str) -> None:
    assert row.is_published is False
    assert row.is_archived is False
    assert row.status == "validated"
    assert row.source == source
    assert row.source_reference == reference
    assert row.content_hash

    validation = db_session.query(PuzzleValidation).filter_by(puzzle_id=row.id).one()
    assert validation.status == "pass"
    history = db_session.query(PuzzleStatusHistory).filter_by(puzzle_id=row.id).one()
    assert (history.from_status, history.to_status) == ("draft", "validated")


def test_local_generator_stages_validated_candidate_and_player_cannot_see_it(db_session):
    puzzle = generator.create_puzzle(db_session, random.Random(13))
    _assert_staged(
        db_session,
        puzzle,
        source="generated",
        reference="generator:piece-recognition",
    )
    with pytest.raises(service.PlayerPuzzleUnavailableError):
        service.player_puzzle(db_session, puzzle.exercise_slug)


def test_seed_stages_imported_candidates_with_history_and_is_idempotent(db_session):
    assert seed.seed_db(db_session) == 15
    assert seed.seed_db(db_session) == 0
    rows = db_session.query(Puzzle).filter(Puzzle.exercise_slug == "piece-recognition").all()
    assert len(rows) == 15
    for row in rows:
        _assert_staged(db_session, row, source="imported", reference="seed:piece-recognition")
    with pytest.raises(service.PlayerPuzzleUnavailableError):
        service.player_puzzle(db_session, "piece-recognition")


def test_player_route_fails_closed_until_candidate_is_explicitly_published(client, db_session):
    puzzle = generator.create_puzzle(db_session, random.Random(17))
    response = client.post("/api/v1/piece-recognition/next", json={})
    assert response.status_code == 503
    assert response.json()["detail"] == "puzzle_not_available"
    assert client.get(f"/api/v1/puzzles/{puzzle.id}").status_code == 404

    publish_staged_puzzles(db_session, puzzle.exercise_slug)
    published = client.post("/api/v1/piece-recognition/next", json={})
    assert published.status_code == 200
    assert published.json()["id"] == puzzle.id


def test_direct_published_flag_does_not_bypass_lifecycle(db_session):
    from app.modules.exercises.models import Exercise

    db_session.add(
        Exercise(
            slug="lifecycle-flag-test",
            title_fa="تست",
            title_en="Test",
            is_active=True,
            sort_order=99,
        )
    )
    db_session.commit()
    puzzle = Puzzle(
        exercise_slug="lifecycle-flag-test",
        answer_json={"value": "ok"},
        is_published=True,
    )
    db_session.add(puzzle)
    db_session.commit()
    db_session.refresh(puzzle)

    assert puzzle.status == "draft"
    with pytest.raises(service.PlayerPuzzleUnavailableError):
        service.player_puzzle(db_session, "lifecycle-flag-test")
