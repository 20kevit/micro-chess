"""Exercise 6 (Pathfinding, simple version): geometry, BFS, scoring, API.

Covers the exercise spec:
- movement per piece (knight/bishop/rook/queen) + illegal steps
- hand-derived shortest distances (incl. multi-move knight tours)
- independent python-chess cross-check of the movement graph
- scoring formula (optimal*5, extra*-2, illegal*-3, negatives)
- completion semantics (star reached vs elsewhere, post-completion guard)
- generator guarantees (one white piece, allowed kinds, no kings/pawns/
  black pieces, source != target, reachable, optimal stored server-side)
- security (no client score/optimal override, no completion without star,
  no skipped illegal steps, no answer leak)
- practice next + step endpoint + full speed lifecycle (20-buffer, 60s)
"""

import random

import chess
import pytest

from app.modules.exercises import registry
from app.modules.pathfinding import generator as gen
from app.modules.pathfinding import moves
from app.modules.pathfinding import seed as seed_mod
from app.modules.pathfinding import sessions as session_service
from app.modules.pathfinding.models import PathfindingSpeedSession
from app.modules.pathfinding.scoring import score_path
from app.modules.pathfinding.validator import SLUG, apply_step, replay_path, validate
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult
from tests.conftest import make_auth_headers, publish_generated_pool

KIND_LETTER = {"knight": "N", "bishop": "B", "rook": "R", "queen": "Q"}


def answer_for(kind: str, start: str, target: str, optimal: int) -> dict:
    return {
        "fen": gen._fen_for(kind, start),
        "from": start,
        "target": target,
        "piece": kind,
        "optimal_moves": optimal,
    }


# --- Movement per piece ---


def test_knight_jumps():
    assert moves.is_legal_step("knight", "a1", "b3") is True
    assert moves.is_legal_step("knight", "a1", "c2") is True
    assert moves.is_legal_step("knight", "b1", "d2") is True
    assert moves.is_legal_step("knight", "b1", "b2") is False  # straight: illegal
    assert moves.is_legal_step("knight", "a1", "a1") is False  # null move


def test_bishop_diagonals():
    assert moves.is_legal_step("bishop", "c1", "h6") is True
    assert moves.is_legal_step("bishop", "c1", "a3") is True
    assert moves.is_legal_step("bishop", "c1", "c2") is False  # straight: illegal
    assert moves.is_legal_step("bishop", "c1", "h7") is False  # opposite color


def test_rook_lines():
    assert moves.is_legal_step("rook", "a1", "a8") is True
    assert moves.is_legal_step("rook", "a1", "h1") is True
    assert moves.is_legal_step("rook", "a1", "b2") is False  # diagonal: illegal


def test_queen_union():
    assert moves.is_legal_step("queen", "a1", "h8") is True
    assert moves.is_legal_step("queen", "a1", "a8") is True
    assert moves.is_legal_step("queen", "a1", "h1") is True
    assert moves.is_legal_step("queen", "d4", "f6") is True
    assert moves.is_legal_step("queen", "d4", "e6") is False  # knight jump: illegal


def test_unknown_kind_and_bad_squares():
    assert moves.is_legal_step("king", "e1", "e2") is False
    assert moves.is_legal_step("pawn", "e2", "e4") is False
    assert moves.is_legal_step("rook", "a1", "a9") is False
    assert moves.is_legal_step("rook", "zz", "a8") is False
    with pytest.raises(ValueError):
        moves.legal_dests("king", "e1")
    assert apply_step("rook", "a1", "a1") is None
    assert apply_step("rook", "a1", "b2") is None
    assert apply_step("rook", "a1", "a8") == "a8"
    with pytest.raises(ValueError):
        apply_step("king", "e1", "e2")


def test_source_target_correctness():
    # Steps only ever move the selected piece: origin mismatch is rejected
    # at the API layer; geometry itself is origin-agnostic and empty-board.
    assert moves.is_legal_step("knight", "g1", "f3") is True
    assert moves.is_legal_step("knight", "g1", "g2") is False


# --- Shortest path: hand-derived distances ---


