# Exercise 7 — Pathfinding with Obstacles (مسیر یابی با مانع)

Production v1 status. The user sees ONE white piece plus black enemies
plus a star square and must walk the piece to the star with legal chess
moves while respecting obstacle rules («مهره را با کمترین حرکت به ستاره
برسانید.»). Identifier: `pathfinding-obstacles`.

This is the direct, more advanced evolution of **Exercise 6 —
Pathfinding** (empty board). It owns the concepts deliberately excluded
there: black pieces, attacked squares, capture-based obstacle removal,
defended-piece logic, dynamic attack maps, and path changes caused by
captures.

## Board composition

Every puzzle contains exactly:

- one WHITE mover: knight (50%) / bishop (20%) / rook (20%) / queen
  (10%) — the same mix as Exercise 6;
- one or more BLACK enemies: pawn / knight / bishop / rook / queen
  (1–5 pieces; black pawns never on rank 1/8);
- one star/target square, distinct from the start square, empty at
  puzzle start, never containing a black piece initially;
- nothing else: no white king, no black king, no kings at all, no
  second white piece, no white pawn.

Enemies never move. They affect physical occupancy, attack/control, and
capture possibilities, and disappear when legally captured.

## Movement and safety rules

The white piece moves with normal chess movement; enemies physically
block sliding rays (knights jump as usual).

Safety rule: **the white piece may NEVER LAND on a square controlled by
an enemy piece.** This applies to every successful white move.

> For sliding pieces, only the landing square must be safe; enemy
> control of intermediate squares does not make the move illegal.
> Physical occupancy still blocks the path.

Example: rook `a1 → a8` with `a4` attacked by a black bishop but `a8`
safe is allowed (assuming no physical blocker).

> Capture requires both an undefended target piece and a safe
> destination square.

- **Condition A (undefended):** the victim must have zero other black
  pieces attacking its square on the CURRENT board. No pin filtering,
  no king-safety: no kings exist (same attack geometry as
  `python-chess` `board.attackers`,unlike Exercise 4 which excludes
  absolutely pinned pieces).
- **Condition B (safe landing):** the destination must be uncontrolled
  by ANY black piece on the RESULTING board (white already landed,
  victim already removed). This makes B independent from A: the white
  piece's own departure can uncover a black ray onto the landing
  square (e.g. a white rook shielding its destination from a black
  rook behind it). Pre-move the square looks safe; post-move it is
  controlled — the move is illegal.

## Dynamic enemy control

Enemy control is NOT static. After every successful capture the victim
disappears and attacks/defenders are recomputed, so a defended piece
can become capturable and a blocked/guarded route can open:

```text
Black A defends Black B, B blocks the route, B cannot be captured.
White captures A → A disappears → B undefended → B capturable →
removing B opens the route.
```

## State-space model and BFS solver

> The solver searches complete board states, not merely white-piece
> positions.

`State { white kind, white square, remaining enemies, target }`, with a
canonical sorted-enemies key (`transitions.canonical_key`). BFS over
`(state → valid transition → new state)` minimizes the NUMBER OF WHITE
MOVES (every move costs 1); the first goal found gives `optimal_moves`.
No route is ever enforced: any valid route with exactly `optimalMoves`
is optimal. Cap `MAX_VISITED = 30000` guards degenerate spaces (served
puzzles stay far below it; see generator).

Single authoritative layer: `pathfinding_obstacles/transitions.py` is
used by the runtime validator, the step oracle, the solver, and the
generator — no parallel rule implementations.

## Generator (`generator.py`)

Generate → board-constraint check → BFS solve → quality-gate check →
accept/reject. Never serves an unverified position.

- Kinds drawn with the documented weights; each drawn kind gets its
  own bounded batch of enemy placements (sliders accept random
  placements far less often than knights — without per-kind retries
  the output collapses to nearly all knights).
- Gates: 1–5 enemies, `optimal_moves` 2–10, solver visited ≤ 20000,
  bishop color bound via the empty-board baseline, and
  meaningfulness: the optimal route must capture at least once OR beat
  the empty-board distance (rejects positions identical to trivial
  Exercise 6 puzzles).
- ~20 puzzles generate in ~3s; practice serves on demand, speed
  prepares ≥20 before the clock starts.

Persisted row: `fen` (full position, rendering),
`position_json = {from, target, piece, enemies}` (public),
`answer_json = {from, target, piece, enemies, optimal_moves}`
(server-only). Identical enemy configurations are reused, not
duplicated; `exclude_ids` steers variety.

## Validation (`validator.py`)

`validate(answer, attempt)` with attempt
`{path: [...squares], illegal_attempts: n}` replays the path
STATEFULLY from the stored initial state: CORRECT iff every step is a
legal transition of the current state (captures update the enemy set)
AND the path ends exactly on the target. Otherwise WRONG (no PARTIAL).

Step oracle (`POST /pathfinding-obstacles/step`, `apply_step`): rebuilds
the LIVE state from the client FEN (current enemies included) with the
server-stored kind/target, validates one transition, returns the updated
FEN + `reached` + `captured`. Rejects wrong origins, null moves,
post-completion moves, inconsistent FENs, and unknown puzzles (404).
Final grading still revalidates the whole path from the initial state.

## Scoring (authoritative, `scoring.py`)

```text
score = optimal_moves × 5
      − max(0, actual_moves − optimal_moves) × 2
      − illegal_attempts × 3
```

Same formula as Exercise 6. Registered via
`register_scorer("pathfinding-obstacles", score_obstacle_path)`.
Captures count as one legal move. Negative scores allowed, never
clamped.

## User flow

