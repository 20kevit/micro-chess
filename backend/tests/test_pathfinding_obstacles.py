"""Exercise 7 (Pathfinding with Obstacles): state, rules, solver, scoring, API.

Covers the exercise spec:
- state representation (enemy sets distinguish states, canonical keys)
- movement per piece (knight/bishop/rook/queen) + physical blocking +
  knight jumping + attacked intermediates ignored for sliders
- destination safety (safe allowed, attacked rejected, multi-attacker)
- captures (undefended ok, defended rejected, controlled-dest rejected,
  removal + attack-map/defender recomputation)
- dynamic defender-removal scenario (A defends B -> capture A -> B free)
- solver (solution found, unsolvable rejected, true minimum, multiple
  optimal routes, state-distinguishing, post-capture recomputation)
- generator (constraints, verified solutions, allowed kinds, no kings)
- scoring formula (optimal*5, extra*-2, illegal*-3, negatives)
- runtime validation + step oracle + practice next + speed lifecycle
"""

import random

import pytest

from app.modules.exercises import registry
from app.modules.pathfinding_obstacles import generator as gen
from app.modules.pathfinding_obstacles import seed as seed_mod
from app.modules.pathfinding_obstacles import sessions as session_service
from app.modules.pathfinding_obstacles import transitions as tr
from app.modules.pathfinding_obstacles.models import ObstaclePathfindingSpeedSession
from app.modules.pathfinding_obstacles.scoring import score_obstacle_path
from app.modules.pathfinding_obstacles.validator import (
    SLUG,
    apply_step,
    replay_path,
    validate,
)
from app.modules.puzzles.models import Puzzle
from app.modules.rule_engine.base import AttemptResult


def S(kind, white, enemies, target):
    return tr.State(white_kind=kind, white_square=white, enemies=tuple(enemies), target=target)


def answer_for(state, optimal):
    d = tr.state_to_dict(state)
    d["optimal_moves"] = optimal
    return d


# --- State representation ---


def test_same_square_different_enemies_are_different_states():
    a = S("rook", "a5", (("c3", "knight"), ("f5", "bishop")), "a8")
    b = S("rook", "a5", (("f5", "bishop"),), "a8")
    assert a.key() != b.key()
    assert hash(a.key()) != hash(b.key())


def test_canonical_key_stable_and_order_insensitive():
    a = tr.parse_state(
        {"piece": "rook", "from": "a5", "target": "a8",
         "enemies": [{"square": "c3", "kind": "knight"}, {"square": "f5", "kind": "bishop"}]}
    )
    b = tr.parse_state(
        {"piece": "rook", "from": "a5", "target": "a8",
         "enemies": [{"square": "f5", "kind": "bishop"}, {"square": "c3", "kind": "knight"}]}
    )
    assert a == b
    assert tr.canonical_key(a) == tr.canonical_key(b)


def test_parse_state_rejects_bad_input():
    with pytest.raises(ValueError):
        tr.parse_state({"piece": "king", "from": "a1", "target": "a8", "enemies": []})
    with pytest.raises(ValueError):
        tr.parse_state({"piece": "rook", "from": "a1", "target": "a8",
                        "enemies": [{"square": "a9", "kind": "pawn"}]})
    with pytest.raises(ValueError):
        tr.parse_state({"piece": "rook", "from": "a1", "target": "a8",
                        "enemies": [{"square": "b2", "kind": "king"}]})


# --- Movement ---


def test_knight_jumps_over_pieces():
    s = S("knight", "b1", (("b2", "pawn"), ("c3", "pawn"), ("d2", "pawn")), "a3")
    assert tr.apply_move(s, "a3") is not None
    assert tr.apply_move(s, "c3") is not None  # capture, undefended pawn
    assert tr.apply_move(s, "b2") is None  # not a knight move


def test_rook_blocked_by_enemy():
    s = S("rook", "a1", (("a4", "pawn"),), "a8")
    assert tr.apply_move(s, "a8") is None  # blocked
    assert tr.apply_move(s, "a3") is not None  # before the blocker
    assert tr.apply_move(s, "a4") is not None  # capture of the blocker


def test_bishop_blocked_by_enemy():
    s = S("bishop", "c1", (("e3", "pawn"),), "h6")
    assert tr.apply_move(s, "h6") is None
    assert tr.apply_move(s, "b2") is not None  # free diagonal, safe landing
    assert tr.apply_move(s, "e3") is not None  # capture of the blocker
    # The pawn on e3 controls d2, so the bishop cannot land there.
    assert tr.black_attackers(s, "d2") == {"e3"}
    assert tr.apply_move(s, "d2") is None


