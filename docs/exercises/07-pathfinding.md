# Exercise 7 — Pathfinding (مسیریابی)

Production v1 status. The user sees ONE white piece plus a star square on
an otherwise empty board and must walk the piece to the star with legal
chess moves («مهره را با حرکت‌های قانونی به خانه ستاره‌دار برسان»).
Identifier: `pathfinding`.

This is intentionally the SIMPLE pathfinding version:

> One white piece + one star + empty board.

No black pieces, no attacked squares, no captures, no king-safety. Those
belong to **Exercise 8 — Pathfinding with Obstacles**.
Get Out of Check is Exercise 6 and is not part of this exercise.

## Roadmap note (renumbering)

Official roadmap (`docs/EXERCISES.md` is the single source of truth):
Pathfinding is **Exercise 7**, Pathfinding with Obstacles is
**Exercise 8**. Exercises 1–6 are unchanged. Castling Rights is
Exercise 21.

The previous obstacle/enemy-control pathfinding implementation that lived
under the `pathfinding` slug was replaced by this simple version; its
enemy-control concepts (attack maps, capture-to-open-paths) move to
Exercise 7 and were deliberately NOT carried over.

## Board composition

Every puzzle contains exactly:

- one WHITE piece: knight (50%) / bishop (20%) / rook (20%) / queen (10%);
- one star/target square, distinct from the start square;
- nothing else — the board is otherwise empty.

There is NO white king, NO black pieces, NO second white piece, NO pawn,
NO king. The generator enforces all of this before persisting (covered by
tests). Because there is no king, this exercise is about **movement
geometry**, not check or king safety — no artificial king-safety rules
exist anywhere in the implementation.

## Movement rules

Real chess movement for the selected piece, with no blockers (empty
board) and no captures:

- **Knight**: the 8 L-jumps (jumps, nothing blocks);
- **Bishop**: any diagonal distance;
- **Rook**: any horizontal/vertical distance;
- **Queen**: union of rook + bishop.