def test_hand_derived_distances():
    assert moves.shortest_path_length("rook", "a1", "a8") == 1
    assert moves.shortest_path_length("bishop", "c1", "h6") == 1
    assert moves.shortest_path_length("queen", "a1", "h8") == 1
    assert moves.shortest_path_length("knight", "a1", "b3") == 1
    assert moves.shortest_path_length("knight", "a1", "c5") == 2  # a1->b3->c5
    assert moves.shortest_path_length("rook", "a1", "h8") == 2
    assert moves.shortest_path_length("bishop", "c1", "a3") == 1
    assert moves.shortest_path_length("bishop", "c1", "d4") == 2  # c1->e3->d4
    assert moves.shortest_path_length("queen", "a1", "h7") == 2
    assert moves.shortest_path_length("knight", "b1", "c3") == 1
    assert moves.shortest_path_length("knight", "a1", "a1") == 0
    assert moves.shortest_path_length("knight", "a1", "c4") == 3  # needs a detour
    assert moves.shortest_path_length("bishop", "d4", "d5") is None  # opposite color


def test_knight_long_tour():
    # Opposite corners: the classic 6-move knight tour.
    assert moves.shortest_path_length("knight", "a1", "h8") == 6
    assert moves.shortest_path_length("knight", "a1", "h7") == 5


def test_bishop_unreachable_opposite_color():
    assert moves.shortest_path_length("bishop", "a1", "h7") is None
    assert moves.shortest_path_length("bishop", "c1", "c2") is None


def test_rook_queen_bishop_always_reachable_same_color():
    assert moves.shortest_path_length("rook", "e4", "e4") == 0
    assert moves.shortest_path_length("queen", "d4", "e6") == 2
    assert moves.shortest_path_length("knight", "a1", "h8") == 6


def test_bad_bfs_input():
    with pytest.raises(ValueError):
        moves.shortest_path_length("king", "e1", "e2")
    with pytest.raises(ValueError):
        moves.shortest_path_length("rook", "a9", "a8")


# --- Independent python-chess cross-check (not the same algorithm) ---

_KIND_TYPE = {"knight": chess.KNIGHT, "bishop": chess.BISHOP, "rook": chess.ROOK, "queen": chess.QUEEN}


def _python_chess_dests(kind: str, square: str) -> set[str]:
    """Independent movement graph via raw python-chess only.

    Kingless board with just the piece: python-chess still generates
    moves normally (no king safety to enforce), so the origin's legal
    moves are exactly the piece geometry. Never calls moves.py.
    """
    board = chess.Board("8/8/8/8/8/8/8/8 w - - 0 1")
    board.set_piece_at(chess.parse_square(square), chess.Piece(_KIND_TYPE[kind], chess.WHITE))
    board.turn = chess.WHITE
    origin = chess.parse_square(square)
    return {
        chess.square_name(m.to_square) for m in board.legal_moves if m.from_square == origin
    }


@pytest.mark.parametrize("kind", ["knight", "bishop", "rook", "queen"])
@pytest.mark.parametrize("square", ["d4", "e4", "c3", "f6", "b2", "g5"])
def test_graph_matches_python_chess(kind: str, square: str):
    assert moves.legal_dests(kind, square) == _python_chess_dests(kind, square)


def test_independent_bfs_agrees_on_samples():
    import random as _random

    rng = _random.Random(42)

    def py_bfs(kind: str, start: str, target: str) -> int | None:
        from collections import deque as _dq

        if start == target:
            return 0
        seen = {start}
        queue = _dq([(start, 0)])
        while queue:
            pos, dist = queue.popleft()
            for nxt in _python_chess_dests(kind, pos):
                if nxt == target:
                    return dist + 1
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, dist + 1))
        return None

    for _ in range(60):
        kind = rng.choice(["knight", "bishop", "rook", "queen"])
        start = f"{'abcdefgh'[rng.randrange(8)]}{rng.randrange(1, 9)}"
        target = f"{'abcdefgh'[rng.randrange(8)]}{rng.randrange(1, 9)}"
        if start in ("h1", "a8") or target in ("h1", "a8"):
            continue
        assert moves.shortest_path_length(kind, start, target) == py_bfs(kind, start, target)


# --- Path replay / validation ---


def test_direct_valid_path():
    run = replay_path("rook", "a1", "a8", ["a1", "a8"])
    assert run == {"ok": True, "prefix": ["a1", "a8"], "fail_at": None, "reached": True, "moves": 1}


def test_multi_step_path():
    run = replay_path("knight", "a1", "c4", ["a1", "b3", "c5", "e6", "d4", "c2", "e3", "c4"])
    assert run["ok"] is True and run["reached"] is True
    assert run["moves"] == len(run["prefix"]) - 1