def test_queen_union_with_blocking():
    s = S("queen", "d4", (("d6", "pawn"),), "d8")
    assert tr.apply_move(s, "d8") is None
    assert tr.apply_move(s, "d6") is not None
    assert tr.apply_move(s, "h8") is not None  # diagonal unblocked


def test_null_and_off_piece_moves_rejected():
    s = S("rook", "a1", (), "a8")
    assert tr.apply_move(s, "a1") is None
    assert tr.apply_move(s, "b2") is None  # diagonal illegal for rook
    assert tr.apply_move(s, "a9") is None  # malformed


# --- Destination safety ---


def test_safe_destination_allowed():
    s = S("rook", "a1", (("h8", "bishop"),), "a8")
    assert tr.apply_move(s, "a8") is not None


def test_attacked_destination_rejected():
    # Black bishop g2 attacks a8 along the diagonal.
    s = S("rook", "a1", (("g2", "bishop"),), "a8")
    assert tr.apply_move(s, "a8") is None


def test_attacked_intermediate_square_does_not_matter():
    # Rook a1 -> a8 where an enemy knight attacks intermediate squares
    # but NOT the destination: the move must stay legal.
    s = S("rook", "a1", (("c3", "knight"),), "a8")
    attacked_mid = {sq for sq in ("a2", "a3", "a4", "a5", "a6", "a7") if tr.black_attackers(s, sq)}
    assert attacked_mid, "test setup must attack an intermediate square"
    assert not tr.black_attackers(s, "a8"), "destination must be safe in this setup"
    assert tr.apply_move(s, "a8") is not None


def test_destination_attacked_by_multiple_enemies_rejected():
    # Knight c3 and queen b2 both control b1.
    s = S("rook", "a1", (("c3", "knight"), ("b2", "queen")), "b1")
    assert tr.black_attackers(s, "b1") == {"c3", "b2"}
    assert tr.apply_move(s, "b1") is None


# --- Captures ---


def test_undefended_enemy_can_be_captured():
    s = S("rook", "a1", (("a4", "pawn"),), "a8")
    assert tr.is_undefended(s, "a4")
    nxt = tr.apply_move(s, "a4")
    assert nxt is not None
    assert nxt.enemies == ()
    assert nxt.white_square == "a4"


def test_defended_enemy_cannot_be_captured():
    # Rook a5 defended by rook a6.
    s = S("rook", "a1", (("a5", "rook"), ("a6", "rook")), "a8")
    assert not tr.is_undefended(s, "a5")
    assert tr.apply_move(s, "a5") is None


def test_capture_onto_controlled_square_rejected():
    # Condition B is evaluated on the RESULTING position, which makes it
    # independent from Condition A: the white rook on e7 shields e6 from
    # the black rook on e8, so the pawn looks undefended pre-move — but
    # after the capture the ray opens and the landing square is
    # controlled, so the capture is ILLEGAL.
    s = S("rook", "e7", (("e6", "pawn"), ("e8", "rook")), "e4")
    assert tr.is_undefended(s, "e6")
    assert tr.apply_move(s, "e6") is None
    # Same uncovering for a quiet move: e7 -> e5 looks safe pre-move
    # (the white rook blocks the file) but lands on a controlled square.
    assert tr.apply_move(s, "e5") is None
    # Sanity: without the black rook behind, the capture is fine.
    plain = S("rook", "e7", (("e6", "pawn"),), "e4")
    assert tr.apply_move(plain, "e6") is not None


def test_capture_removes_piece_and_changes_attack_map():
    s = S("rook", "a1", (("a4", "pawn"), ("g2", "bishop")), "a8")
    # Black pawn a4 attacks b3 (black pawns strike toward rank 1).
    assert tr.black_attackers(s, "b3") == {"a4"}
    nxt = tr.apply_move(s, "a4")
    assert nxt is not None
    assert tr.black_attackers(nxt, "b3") == set()
    # a8 still controlled by the bishop after the pawn is gone.
    assert tr.black_attackers(nxt, "a8") == {"g2"}


def test_defender_status_changes_after_capture():
    # Pawn d4 defended by bishop g1; queen takes the bishop first.
    s = S("queen", "a1", (("d4", "pawn"), ("g1", "bishop")), "h8")
    assert not tr.is_undefended(s, "d4")
    mid = tr.apply_move(s, "g1")
    assert mid is not None
    assert tr.is_undefended(mid, "d4")