Movement geometry lives in `pathfinding/moves.py` (pure functions, no
`python-chess`: a kingless board is not a legal chess position, but the
geometry is exactly the piece's real movement). The test suite
cross-checks the whole graph against raw `python-chess` on kingless
boards, so graph bugs are caught by an independent implementation.

## Shortest path (BFS)

Model: `node = square`, `edge = one legal move`. `shortest_path_length`
is BFS over that graph and minimizes the NUMBER OF PIECE MOVES (never the
number of squares traveled). Examples (all asserted in tests):

- rook `a1 → a8` = 1, `a1 → h8` = 2
- bishop `c1 → h6` = 1, `c1 → d4` = 2, opposite-color = unreachable
- queen `a1 → h8` = 1, `a1 → h7` = 2
- knight `a1 → b3` = 1, `a1 → c5` = 2, `a1 → c4` = 3, `a1 → h8` = 6

For every generated puzzle the server computes and stores `optimal_moves`
in the server-only `answer_json`. Multiple equally short routes are all
valid: the server NEVER stores or enforces one specific route — only the
count matters for scoring.

## Generator (`generator.py`)

- Piece choice uses the documented weights (`PIECE_WEIGHTS`) via
  `rng.choices` — the distribution is controlled by the generator, not
  assumed. Finite samples fluctuate; batch-exactness is never required
  (tests assert ±5% over 4000 draws).
- Start/target are uniform random distinct squares; unreachable pairs
  (bishop opposite color) are rejected; every puzzle is verified
  reachable with `optimal_moves >= 1` before persistence.
- Difficulty: uniform sampling already mixes 1-move puzzles (rook/queen
  sharing a line) with natural multi-move knight/bishop tours. To avoid
  floods of trivial one-movers, a 1-move candidate is re-rolled with
  probability 0.6 (bounded retries), keeping 1-, 2-, 3- and longer
  puzzles. No adaptive difficulty yet.
- Persisted row: `fen` (empty board + piece, for rendering),
  `position_json = {from, target, piece}` (public),
  `answer_json = {fen, from, target, piece, optimal_moves}` (server-only).
  Identical `(piece, from, target)` rows are reused, not duplicated;
  `exclude_ids` steers variety with bounded re-rolls.
- Exercise row: title «مسیریابی», `sort_order = 6`.

## Validation (`validator.py`)

`validate(answer, attempt)` with attempt
`{path: [...squares], illegal_attempts: n}`:

- CORRECT iff `path[0]` is the start square, EVERY consecutive step is
  legal geometry for the stored piece, and the path ends exactly on the
  target. Any legal route with the optimal count is optimal.
- WRONG otherwise: incomplete path, illegal step (never skippable),
  wrong start, malformed input, claiming completion from another square.
  No PARTIAL: reaching the star is the submission event.
- `illegal_attempts` is clamped to `>= 0` server-side; client `score` /
  `optimal_moves` / `isCorrect` fields are ignored (covered by tests).

Step oracle (`POST /pathfinding/step`, `apply_step`): pure single-move
legality assistance. Rejects wrong-piece origins, `origin != selected`,
null moves, post-completion moves (`origin == target`), and unknown
puzzles (404). Returns the updated FEN (piece moved server-side from the
submitted FEN) + `reached` flag. Captures never occur (`captured: null`).

## Scoring (authoritative, `scoring.py`)

```text
score = optimal_moves × 5
      − max(0, actual_moves − optimal_moves) × 2
      − illegal_attempts × 3
```

- Registered via `register_scorer("pathfinding", score_path)`.
- Legal moves inside the optimal count are never penalized; each extra
  legal move costs −2 once; each illegal attempt costs −3.
- Spec example: optimal 3, 5 legal moves, 2 illegal → 15 − 4 − 6 = 5
  (asserted in tests, incl. negative-score and exact-boundary cases).
- Negative scores allowed, never clamped (same policy as Exercises 1–5).
- The user may leave the optimal path freely — no restart, just the
  extra-move penalty — until the star is reached.

## User flow

```text
Main Page (/)
   ↓  مسیریابی card
   ├── تمرینی (?mode=practice)      └── سرعتی (?mode=speed)
   ↓                                     ↓
full-viewport game screen           prepare ≥20 puzzles (no clock)
   ↓                                     ↓
first puzzle loads immediately     clock starts → 60s session
   ↓                                     ↓
drag/click step by step → arrival → brief feedback → auto next (speed)
practice: manual «معمای بعدی» → prefetched next → authoritative report
```

- Practice and Speed buttons on the home card directly enter their loops
  (no intermediate screen), same pattern as Exercises 1–5.
- Gameplay runs in the full-viewport overlay (`PieceGameLayout.GameShell`):
  board + question + status + timer always fit without page scrolling
  (portrait stacks, landscape uses the 240px control column).
- Drag-and-drop is primary (grab → drag → release); click-select then
  click-destination works identically, including repeated clicks without
  reselecting. After every successful move the piece REMAINS selected and
  the legal-move counter increments.
- Illegal attempt: short error buzz (`lib/sound.ts`), red destination
  highlight for 700ms, piece stays, −3 state, counter for illegal tries
  increments, piece stays selected. No board mutation, no move counted.
- Completion: the moment the piece reaches the star the client stops
  input and auto-submits `{path, illegal_attempts}` (practice:
  `POST /attempts`; speed: session submit). No Submit button for the path.
- Animation: every legal move glides source→destination (timer-driven
  overlay, no library): 220ms practice, 110ms speed. Input locks during
  the glide so a move is never double-counted; rapid input is ignored
  safely. Mobile touch works through the shared `ChessBoard` gestures.

## Practice Mode

Untimed. First puzzle loads immediately; current+next prefetch buffer
(`POST /pathfinding/next` with `exclude_ids`); «معمای بعدی» swaps
instantly and refills. Retry restarts the current puzzle (path + illegal
counter reset). Anonymous attempts also append to localStorage; the
server is source of truth for accounts.

## Speed Mode

Lifecycle `preparing` → `active` → `finished`/`expired`, mirroring
Exercises 1–5 (`pathfinding_speed_sessions` table, same columns):

1. Enter → session opens in `preparing` (NO clock).
2. Client prepares ≥20 puzzles behind «در حال آماده‌سازی...» (buffer
   counts never shown); `start` requires the full buffer (`409`
   otherwise) — preparation time is never billed.
3. Loop: walk to the star → very brief success pill → AUTOMATIC advance
   (400ms, no manual Next). Single lock from submit through transition;
   timer keeps running; expiry mid-transition routes to the report.
4. Background refill below 12 (+12 batches); exhausted queue falls back
   to single on-demand fetch. Session-loss recovery mirrors Exercises
   1–5 (report attempt, dead screen, 3-skip give-up).
5. Report rebuilt authoritatively from stored attempts (validator
   re-run per attempt; client scores ignored).

## Persian / RTL rendering

Design-system typography (Vazirmatn, `lang="fa"` `dir="rtl"`). Page RTL;
board island `dir="ltr"`, white orientation, a-file left. Star marker is
a gold SVG (55% of the square, pointer-transparent so dragging works),
visible during movement, scales with board size. New strings:
`exercises.pathfinding.title/desc` («مسیریابی»),
`pathfinding.intro/invalid/moves/illegal/arrived/score`.

## Audio

No established sound system existed (`audio/ports.py` is a TTS boundary
only), so the smallest reusable solution was added: `lib/sound.ts`
synthesizes short WebAudio blips (error buzz 180Hz/140ms, success chime
660Hz/110ms) from user-gesture handlers. Lazily creates one shared
`AudioContext`, resumes on suspend (autoplay-safe), never throws, never
blocks gameplay, no dependencies.

## Security

- `answer_json` (incl. `optimal_moves`) never leaves the server —
  including inside prefetch/session buffers (covered by API tests);
  `position_json` carries only `{from, target, piece}`.
- Grading/scoring recompute from the stored answer; client `score` /
  `optimal_moves` / `fen` overrides are ignored (covered by tests).
- Only session-issued puzzles are submittable (404 otherwise); the speed
  clock is server-authoritative (410 on expiry); post-completion steps
  are rejected.

## API

| Method & path | Purpose |
|---|---|
| `POST /api/v1/pathfinding/next` `{exclude_ids?}` | fresh random practice puzzle (`PuzzleOut`, no answer) |
| `POST /api/v1/pathfinding/step` `{puzzle_id, fen, selected_at, from, to}` | single-step legality oracle (`StepOut`: updated FEN, `reached`) |
| `POST /api/v1/pathfinding/sessions` | open session (`preparing`, clock NOT running) |
| `POST /api/v1/pathfinding/sessions/{id}/puzzles` `{count}` | prepare N buffer puzzles (`410` when expired; capped at 60) |
| `POST /api/v1/pathfinding/sessions/{id}/start` | start the 60s clock (`409 buffer_not_ready` below 20) |
| `POST /api/v1/pathfinding/sessions/{id}/next` | single session puzzle |
| `POST /api/v1/pathfinding/sessions/{id}/submit` | graded path + updated summary (`409` before start, `410` when expired) |
| `GET /api/v1/pathfinding/sessions/{id}` | summary (auto-expires) |
| `GET /api/v1/pathfinding/sessions/{id}/report` | authoritative per-puzzle report |
| `POST /api/v1/pathfinding/sessions/{id}/finish` | end early + summary |
| `POST /api/v1/attempts` | standard attempt submit (practice; `{path, illegal_attempts}`) |

Errors: `session_not_found` (404), `session_not_started` (409),
`session_expired` (410), `buffer_not_ready` (409),
`puzzle_not_in_session`/`puzzle_not_available` (404).

## Tests

- Backend `tests/test_pathfinding.py` (75 tests): per-piece movement +
  illegal geometry; hand-derived distances (rook/bishop/queen 1-movers,
  knight 1/2/3/6-movers, bishop unreachable); full-graph equality vs raw
  `python-chess` (4 kinds × 6 squares) + 60 random BFS cross-checks;
  replay semantics (multi-route, suboptimal-valid, incomplete/diverted
  rejected); validation (completion-only, force-completion rejected);
  scoring formula (optimal/extra/illegal/mixed/spec example/negative/
  boundaries); generator (weights ±5%, single clean piece, no
  kings/pawns/black, source≠target, reachable, optimal stored,
  difficulty mix); security (score/optimal/isCorrect ignored, no
  target-skip); seed idempotency; step endpoint (valid/invalid/mismatch/
  post-completion/404/reached flag); attempt API (authoritative score,
  extra+illegal penalty math, no-leak list/detail); practice next +
  full speed lifecycle (20-buffer, 60s, pre-start refusal, speed formula,
  client-score ignored, unknown-session 404, client-FEN ignored).
- Frontend `PathfindingPlay.test.tsx` (17 tests): pure helpers
  (payload clamping, pos, square centers, speed-faster-than-practice);
  catalog practice/speed entries + URLs; direct practice entry (star +
  selection + counter); click move + persistent selection; touch drag;
  repeated clicks; tap-again-keeps-selection; illegal buzz + red flash +
  counters + flash expiry; arrival submit payload (no score/optimal
  leak) + success + score display; practice prefetch advance; speed
  prepare-20-before-clock; speed arrival auto-advance without manual
  Next; speed illegal resilience.
- `npm test` (vitest): 119 passed. `npm run typecheck` + `npm run build`
  clean. `pytest`: 742 passed (Exercises 1–5 untouched and green).

## Known limitations

- Speed sessions are per-exercise (`pathfinding_speed_sessions`,
  mirroring the Exercises 1–5 tables); a generic session table can
  replace all six when the pattern stabilises.
- Rating stays a stub: `rating_delta` is always None (practice attempts
  never set it, per AGENTS.md).
- No adaptive difficulty: the 0.6 trivial-reject keeps a healthy mix,
  but per-player targeting is future work.
- Orientation is fixed to White; the star/board geometry already works
  in both orientations if a future exercise needs Black.
- The error/success sounds are minimal synth blips; a shared
  design-system sound set can replace them later.