def test_multiple_optimal_paths_accepted():
    assert replay_path("rook", "a1", "h8", ["a1", "a8", "h8"])["ok"] is True
    assert replay_path("rook", "a1", "h8", ["a1", "h1", "h8"])["ok"] is True


def test_non_optimal_but_valid_path_accepted():
    run = replay_path("rook", "a1", "a8", ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8"])
    assert run["ok"] is True and run["moves"] == 7


def test_incomplete_and_diverted_paths_rejected():
    assert replay_path("rook", "a1", "a8", ["a1", "a4"])["ok"] is False
    assert replay_path("rook", "a1", "a8", ["a1", "h1"])["ok"] is False
    bad = replay_path("rook", "a1", "a8", ["a1", "b2"])
    assert bad["ok"] is False and bad["fail_at"] == "b2"


def test_validate_correct_and_detail():
    out = validate(answer_for("rook", "a1", "a8", 1), {"path": ["a1", "a8"], "illegal_attempts": 0})
    assert out.result == AttemptResult.CORRECT
    assert out.detail["reached"] is True
    assert out.detail["moves"] == 1
    assert out.detail["optimal_moves"] == 1
    assert out.detail["missed"] == []


def test_validate_reaching_target_only_completes():
    assert (
        validate(answer_for("rook", "a1", "a8", 1), {"path": ["a1", "a4"]}).result
        == AttemptResult.WRONG
    )
    assert (
        validate(answer_for("rook", "a1", "a8", 1), {"path": ["a1", "h1"]}).result
        == AttemptResult.WRONG
    )


def test_validate_wrong_start_empty_malformed():
    base = answer_for("rook", "a1", "a8", 1)
    assert validate(base, {"path": ["a2", "a8"]}).result == AttemptResult.WRONG
    assert validate(base, {"path": []}).result == AttemptResult.WRONG
    assert validate(base, {}).result == AttemptResult.WRONG
    assert validate(base, {"path": "a1a8"}).result == AttemptResult.WRONG
    assert validate(base, {"path": ["a1", "zz"]}).result == AttemptResult.WRONG
    assert validate(base, {"path": ["a1", 42]}).result == AttemptResult.WRONG
    assert validate({}, {"path": ["a1", "a8"]}).result == AttemptResult.WRONG
    assert validate(base, None).result == AttemptResult.WRONG  # type: ignore[arg-type]


def test_validate_cannot_force_completion():
    base = answer_for("rook", "a1", "a8", 1)
    # Skipping straight to the target square is not a path.
    assert validate(base, {"path": ["a8"], "reached": True}).result == AttemptResult.WRONG
    # Claiming completion from a different square fails.
    assert validate(base, {"path": ["a1", "h1"]}).result == AttemptResult.WRONG
    # Jumping over geometry (not a legal step) fails even at the target.
    assert validate(base, {"path": ["a1", "a8"], "optimal_moves": 99}).result == AttemptResult.CORRECT
    # ... but illegal jumps never validate:
    assert validate(base, {"path": ["a1", "b2", "a8"]}).result == AttemptResult.WRONG


def test_registered_in_registry():
    assert registry.get_validator(SLUG) is not None
    assert registry.get_scorer(SLUG) is not None


# --- Scoring ---


def _validation_for(optimal: int, path: list[str], illegal: int = 0):
    kind = "rook"
    return validate(answer_for(kind, path[0], path[-1], optimal), {"path": path, "illegal_attempts": illegal})


def test_score_optimal_only():
    assert score_path(_validation_for(3, ["a1", "a8", "h8", "h1"])) == 15.0


def test_score_extra_moves():
    # optimal 3, actual 5 -> 15 - 2*2 = 11.
    assert score_path(_validation_for(3, ["a1", "a2", "a3", "a8", "h8", "h1"])) == 11.0


def test_score_illegal_attempts():
    # optimal 3, actual 3, 2 illegal -> 15 - 6 = 9.
    assert score_path(_validation_for(3, ["a1", "a8", "h8", "h1"], illegal=2)) == 9.0


def test_score_mixed_spec_example():
    # Spec example: optimal 3, 5 legal moves, 2 illegal -> 15 - 4 - 6 = 5.
    v = _validation_for(3, ["a1", "a2", "a3", "a8", "h8", "h1"], illegal=2)
    assert score_path(v) == 5.0


def test_score_negative_allowed():
    v = _validation_for(1, ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8"], illegal=5)
    # 5 - 6*2 - 5*3 = -22.
    assert score_path(v) == -22.0


def test_score_exact_boundary():
    assert score_path(_validation_for(1, ["a1", "a8"])) == 5.0
    assert score_path(_validation_for(1, ["a1", "a2", "a8"])) == 3.0
    assert score_path(_validation_for(1, ["a1", "a8"], illegal=1)) == 2.0


def test_score_wrong_validation_still_scores_from_detail():
    out = validate(answer_for("rook", "a1", "a8", 1), {"path": ["a1", "a4"]})
    assert out.result == AttemptResult.WRONG
    assert score_path(out) == 5.0  # 1*5 - 0 extra - 0 illegal


# --- Generator ---


def test_weighted_distribution_targets_spec():
    rng = random.Random(1234)
    counts = {"knight": 0, "bishop": 0, "rook": 0, "queen": 0}
    for _ in range(4000):
        counts[gen.pick_kind(rng)] += 1
    total = sum(counts.values())
    assert abs(counts["knight"] / total - 0.50) < 0.05
    assert abs(counts["bishop"] / total - 0.20) < 0.05
    assert abs(counts["rook"] / total - 0.20) < 0.05
    assert abs(counts["queen"] / total - 0.10) < 0.05


def _assert_single_clean_piece(data: dict) -> None:
    board = chess.Board(data["fen"])
    pieces = [(sq, p) for sq, p in board.piece_map().items()]
    assert len(pieces) == 1
    (sq, piece) = pieces[0]
    assert piece.color == chess.WHITE
    assert chess.square_name(sq) == data["from"]
    assert piece.symbol() == KIND_LETTER[data["piece"]]
    assert piece.piece_type not in (chess.KING, chess.PAWN)
    assert all(p.color == chess.WHITE for _, p in pieces)


def test_generator_guarantees():
    rng = random.Random(99)
    for _ in range(60):
        data = gen.generate_question_data(rng)
        assert data["piece"] in ("knight", "bishop", "rook", "queen")
        assert data["from"] != data["target"]
        _assert_single_clean_piece(data)
        optimal = moves.shortest_path_length(data["piece"], data["from"], data["target"])
        assert optimal is not None and optimal >= 1
        assert data["optimal_moves"] == optimal


def test_generator_difficulty_mix():
    rng = random.Random(7)
    lengths = [gen.generate_question_data(rng)["optimal_moves"] for _ in range(120)]
    assert any(v == 1 for v in lengths)
    assert sum(1 for v in lengths if v == 2) >= 20
    assert sum(1 for v in lengths if v >= 3) >= 10


def test_create_puzzle_persists_and_hides_answer(db_session):
    rng = random.Random(11)
    puzzle = gen.create_puzzle(db_session, rng)
    assert puzzle.exercise_slug == SLUG
    assert not puzzle.is_published and not puzzle.is_archived
    assert puzzle.status == "validated"
    assert puzzle.position_json == {
        "from": puzzle.answer_json["from"],
        "target": puzzle.answer_json["target"],
        "piece": puzzle.answer_json["piece"],
    }
    assert "optimal_moves" not in puzzle.position_json
    assert puzzle.answer_json["optimal_moves"] == moves.shortest_path_length(
        puzzle.answer_json["piece"], puzzle.answer_json["from"], puzzle.answer_json["target"]
    )


# --- Security: client cannot override authoritative data ---


def test_client_score_and_optimal_ignored():
    base = answer_for("rook", "a1", "a8", 1)
    out = validate(base, {"path": ["a1", "a4"], "score": 100.0, "optimal_moves": 99, "result": "correct"})
    assert out.result == AttemptResult.WRONG
    assert score_path(out) == 5.0  # server optimal (1), not the client's 99


def test_client_is_correct_ignored():
    base = answer_for("rook", "a1", "a8", 1)
    assert validate(base, {"path": ["a1", "a4"], "isCorrect": True}).result == AttemptResult.WRONG


def test_independent_optimal_recomputed_on_submit(client, db_session):
    rng = random.Random(5)
    puzzle = gen.create_puzzle(db_session, rng)
    ans = puzzle.answer_json
    optimal = moves.shortest_path_length(ans["piece"], ans["from"], ans["target"])
    assert ans["optimal_moves"] == optimal
    publish_generated_pool(db_session, SLUG, gen.create_puzzle, count=1)
    bad = client.post(
        "/api/v1/attempts",
        json={
            "puzzle_id": puzzle.id,
            "answer": {"path": [ans["from"], ans["from"]], "optimal_moves": 0, "score": 999},
            "mode": "practice",
        },
        headers=make_auth_headers(db_session),
    )
    assert bad.json()["result"] == "wrong"


# --- Seed ---


def test_seed_count_and_content(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0  # idempotent
    puzzles = db_session.query(Puzzle).filter(Puzzle.exercise_slug == SLUG).all()
    assert len(puzzles) == 15
    for puzzle in puzzles:
        assert puzzle.fen
        assert puzzle.position_json["from"] != puzzle.position_json["target"]
        assert puzzle.position_json["piece"] in ("knight", "bishop", "rook", "queen")
        assert puzzle.answer_json["optimal_moves"] >= 1
        assert puzzle.prompt_fa
        assert not puzzle.is_published and puzzle.status == "validated"


# --- Step endpoint + attempt API ---


def _seed_puzzle(db_session, seed: int = 3) -> Puzzle:
    puzzle = gen.create_puzzle(db_session, random.Random(seed))
    publish_generated_pool(db_session, SLUG, gen.create_puzzle, count=1)
    return puzzle


def _legal_dest_for(puzzle: Puzzle) -> str:
    ans = puzzle.answer_json
    return sorted(moves.legal_dests(ans["piece"], ans["from"]))[0]


def test_step_endpoint_accepts_valid_move(client, db_session):
    puzzle = _seed_puzzle(db_session)
    start = puzzle.position_json["from"]
    dest = _legal_dest_for(puzzle)
    res = client.post(
        "/api/v1/pathfinding/step",
        json={"puzzle_id": puzzle.id, "fen": puzzle.fen, "selected_at": start, "from": start, "to": dest},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["selected_at"] == dest
    assert body["fen"] != puzzle.fen
    assert body["reached"] == (dest == puzzle.position_json["target"])


def test_step_endpoint_rejects_bad_moves(client, db_session):
    puzzle = _seed_puzzle(db_session)
    start = puzzle.position_json["from"]
    illegal = "a1" if start != "a1" else "h8"
    if moves.is_legal_step(puzzle.answer_json["piece"], start, illegal):
        illegal = "b2" if start != "b2" else "g7"
    for payload in [
        {"from": "e5", "to": "e6"},  # wrong piece
        {"from": start, "to": illegal},  # illegal geometry
        {"from": "zz", "to": dest} if (dest := _legal_dest_for(puzzle)) else {"from": "zz", "to": "a1"},
        {"from": start, "to": _legal_dest_for(puzzle), "fen": "not a fen"},
    ]:
        res = client.post(
            "/api/v1/pathfinding/step",
            json={"puzzle_id": puzzle.id, "fen": payload.pop("fen", puzzle.fen), **payload, "selected_at": start},
        )
        assert res.status_code == 200
        assert res.json()["ok"] is False


def test_step_rejects_origin_mismatch_and_post_completion(client, db_session):
    puzzle = _seed_puzzle(db_session)
    start = puzzle.position_json["from"]
    dest = _legal_dest_for(puzzle)
    res = client.post(
        "/api/v1/pathfinding/step",
        json={"puzzle_id": puzzle.id, "fen": puzzle.fen, "selected_at": "e5", "from": start, "to": dest},
    )
    assert res.json()["ok"] is False
    # Origin already on the star: no further moves accepted.
    res = client.post(
        "/api/v1/pathfinding/step",
        json={
            "puzzle_id": puzzle.id,
            "fen": puzzle.fen,
            "selected_at": puzzle.position_json["target"],
            "from": puzzle.position_json["target"],
            "to": start,
        },
    )
    assert res.json()["ok"] is False


def test_step_endpoint_unknown_puzzle(client, db_session):
    res = client.post(
        "/api/v1/pathfinding/step",
        json={"puzzle_id": 999999, "fen": gen._fen_for("rook", "a1"), "selected_at": "a1", "from": "a1", "to": "a8"},
    )
    assert res.status_code == 404


def test_step_reaches_target_flag(client, db_session):
    rng = random.Random(21)
    puzzle = None
    for _ in range(50):
        candidate = gen.create_puzzle(db_session, rng)
        ans = candidate.answer_json
        if ans["optimal_moves"] == 1 and moves.is_legal_step(ans["piece"], ans["from"], ans["target"]):
            puzzle = candidate
            break
    if puzzle is None:  # pragma: no cover - generator almost always yields one-movers
        puzzle = _seed_puzzle(db_session)
    ans = puzzle.answer_json
    assert moves.is_legal_step(ans["piece"], ans["from"], ans["target"])
    publish_generated_pool(db_session, SLUG, gen.create_puzzle, count=1)
    res = client.post(
        "/api/v1/pathfinding/step",
        json={
            "puzzle_id": puzzle.id,
            "fen": puzzle.fen,
            "selected_at": ans["from"],
            "from": ans["from"],
            "to": ans["target"],
        },
    )
    assert res.json()["ok"] is True
    assert res.json()["reached"] is True


def _bfs_path(kind: str, start: str, target: str) -> list[str]:
    """Independent path (parent pointers) for submit tests."""
    from collections import deque as _dq

    prev: dict[str, str | None] = {start: None}
    queue = _dq([start])
    while queue:
        pos = queue.popleft()
        if pos == target:
            break
        for nxt in moves.legal_dests(kind, pos):
            if nxt not in prev:
                prev[nxt] = pos
                queue.append(nxt)
    assert target in prev
    path = [target]
    while path[-1] != start:
        parent = prev[path[-1]]
        assert parent is not None
        path.append(parent)
    return list(reversed(path))


def test_api_submit_full_path_scores_authoritatively(client, db_session):
    puzzle = _seed_puzzle(db_session)
    headers = make_auth_headers(db_session)
    ans = puzzle.answer_json
    path = _bfs_path(ans["piece"], ans["from"], ans["target"])
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"path": path, "illegal_attempts": 0}, "mode": "practice"},
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == float(ans["optimal_moves"] * 5)
    assert ok.json()["rating_delta"] is None

    bad = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"path": [ans["from"], "h8"]}, "mode": "practice"},
        headers=headers,
    )
    assert bad.json()["result"] == "wrong"

    rated = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"path": path}, "mode": "rated"},
    )
    assert rated.status_code == 401