def test_no_pin_filtering_without_kings():
    # A black piece "aligned" with nothing still defends: raw attackers count.
    s = S("rook", "a1", (("d5", "pawn"), ("d8", "rook")), "a8")
    assert not tr.is_undefended(s, "d5")
    assert tr.apply_move(s, "d5") is None


# --- Dynamic multi-step scenario ---


def test_dynamic_defender_removal_opens_route():
    # Pawn d4 blocks the d-file and is defended by bishop b6, which also
    # guards the star d8: the bishop capture is FORCED (no quiet route
    # can land on the controlled star). Then d4 falls and the file opens.
    s = S("queen", "a1", (("d4", "pawn"), ("b6", "bishop")), "d8")
    assert not tr.is_undefended(s, "d4")
    assert tr.apply_move(s, "d4") is None  # defended: cannot capture yet
    assert tr.black_attackers(s, "d8") == {"b6"}  # star guarded
    step1 = tr.apply_move(s, "a6")
    assert step1 is not None
    step2 = tr.apply_move(step1, "b6")  # capture the guard
    assert step2 is not None and len(step2.enemies) == 1
    assert tr.is_undefended(step2, "d4")  # d4 now undefended
    step3 = tr.apply_move(step2, "d8")  # star now safe, file route open
    assert step3 is not None and step3.white_square == "d8"
    solved = tr.solve(s)
    assert solved is not None
    assert solved["optimal_moves"] == 3
    assert solved["captures"] == 1
    assert validate(answer_for(s, 3),
                    {"path": solved["path"], "illegal_attempts": 0}).result == AttemptResult.CORRECT


# --- Solver ---


def test_solver_finds_solution_and_true_minimum():
    s = S("rook", "a1", (("a4", "pawn"),), "a8")
    solved = tr.solve(s)
    assert solved is not None
    # a1->a4(x)->a8 would land on... a8 safe here (no bishop), so 2 moves.
    assert solved["optimal_moves"] == 2
    assert solved["path"][0] == "a1" and solved["path"][-1] == "a8"
    # The reported path replays legally to the star.
    assert validate(answer_for(s, solved["optimal_moves"]),
                    {"path": solved["path"], "illegal_attempts": 0}).result == AttemptResult.CORRECT


def test_solver_rejects_unsolvable():
    # Rook boxed: file blocked by defended piece, rank attacked everywhere reachable.
    s = S("rook", "a1", (("a5", "rook"), ("a6", "rook")), "a8")
    assert tr.solve(s) is None


def test_solver_distinguishes_enemy_sets_not_just_squares():
    # The star d2 is controlled by the pawn on c3, so the direct knight
    # hop is illegal and the pawn must be removed first: a squares-only
    # BFS would wrongly answer 1, the state-space BFS answers 3.
    s = S("knight", "b1", (("c3", "pawn"),), "d2")
    assert tr.apply_move(s, "d2") is None
    solved = tr.solve(s)
    assert solved is not None
    assert solved["optimal_moves"] == 3
    assert solved["path"] == ["b1", "c3", "e4", "d2"]
    assert validate(answer_for(s, 3), {"path": solved["path"], "illegal_attempts": 0}).result == AttemptResult.CORRECT
    # Same (piece, from, target) with no enemies is a different problem.
    bare = S("knight", "b1", (), "d2")
    assert tr.solve(bare)["optimal_moves"] == 1


def test_solver_recomputes_attacks_after_captures():
    s = S("rook", "a1", (("a4", "pawn"), ("g2", "bishop")), "a8")
    solved = tr.solve(s)
    assert solved is not None
    # Must capture the pawn (blocker) AND the bishop (star guard): >= 3 moves.
    assert solved["captures"] >= 1
    assert solved["optimal_moves"] >= 3
    assert validate(answer_for(s, solved["optimal_moves"]),
                    {"path": solved["path"], "illegal_attempts": 0}).result == AttemptResult.CORRECT


def test_solver_counts_moves_not_squares():
    s = S("rook", "a1", (), "h8")
    solved = tr.solve(s)
    assert solved is not None
    assert solved["optimal_moves"] == 2  # two piece moves, not 14 squares