Same shell and lifecycle as Exercise 6 (`PathfindingObstaclesPlay`:
practice + speed reusing `PieceGameLayout.GameShell`, timer, hints,
feedback; drag primary, click-to-move supported, piece stays selected,
220ms practice / 110ms speed glide, illegal buzz + 700ms red flash;
arrival auto-submits `{path, illegal_attempts}`).

- Illegal attempt: error buzz (`lib/sound.ts`), red destination
  highlight, piece stays, `illegalAttempts + 1`, still selected, puzzle
  stays active — no reset.
- Legal move: glide animation, state updates, capture removes the enemy
  (rendered from the server-returned FEN), control maps recomputed
  server-side for the next step.
- Speed: `preparing` → `active` → `finished`/`expired`
  (`pathfinding_obstacles_speed_sessions`, same columns as Exercise 6),
  ≥20 prepared before the 60s clock, ~400ms auto-advance, background
  refill, server-rebuilt report.

## Persian / RTL rendering

Page RTL; board island `dir="ltr"`, white orientation. Same gold star
SVG (55%, pointer-transparent) and design-system typography. New
strings: `exercises.pathfinding-obstacles.title/desc` («مسیر یابی با
مانع»); move/illegal/arrival/score/invalid texts reuse the
`pathfinding.*` keys (same wording, one vocabulary).

## Security

- `answer_json` (incl. `optimal_moves`) never leaves the server —
  including prefetch/session buffers; `position_json` carries only
  task data. Enemy kinds/squares are public (rendered); nothing about
  the solution is.
- Grading/scoring recompute from the stored answer; client `score` /
  `optimal_moves` / `fen` overrides are ignored. Step-oracle FENs are
  cross-checked against the stored kind/enemies (type-substitution
  rejected); final grading replays from the stored initial state.
- Only session-issued puzzles are submittable (404 otherwise); the
  speed clock is server-authoritative (410 on expiry);
  post-completion steps rejected.

## API

| Method & path | Purpose |
|---|---|
| `POST /api/v1/pathfinding-obstacles/next` `{exclude_ids?}` | fresh solved practice puzzle (`PuzzleOut`, no answer) |
| `POST /api/v1/pathfinding-obstacles/step` `{puzzle_id, fen, selected_at, from, to}` | single-step oracle (`StepOut`: updated FEN, `reached`, `captured`) |
| `POST /api/v1/pathfinding-obstacles/sessions` | open session (`preparing`, clock NOT running) |
| `POST /api/v1/pathfinding-obstacles/sessions/{id}/puzzles` `{count}` | prepare N buffer puzzles (`410` when expired; capped at 60) |
| `POST /api/v1/pathfinding-obstacles/sessions/{id}/start` | start the 60s clock (`409 buffer_not_ready` below 20) |
| `POST /api/v1/pathfinding-obstacles/sessions/{id}/next` | single session puzzle |
| `POST /api/v1/pathfinding-obstacles/sessions/{id}/submit` | graded path + updated summary (`409` before start, `410` when expired) |
| `GET /api/v1/pathfinding-obstacles/sessions/{id}` | summary (auto-expires) |
| `GET /api/v1/pathfinding-obstacles/sessions/{id}/report` | authoritative per-puzzle report |
| `POST /api/v1/pathfinding-obstacles/sessions/{id}/finish` | end early + summary |
| `POST /api/v1/attempts` | standard attempt submit (practice; `{path, illegal_attempts}`) |

Errors: `session_not_found` (404), `session_not_started` (409),
`session_expired` (410), `buffer_not_ready` (409),
`puzzle_not_in_session`/`puzzle_not_available` (404).

## Tests

- Backend `tests/test_pathfinding_obstacles.py` (48 tests): state
  identity/canonical keys; per-piece movement + blocking + knight
  jumps + attacked-intermediate acceptance; destination safety
  (safe/attacked/multi-attacker); captures (undefended/defended/
  controlled-dest/uncovering/Condition-B-post-move, removal +
  attack-map/defender recomputation, no pin filtering); forced-capture
  dynamic scenario; solver (minimum, unsolvable, state separation,
  post-capture recomputation, move counting, baseline); validator
  replay (optimal + longer routes, wrong start/incomplete/malformed,
  client-optimal ignored, oracle guards); scoring (optimal/extra/
  illegal/combined/negative/registration); generator (verified
  solutions, constraints, no kings/pawn ranks, slider mix,
  meaningfulness, persistence, seed idempotency); runtime API
  (no-leak next, step accept/reject/capture/404, authoritative
  attempt score, wrong-path rejection, full speed lifecycle).
- Frontend `PathfindingObstaclesPlay.test.tsx` (20 tests): pure
  helpers (payload, `obstaclePosOf` incl. enemies, centers,
  speed-faster); catalog entries + URLs; practice entry (star +
  enemies + selection + counter); click + persistent selection; touch
  drag; repeated clicks; tap-again; illegal buzz + red flash +
  counters + expiry; arrival payload (no leak) + success + score;
  prefetch advance; speed prepare-20, auto-advance, illegal
  resilience; enemy+star rendering; capture propagation to the next
  step; Persian catalog strings.
- `npm test` (vitest): full suite green. `npm run typecheck` +
  `npm run build` clean. `pytest`: 790 passed.

## Known limitations

- Speed sessions are per-exercise
  (`pathfinding_obstacles_speed_sessions`, mirroring Exercises 1–6);
  a generic session table can replace all seven when the pattern
  stabilises.
- Rating stays a stub: `rating_delta` is always None (practice
  attempts never set it, per AGENTS.md).
- No adaptive difficulty: the 2–10 optimal window plus the
  meaningfulness gate keep a healthy mix, per-player targeting is
  future work.
- Orientation is fixed to White.
- The error/success sounds are minimal synth blips shared with
  Exercise 6.