def test_api_submit_extra_and_illegal_penalized(client, db_session):
    puzzle = _seed_puzzle(db_session)
    ans = puzzle.answer_json
    path = _bfs_path(ans["piece"], ans["from"], ans["target"])
    optimal = ans["optimal_moves"]
    # Valid detour: step to a different neighbor X and back (A->X->A),
    # then follow the optimal path — exactly 2 extra legal moves.
    neighbor = next(d for d in sorted(moves.legal_dests(ans["piece"], path[0])) if d != path[1])
    extra_path = [path[0], neighbor, path[0]] + path[1:]
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": puzzle.id, "answer": {"path": extra_path, "illegal_attempts": 1}, "mode": "practice"},
        headers=make_auth_headers(db_session),
    )
    actual = len(extra_path) - 1
    assert actual == optimal + 2
    expected = float(optimal * 5 - 2 * 2 - 3)
    assert res.json()["result"] == "correct"
    assert res.json()["score"] == expected


def test_api_list_and_detail_hide_answer(client, db_session):
    gen.create_puzzle(db_session, random.Random(31))
    publish_generated_pool(db_session, SLUG, gen.create_puzzle, count=1)
    res = client.get(f"/api/v1/puzzles?exercise={SLUG}")
    assert res.status_code == 200
    assert len(res.json()) >= 1
    assert "answer_json" not in res.json()[0]
    first_id = res.json()[0]["id"]
    assert "optimal_moves" not in str(res.json()[0].get("position_json", {}))
    detail = client.get(f"/api/v1/puzzles/{first_id}")
    assert "answer_json" not in detail.json()