def test_empty_board_distance_baseline():
    assert tr.empty_board_distance("rook", "a1", "a8") == 1
    assert tr.empty_board_distance("bishop", "c1", "h6") == 1
    assert tr.empty_board_distance("bishop", "c1", "d4") == 2
    assert tr.empty_board_distance("bishop", "c1", "c2") is None  # opposite color


# --- Validator: replay semantics ---


def _rook_blocker_answer():
    s = S("rook", "a1", (("a4", "pawn"),), "a8")
    return s, answer_for(s, 2)


def test_validate_accepts_optimal_and_longer_valid_routes():
    s, answer = _rook_blocker_answer()
    assert validate(answer, {"path": ["a1", "a4", "a8"], "illegal_attempts": 0}).result == AttemptResult.CORRECT
    # Longer but legal route is still CORRECT (extra-move penalty in scoring).
    long_ok = validate(answer, {"path": ["a1", "a4", "a5", "a8"], "illegal_attempts": 0})
    assert long_ok.result == AttemptResult.CORRECT
    assert long_ok.detail["moves"] == 3


def test_validate_rejects_illegal_step_wrong_start_incomplete():
    s, answer = _rook_blocker_answer()
    assert validate(answer, {"path": ["a1", "a8"], "illegal_attempts": 0}).result == AttemptResult.WRONG
    assert validate(answer, {"path": ["a2", "a4", "a8"], "illegal_attempts": 0}).result == AttemptResult.WRONG
    assert validate(answer, {"path": ["a1", "a4"], "illegal_attempts": 0}).result == AttemptResult.WRONG
    assert validate(answer, {"path": [], "illegal_attempts": 0}).result == AttemptResult.WRONG
    assert validate(answer, {"path": ["a1", "a9"], "illegal_attempts": 0}).result == AttemptResult.WRONG


def test_validate_ignores_client_optimal_and_counts_illegal():
    s, answer = _rook_blocker_answer()
    res = validate(answer, {"path": ["a1", "a4", "a8"], "illegal_attempts": 5, "optimal_moves": 99})
    assert res.result == AttemptResult.CORRECT
    assert res.detail["optimal_moves"] == 2
    assert res.detail["illegal_attempts"] == 5


def test_apply_step_oracle():
    s, _ = _rook_blocker_answer()
    nxt = apply_step(s, "a1", "a4")
    assert nxt is not None and nxt.white_square == "a4"
    assert apply_step(s, "a1", "a8") is None  # blocked
    assert apply_step(s, "a2", "a4") is None  # origin != selected
    done = S("rook", "a8", (), "a8")
    assert apply_step(done, "a8", "a7") is None  # post-completion


def test_replay_path_reports_captures_and_failures():
    s, _ = _rook_blocker_answer()
    run = replay_path(s, ["a1", "a4", "a8"])
    assert run == {"ok": True, "prefix": ["a1", "a4", "a8"], "fail_at": None,
                   "reached": True, "moves": 2, "captures": 1}
    run = replay_path(s, ["a1", "a8"])
    assert run["ok"] is False and run["fail_at"] == "a8"


# --- Scoring ---


def _validation(moves, optimal, illegal):
    from app.modules.rule_engine.base import ValidationResult
    return ValidationResult(result=AttemptResult.CORRECT, message_key="feedback.correct",
                            detail={"moves": moves, "optimal_moves": optimal, "illegal_attempts": illegal})


def test_scoring_optimal_only():
    assert score_obstacle_path(_validation(3, 3, 0)) == 15.0


def test_scoring_extra_moves():
    assert score_obstacle_path(_validation(5, 3, 0)) == 15.0 - 4.0


def test_scoring_illegal_attempts():
    assert score_obstacle_path(_validation(3, 3, 2)) == 15.0 - 6.0


def test_scoring_combined_and_negative():
    assert score_obstacle_path(_validation(5, 3, 2)) == 5.0
    assert score_obstacle_path(_validation(0, 1, 5)) == 5.0 - 15.0  # negative allowed
    # Illegal attempts never inflate the legal move count.
    _, answer = _rook_blocker_answer()
    v = validate(answer, {"path": ["a1", "a4", "a8"], "illegal_attempts": 4})
    assert v.detail["moves"] == 2
    assert score_obstacle_path(v) == 10.0 - 12.0


def test_scoring_registered_for_slug():
    assert registry.get_scorer(SLUG) is not None
    assert registry.get_validator(SLUG) is not None


# --- Generator ---