# --- Practice next + speed lifecycle ---


@pytest.fixture
def published_pool(db_session):
    seed_mod.seed_db(db_session)
    publish_generated_pool(db_session, SLUG, gen.create_puzzle)


def _practice_puzzle(client) -> dict:
    res = client.post("/api/v1/pathfinding/next", json={"exclude_ids": []})
    assert res.status_code == 200
    body = res.json()
    assert "answer_json" not in body
    assert body["position_json"]["from"] != body["position_json"]["target"]
    return body


def _submit_path(client, session_id: int | str, puzzle_id: int, answer: dict):
    return client.post(f"/api/v1/pathfinding/sessions/{session_id}/submit", json={"puzzle_id": puzzle_id, "answer": answer})


def test_api_next_and_submit(client, db_session, published_pool):
    headers = make_auth_headers(db_session)
    body = _practice_puzzle(client)
    puzzle = db_session.get(Puzzle, body["id"])
    assert puzzle is not None
    ans = puzzle.answer_json
    path = _bfs_path(ans["piece"], ans["from"], ans["target"])
    ok = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": body["id"], "answer": {"path": path, "illegal_attempts": 0}, "mode": "practice"},
        headers=headers,
    )
    assert ok.json()["result"] == "correct"
    assert ok.json()["score"] == float(ans["optimal_moves"] * 5)