def test_generator_always_serves_verified_solvable_puzzles():
    rng = random.Random(1234)
    for _ in range(10):
        data = gen.generate_question_data(rng)
        state = tr.parse_state(
            {"piece": data["piece"], "from": data["from"], "target": data["target"],
             "enemies": data["enemies"]}
        )
        solved = tr.solve(state)
        assert solved is not None
        assert solved["optimal_moves"] == data["optimal_moves"]
        assert gen.MIN_OPTIMAL <= data["optimal_moves"] <= gen.MAX_OPTIMAL
        assert gen.MIN_ENEMIES <= len(data["enemies"]) <= gen.MAX_ENEMIES


def test_generator_board_constraints():
    rng = random.Random(99)
    for _ in range(10):
        data = gen.generate_question_data(rng)
        assert data["piece"] in tr.ALLOWED_WHITE_KINDS
        assert data["from"] != data["target"]
        assert len(data["enemies"]) >= 1
        occupied = {data["from"], data["target"]}
        for enemy in data["enemies"]:
            assert enemy["kind"] in tr.ALLOWED_ENEMY_KINDS
            assert enemy["square"] not in occupied
            occupied.add(enemy["square"])
            if enemy["kind"] == "pawn":
                assert enemy["square"][1] not in ("1", "8")
        # No kings anywhere in the rendered position.
        assert "k" not in data["fen"].split(" ")[0].lower().replace("n", "")


def test_generator_piece_mix_covers_sliders():
    rng = random.Random(7007)
    kinds = {gen.generate_question_data(rng)["piece"] for _ in range(30)}
    assert "knight" in kinds
    assert kinds & {"bishop", "rook", "queen"}, "sliders must appear"


def test_generator_meaningfulness_gate():
    # Every served puzzle must need a capture or beat the empty baseline.
    rng = random.Random(2024)
    for _ in range(10):
        data = gen.generate_question_data(rng)
        state = tr.parse_state(
            {"piece": data["piece"], "from": data["from"], "target": data["target"],
             "enemies": data["enemies"]}
        )
        solved = tr.solve(state)
        assert solved is not None
        baseline = tr.empty_board_distance(data["piece"], data["from"], data["target"])
        assert baseline is not None
        assert solved["captures"] >= 1 or solved["optimal_moves"] > baseline


def test_create_puzzle_persists_and_reuses(db_session):
    rng = random.Random(7)
    first = gen.create_puzzle(db_session, rng)
    assert first.exercise_slug == SLUG
    assert first.is_published and not first.is_archived
    assert "optimal_moves" in first.answer_json
    assert "optimal_moves" not in first.position_json
    # Solver accepts the persisted puzzle.
    state = tr.parse_state(
        {"piece": first.answer_json["piece"], "from": first.answer_json["from"],
         "target": first.answer_json["target"], "enemies": first.answer_json["enemies"]}
    )
    solved = tr.solve(state)
    assert solved is not None
    assert solved["optimal_moves"] == first.answer_json["optimal_moves"]


def test_seed_idempotent(db_session):
    assert seed_mod.seed_db(db_session) == 15
    assert seed_mod.seed_db(db_session) == 0


# --- Runtime API ---


def test_practice_next_never_leaks_answer(client):
    res = client.post("/api/v1/pathfinding-obstacles/next", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["exercise_slug"] == SLUG
    assert body["fen"] is not None
    pos = body["position_json"]
    assert {"from", "target", "piece", "enemies"} <= set(pos.keys())
    assert "answer_json" not in body


def test_step_oracle_accepts_rejects_and_tracks_capture(client):
    nxt = client.post("/api/v1/pathfinding-obstacles/next", json={}).json()
    pid = nxt["id"]
    fen, pos = nxt["fen"], nxt["position_json"]
    state = tr.parse_state(
        {"piece": pos["piece"], "from": pos["from"], "target": pos["target"], "enemies": pos["enemies"]}
    )
    transitions = tr.legal_transitions(state)
    assert transitions, "generated puzzle must have at least one legal first move"
    dest = sorted(transitions)[0]
    good = client.post("/api/v1/pathfinding-obstacles/step", json={
        "puzzle_id": pid, "fen": fen, "selected_at": pos["from"],
        "from": pos["from"], "to": dest}).json()
    assert good["ok"] is True
    assert good["selected_at"] == dest
    if transitions[dest]["capture"]:
        assert good["captured"] == dest
    else:
        assert good["captured"] is None
    # A far illegal destination is rejected with the board unchanged.
    bad = client.post("/api/v1/pathfinding-obstacles/step", json={
        "puzzle_id": pid, "fen": fen, "selected_at": pos["from"],
        "from": pos["from"], "to": pos["from"]}).json()
    assert bad["ok"] is False
    assert bad["fen"] == fen


def test_step_unknown_puzzle_404(client):
    res = client.post("/api/v1/pathfinding-obstacles/step", json={
        "puzzle_id": 999999, "fen": "8/8/8/8/8/8/8/8 w - - 0 1",
        "selected_at": "a1", "from": "a1", "to": "a2"})
    assert res.status_code == 404


def test_attempt_api_authoritative_score_and_no_leak(client):
    nxt = client.post("/api/v1/pathfinding-obstacles/next", json={}).json()
    pos = nxt["position_json"]
    state = tr.parse_state(
        {"piece": pos["piece"], "from": pos["from"], "target": pos["target"], "enemies": pos["enemies"]}
    )
    solved = tr.solve(state)
    assert solved is not None
    res = client.post("/api/v1/attempts", json={
        "puzzle_id": nxt["id"],
        "answer": {"path": solved["path"], "illegal_attempts": 1,
                   "score": 9999, "optimal_moves": 1},
        "mode": "practice",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["result"] == "correct"
    expected = solved["optimal_moves"] * 5 - 3
    assert body["score"] == expected
    assert body["rating_delta"] is None  # practice never rates
    # Puzzle detail endpoints never expose the answer.
    detail = client.get(f"/api/v1/puzzles/{nxt['id']}").json()
    assert "answer_json" not in detail


def test_attempt_wrong_path_rejected(client):
    nxt = client.post("/api/v1/pathfinding-obstacles/next", json={}).json()
    pos = nxt["position_json"]
    res = client.post("/api/v1/attempts", json={
        "puzzle_id": nxt["id"],
        "answer": {"path": [pos["from"]], "illegal_attempts": 0},
        "mode": "practice",
    })
    assert res.status_code == 200
    assert res.json()["result"] == "wrong"


def test_speed_lifecycle_buffer_clock_submit_report(client):
    session = client.post("/api/v1/pathfinding-obstacles/sessions", json={}).json()
    sid = session["session_id"]
    assert session["status"] == "preparing"
    # Clock refuses to start before the 20-puzzle buffer exists.
    res = client.post(f"/api/v1/pathfinding-obstacles/sessions/{sid}/start")
    assert res.status_code == 409
    batch = client.post(
        f"/api/v1/pathfinding-obstacles/sessions/{sid}/puzzles", json={"count": 20}).json()
    assert len(batch) == 20
    # Buffered puzzles carry no answers.
    assert all("answer_json" not in p for p in batch)
    started = client.post(f"/api/v1/pathfinding-obstacles/sessions/{sid}/start").json()
    assert started["status"] == "active"
    first = batch[0]
    pos = first["position_json"]
    state = tr.parse_state(
        {"piece": pos["piece"], "from": pos["from"], "target": pos["target"], "enemies": pos["enemies"]}
    )
    solved = tr.solve(state)
    assert solved is not None
    sub = client.post(f"/api/v1/pathfinding-obstacles/sessions/{sid}/submit", json={
        "puzzle_id": first["id"],
        "answer": {"path": solved["path"], "illegal_attempts": 0},
    }).json()
    assert sub["attempt"]["result"] == "correct"
    assert sub["session"]["attempted"] == 1
    report = client.get(f"/api/v1/pathfinding-obstacles/sessions/{sid}/report").json()
    assert len(report["entries"]) == 1
    assert report["entries"][0]["result"] == "correct"
    # Unknown puzzle is not submittable in the session.
    res = client.post(f"/api/v1/pathfinding-obstacles/sessions/{sid}/submit", json={
        "puzzle_id": 999999, "answer": {"path": ["a1"], "illegal_attempts": 0}})
    assert res.status_code == 404
    # Unknown session id.
    assert client.get("/api/v1/pathfinding-obstacles/sessions/does-not-exist").status_code == 404


def test_apply_step_rejects_post_completion_and_wrong_origin():
    # Exercise apply_step directly: completion + mismatch guards.
    s = S("rook", "a1", (("a4", "pawn"),), "a8")
    done = S("rook", "a8", (), "a8")
    assert apply_step(done, "a8", "a7") is None
    assert apply_step(s, "a2", "a4") is None