def test_speed_lifecycle(client, db_session, published_pool):
    headers = make_auth_headers(db_session)
    opened = client.post("/api/v1/pathfinding/sessions", json={})
    assert opened.status_code == 200
    sid = opened.json()["session_id"]

    early = client.post(
        f"/api/v1/pathfinding/sessions/{sid}/submit",
        json={"puzzle_id": 1, "answer": {"path": ["a1", "a8"]}},
        headers=headers,
    )
    assert early.status_code == 409

    prepared = client.post(f"/api/v1/pathfinding/sessions/{sid}/puzzles", json={"count": 20})
    assert prepared.status_code == 200
    assert len(prepared.json()) >= 20
    assert all("answer_json" not in p for p in prepared.json())

    started = client.post(f"/api/v1/pathfinding/sessions/{sid}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "active"

    first_id = prepared.json()[0]["id"]
    first = client.get(f"/api/v1/puzzles/{first_id}").json()
    from_sq, target = first["position_json"]["from"], first["position_json"]["target"]
    piece = first["position_json"]["piece"]
    path = _bfs_path(piece, from_sq, target)
    sub = client.post(
        f"/api/v1/pathfinding/sessions/{sid}/submit",
        json={"puzzle_id": first_id, "answer": {"path": path, "illegal_attempts": 1}},
        headers=headers,
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["result"] == "correct"
    # Same formula in speed: optimal*5 - 0 extra - 1*3.
    optimal = moves.shortest_path_length(piece, from_sq, target)
    assert sub.json()["attempt"]["score"] == float(optimal * 5 - 3)

    report = client.get(f"/api/v1/pathfinding/sessions/{sid}/report")
    assert report.status_code == 200
    assert len(report.json()["entries"]) == 1

    finished = client.post(f"/api/v1/pathfinding/sessions/{sid}/finish")
    assert finished.status_code == 200
    assert finished.json()["status"] == "finished"


def test_speed_requires_full_buffer(client):
    opened = client.post("/api/v1/pathfinding/sessions", json={}).json()
    sid = opened["session_id"]
    client.post(f"/api/v1/pathfinding/sessions/{sid}/puzzles", json={"count": 5})
    assert client.post(f"/api/v1/pathfinding/sessions/{sid}/start").status_code == 409


def test_speed_unknown_session_404(client):
    assert client.get("/api/v1/pathfinding/sessions/nope").status_code == 404


def test_speed_submit_ignores_client_score(client, db_session, published_pool):
    opened = client.post("/api/v1/pathfinding/sessions", json={}).json()
    sid = opened["session_id"]
    prepared = client.post(f"/api/v1/pathfinding/sessions/{sid}/puzzles", json={"count": 20}).json()
    client.post(f"/api/v1/pathfinding/sessions/{sid}/start")
    first_id = prepared[0]["id"]
    first = client.get(f"/api/v1/puzzles/{first_id}").json()
    path = _bfs_path(first["position_json"]["piece"], first["position_json"]["from"], first["position_json"]["target"])
    sub = client.post(
        f"/api/v1/pathfinding/sessions/{sid}/submit",
        json={"puzzle_id": first_id, "answer": {"path": path, "score": 9999, "optimal_moves": 99}},
        headers=make_auth_headers(db_session),
    )
    assert sub.status_code == 200
    assert sub.json()["attempt"]["score"] != 9999.0


def test_practice_submit_ignores_client_fen(client, db_session, published_pool):
    body = _practice_puzzle(client)
    res = client.post(
        "/api/v1/attempts",
        json={"puzzle_id": body["id"], "answer": {"path": [], "fen": "8/8/8/8/8/8/8/R7 w - - 0 1"}, "mode": "practice"},
        headers=make_auth_headers(db_session),
    )
    assert res.status_code == 200
    assert res.json()["result"] == "wrong"
