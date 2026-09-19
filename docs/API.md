# API (foundation)

Base URL: `http://localhost:8000`. All module routes under `/api/v1`.

## Health

- `GET /health` → `{"status": "ok"}`

## Auth

- `POST /api/v1/auth/register` `{email, password, display_name?}` → `{access_token, token_type}` (201)
- `POST /api/v1/auth/login` `{email, password}` → `{access_token, token_type}`
- `GET /api/v1/users/me` (Bearer) → `{id, email, display_name, created_at}`
- Errors: `email_taken` (400), `invalid_credentials` (401), `auth_required` (401)

## Exercises

- `GET /api/v1/exercises` → `[{slug, title_fa, title_en, description, is_active}]` (active only)

## Puzzles (read-only for MVP)

- `GET /api/v1/puzzles?exercise=<slug>` → published + non-archived puzzles
- Response omits `answer_json` (backend authoritative). Admin authoring comes later.
- `GET /api/v1/puzzles/{id}` → single puzzle (education stays accessible later); 404 `puzzle_not_available`

Example:

```json
[
  {
    "id": 1,
    "exercise_slug": "piece-recognition",
    "fen": null,
    "position_json": {},
    "hint_json": {},
    "initial_rating": 1200.0,
    "is_published": true,
    "is_archived": false,
    "published_at": "2026-01-01T00:00:00"
  }
]
```

## Attempts

- `POST /api/v1/attempts`
  - Auth: required for all modes (`auth_required` 401 for guest/anonymous).
    Guest practice is disabled: only authenticated accounts hold
    `attempts.submit`, so guests create no attempts and no evidence.
    Historical guest rows are preserved and migratable. Speed
    `.../sessions/{id}/submit` endpoints require the same capability.
  - Body: `{puzzle_id, answer: {selected_squares: []}, mode, client_result?, hints_used?: [], started_at?}`
  - `client_result` short-circuits validation for terminal states; otherwise the exercise validator runs.
  - Response: `{id, puzzle_id, exercise_slug, mode, result, score, feedback_key, rating_delta, detail, hints_used, started_at, duration_ms, created_at}`
  - `detail` is `{correct: [], missed: [], wrong: []}` for piece-recognition.
  - `score` is authoritative and backend-computed (per-square 5/−1/−2 for
    piece-recognition, legal-destinations, captures, and undefended-pieces,
    per-move 5/−1/−2 for giving-check, per-move 5/−2/−3 for get-out-of-check,
    via their registered scorers,
    else correct=1.0/partial=0.5/0); never
    trusted from the client; may be negative.
  - `result` in correct/partial/wrong/timeout/skipped/abandoned.
  - `rating_delta` is set for rated attempts (interim Elo-style update); practice attempts never set it (`null`). Numeric ratings stay hidden from players; only rated-game counts are shown.
  - Errors: `puzzle_not_available` (404 for missing/unpublished/archived).

## Piece Recognition (Exercise 1)

Lifecycle: open (`preparing`, no clock) → prepare ≥20 → start (60s clock)
→ submit loop → finish/report.

- `POST /api/v1/piece-recognition/next` `{exclude_ids?: []}` → fresh random
  practice `PuzzleOut` (published row, no `answer_json`; identical rows reused).
- `POST /api/v1/piece-recognition/sessions` `{duration_s?}` (default 60) →
  `{session_id, exercise_slug, status: "preparing", duration_s, started_at,
  expires_at: null, remaining_ms, buffered}`.
- `POST /api/v1/piece-recognition/sessions/{id}/puzzles` `{count}` (default 20,
  cap 60) → `PuzzleOut[]` for the buffer/refill; `410 session_expired` after expiry.
- `POST /api/v1/piece-recognition/sessions/{id}/start` → active session with
  running clock; `409 buffer_not_ready` below 20 buffered puzzles.
- `POST /api/v1/piece-recognition/sessions/{id}/next` → single session `PuzzleOut`.
- `POST /api/v1/piece-recognition/sessions/{id}/submit`
  `{puzzle_id, answer: {selected_squares: []}, hints_used?: [], started_at?}` →
  `{attempt: AttemptOut, feedback_key, detail, session: summary}`.
  Only puzzles issued to the session are accepted (404 otherwise);
  client-supplied FEN/target/solution/score fields are ignored;
  `409 session_not_started` before the clock starts.
- `GET /api/v1/piece-recognition/sessions/{id}` → summary
  `{session_id, status, duration_s, started_at, expires_at, remaining_ms,
  buffered, attempted, correct, partial, wrong, score}` (auto-expires).
- `GET /api/v1/piece-recognition/sessions/{id}/report` → `{session, entries[]}`
  rebuilt from stored attempts: per-puzzle prompt/result/score/correct/missed/wrong.
- `POST /api/v1/piece-recognition/sessions/{id}/finish` → final summary.
- Errors: `session_not_found` (404), `session_not_started` (409),
  `session_expired` (410), `buffer_not_ready` (409),
  `puzzle_not_in_session`/`puzzle_not_available` (404).

## Legal Destinations (Exercise 2)

Same lifecycle and contract as Exercise 1 (open → prepare ≥20 → start
60s clock → submit loop → finish/report), under `/api/v1/legal-destinations`:

- `POST /api/v1/legal-destinations/next` `{exclude_ids?: []}` → fresh
  random white-only practice `PuzzleOut` (no `answer_json`; the target
  square in `position_json.from` is public task data, destinations are not).
- `POST /api/v1/legal-destinations/sessions` → `preparing` session (60s default).
- `POST /api/v1/legal-destinations/sessions/{id}/puzzles` `{count}` →
  buffer/refill puzzles (cap 60); `POST .../start` requires ≥20.
- `POST /api/v1/legal-destinations/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}`; per-square 5/−1/−2 scoring
  with the +5 zero-target bonus; only session-issued puzzles accepted.
- `GET .../sessions/{id}` → summary; `GET .../report` → authoritative
  per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.
- Full spec: `docs/exercises/02-legal-destinations.md`.

## Captures (Exercise 3)

Same lifecycle and contract as Exercises 1–2 (open → prepare ≥20 → start
60s clock → submit loop → finish/report), under `/api/v1/captures`:

- `POST /api/v1/captures/next` `{exclude_ids?: []}` → fresh random
  hunter-vs-black practice `PuzzleOut` (no `answer_json`; the hunter
  square in `position_json.from` is public task data, capturable squares
  are not).
- `POST /api/v1/captures/sessions` → `preparing` session (60s default).
- `POST /api/v1/captures/sessions/{id}/puzzles` `{count}` →
  buffer/refill puzzles (cap 60); `POST .../start` requires ≥20.
- `POST /api/v1/captures/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}`; per-square 5/−1/−2 scoring
  with the +5 zero-target bonus; only session-issued puzzles accepted.
  Defense never matters: answers use the `ignore-enemy-attacks` profile.
- `GET .../sessions/{id}` → summary; `GET .../report` → authoritative
  per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.
- Full spec: `docs/exercises/03-captures.md`.

## Undefended Pieces (Exercise 4)

Same lifecycle and contract as Exercises 1–3 (open → prepare ≥20 → start
60s clock → submit loop → finish/report), under
`/api/v1/undefended-pieces`:

- `POST /api/v1/undefended-pieces/next` `{exclude_ids?: []}` → fresh
  random shared-position practice `PuzzleOut` (no `answer_json`; only
  FEN is used from `puzzles.db`, Moves/Rating/Themes ignored).
- `POST /api/v1/undefended-pieces/sessions` → `preparing` session (60s default).
- `POST /api/v1/undefended-pieces/sessions/{id}/puzzles` `{count}` →
  buffer/refill puzzles (cap 60); `POST .../start` requires ≥20.
- `POST /api/v1/undefended-pieces/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}`; per-square 5/−1/−2 scoring
  with the +5 zero-target bonus; only session-issued puzzles accepted.
  Undefended = attacked by ≥1 valid enemy AND defended by 0 valid
  friendlies; absolutely pinned pieces never count; kings never answers.
- `GET .../sessions/{id}` → summary; `GET .../report` → authoritative
  per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.
- Full spec: `docs/exercises/04-undefended-pieces.md`.

## Giving Check (Exercise 5)

Same lifecycle and contract as Exercises 1–4 (open → prepare ≥20 → start
60s clock → submit loop → finish/report), under `/api/v1/giving-check`:

- `POST /api/v1/giving-check/next` `{exclude_ids?: []}` → fresh
  random shared-position practice `PuzzleOut` (no `answer_json`; only
  FEN is used from `puzzles.db`, Moves/Rating/Themes ignored;
  positions with either king already in check are never issued).
- `POST /api/v1/giving-check/sessions` → `preparing` session (60s default).
- `POST /api/v1/giving-check/sessions/{id}/puzzles` `{count}` →
  buffer/refill puzzles (cap 60); `POST .../start` requires ≥20.
- `POST /api/v1/giving-check/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}` with
  `answer: {moves: [{from, to, promotion?}]}` (plain UCI strings also
  accepted; direction matters; duplicates normalized); per-move
  5/−1/−2 scoring with the +5 zero-target bonus; only session-issued
  puzzles accepted. Correct = every legal non-King move (UCI) that
  leaves the opponent king in check, for White AND Black regardless of
  the FEN's side to move (direct/capture/discovered/double/
  promotion/en-passant; kings and castling never answers).
- `GET .../sessions/{id}` → summary; `GET .../report` → authoritative
  per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.
- Full spec: `docs/exercises/05-giving-check.md`.

## Get Out of Check (Exercise 6)

Same lifecycle and contract as Exercises 1–5 (open → prepare ≥20 → start
60s clock → submit loop → finish/report), under `/api/v1/get-out-of-check`:

- `POST /api/v1/get-out-of-check/next` `{exclude_ids?: []}` → fresh
  random synthetic practice `PuzzleOut` (no `answer_json`; only
  the FEN is exposed for rendering, the escape set never is; White to
  move is always in check and never checkmated).
- `POST /api/v1/get-out-of-check/sessions` → `preparing` session (60s default).
- `POST /api/v1/get-out-of-check/sessions/{id}/puzzles` `{count}` →
  buffer/refill puzzles (cap 60); `POST .../start` requires ≥20.
- `POST /api/v1/get-out-of-check/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}` with
  `answer: {moves: [{from, to, promotion?}]}` (plain UCI strings also
  accepted; direction matters; duplicates normalized); per-move
  5/−2/−3 scoring (no zero-target bonus: every valid puzzle has ≥1
  escape); only session-issued puzzles accepted. Correct = every legal
  White move (UCI) after which White's own king is safe (capture /
  block / king escape; double checks accept king moves only).
- `GET .../sessions/{id}` → summary; `GET .../report` → authoritative
  per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.

## Pathfinding (Exercise 7)

Same lifecycle and contract as Exercises 1–5 (open → prepare ≥20 → start
60s clock → submit loop → finish/report), under `/api/v1/pathfinding`:

- `POST /api/v1/pathfinding/next` `{exclude_ids?: []}` → fresh
  random single-piece practice `PuzzleOut` (no `answer_json`; the
  start/target/piece in `position_json` is public task data, the BFS
  optimal count is not).
- `POST /api/v1/pathfinding/step`
  `{puzzle_id, fen, selected_at, from, to}` → legality oracle
  `{ok, fen, selected_at, reached, captured: null, message_key}`;
  rejects wrong-piece origins, `from != selected_at` mismatches,
  illegal geometry, post-completion moves, and unknown puzzles (404
  `puzzle_not_available`).
- `POST /api/v1/pathfinding/sessions` → `preparing` session (60s default).
- `POST /api/v1/pathfinding/sessions/{id}/puzzles` `{count}` →
  buffer/refill puzzles (cap 60); `POST .../start` requires ≥20.
- `POST /api/v1/pathfinding/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}` with
  `answer: {path: [...squares], illegal_attempts: n}`;
  `optimal×5 − extra×2 − illegal×3` scoring; only session-issued
  puzzles accepted; client score/optimal fields ignored.
- `GET .../sessions/{id}` → summary; `GET .../report` → authoritative
  per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.
- Full spec: `docs/exercises/07-pathfinding.md`.

## Pathfinding with Obstacles (Exercise 8)

Same lifecycle and contract as Exercise 7 (open → prepare ≥20 → start
60s clock → submit loop → finish/report), under
`/api/v1/pathfinding-obstacles`:

- `POST /api/v1/pathfinding-obstacles/next` `{exclude_ids?: []}` →
  fresh random solved practice `PuzzleOut` (no `answer_json`; the
  start/target/piece in `position_json` is public task data, the
  state-space BFS optimal count is not).
- `POST /api/v1/pathfinding-obstacles/step`
  `{puzzle_id, fen, selected_at, from, to}` → legality oracle
  `{ok, fen, selected_at, reached, captured, message_key}`;
  rebuilds the live board state from the client FEN with the
  server-stored kind/target (movement + blocking + destination
  safety + undefended-only captures); rejects post-completion moves
  and unknown puzzles (404 `puzzle_not_available`).
- `POST /api/v1/pathfinding-obstacles/sessions` → `preparing`
  session (60s default).
- `POST /api/v1/pathfinding-obstacles/sessions/{id}/puzzles`
  `{count}` → buffer/refill puzzles (cap 60);
  `POST .../start` requires ≥20.
- `POST /api/v1/pathfinding-obstacles/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}` with
  `answer: {path: [...squares], illegal_attempts: n}`;
  `optimal×5 − extra×2 − illegal×3` scoring; only session-issued
  puzzles accepted; client score/optimal fields ignored.
- `GET .../sessions/{id}` → summary; `GET .../report` →
  authoritative per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.
  - Full spec: `docs/exercises/08-pathfinding-obstacles.md`.

## Balance Scale (Exercise 9)

Same lifecycle and contract as Exercises 1–7 (open → prepare ≥20 → start
60s clock → submit loop → finish/report), under `/api/v1/balance-scale`:

- `POST /api/v1/balance-scale/next` `{exclude_ids?: []}` → fresh
  random practice `PuzzleOut` (no `answer_json`; only the black left
  pieces in `position_json.left` are public task data, the target and
  optimal count are not).
- `POST /api/v1/balance-scale/sessions` → `preparing` session (60s default).
- `POST /api/v1/balance-scale/sessions/{id}/puzzles` `{count}` →
  buffer/refill puzzles (cap 60); `POST .../start` requires ≥20.
- `POST /api/v1/balance-scale/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}` with
  `answer: {pieces: [...]}` (the placed white pieces);
  `max(0, 10 − extra)` scoring where extra = used − server-side optimal;
  only session-issued puzzles accepted; client score/optimal/target
  fields ignored. No Submit button exists client-side: exact balance
  auto-submits; practice waits for «معمای بعدی», speed auto-advances.
- `GET .../sessions/{id}` → summary; `GET .../report` → authoritative
  per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.
  - Full spec: `docs/exercises/09-balance-scale.md`.

## Heavier Side (Exercise 10)

Same lifecycle and contract as Exercises 1–7 and 10 (open → prepare ≥20
→ start 60s clock → submit loop → finish/report), under
`/api/v1/heavier-side`:

- `POST /api/v1/heavier-side/next` `{exclude_ids?: []}` → fresh random
  10%-eligible shared-position practice `PuzzleOut` (no `answer_json`;
  only the FEN in `position_json.fen` is public task data, the material
  verdict is not).
- `POST /api/v1/heavier-side/sessions` → `preparing` session (60s default).
- `POST /api/v1/heavier-side/sessions/{id}/puzzles` `{count}` →
  buffer/refill puzzles (cap 60); `POST .../start` requires ≥20.
- `POST /api/v1/heavier-side/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}` with
  `answer: {choice: "white" | "black" | "equal"}`; +5/−2 scoring;
  only session-issued puzzles accepted; client totals/scores ignored.
  No Submit button exists client-side: tapping a choice submits;
  practice auto-advances after ~1500ms, speed after ~450ms.
- `GET .../sessions/{id}` → summary; `GET .../report` → authoritative
  per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.
  - Full spec: `docs/exercises/10-heavier-side.md`.

## Memorization Board (Exercise 12, صفحه‌ی حفظی)

Same lifecycle and contract as Exercises 1–7, 10, and 11 (open → prepare
≥20 → start 60s clock → submit loop → finish/report), under
`/api/v1/chinese-board`:

- `POST /api/v1/chinese-board/next` `{exclude_ids?: []}` → fresh random
  real-position practice `PuzzleOut` (no `answer_json`; the FEN in
  `position_json.fen` is the board shown during memorization, plus the
  server-computed `piece_count` and `memorization_ms = piece_count × 1000`;
  the piece set verdict is not).
- `POST /api/v1/chinese-board/sessions` → `preparing` session (60s default).
- `POST /api/v1/chinese-board/sessions/{id}/puzzles` `{count}` →
  buffer/refill puzzles (cap 60); `POST .../start` requires ≥20.
- `POST /api/v1/chinese-board/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}` with
  `answer: {pieces: [{square, piece, color}]}` (free placement; only
  `pieces` is read, client score/count/FEN fields ignored);
  `5×correct − 2×(wrong+missing)` scoring with no floor (negatives kept;
  a wrong-square original is one error, never double-counted); only
  session-issued puzzles accepted. Practice submits through standard
  `POST /api/v1/attempts` and advances manually; speed auto-advances
  after ~600ms feedback.
- `GET .../sessions/{id}` → summary; `GET .../report` → authoritative
  per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.
  - Full spec: `docs/exercises/12-memorization-board.md`.

## Pin (Exercise 11)

No dedicated router and no speed sessions. Puzzles are served
through `GET /api/v1/puzzles?exercise=pin` and answered through
standard `POST /api/v1/attempts` with
`answer: {squares: [<pinner>, <pinned>, <behind>]}` (the three
pieces forming the pin, in order; `selected_squares` accepted as
an alias). CORRECT only for the exact ordered triplet recomputed
from the stored FEN (absolute when behind is the King, relative
only when behind is strictly more valuable); CORRECT or WRONG
only. Scoring is the shared default (correct=1.0, else 0).

## Is it Checkmate? (Exercise 13)

No dedicated router and no speed sessions. Puzzles are served
through `GET /api/v1/puzzles?exercise=is-checkmate` and answered
through standard `POST /api/v1/attempts` with
`answer: {choice: "checkmate" | "check" | "not_check"}`, matched
against the state derived from the stored FEN
(checkmate = in check with no legal moves; stalemate classifies as
`not_check`). CORRECT or WRONG only; shared default scoring.

## Blindfold Square Vision (Exercise 14)

Same lifecycle and contract as Exercises 1–7 (open → prepare ≥20
→ start 60s clock → submit loop → finish/report), under
`/api/v1/blindfold-square-vision`:

- `POST /api/v1/blindfold-square-vision/next`
  `{exclude_ids?: []}` → fresh random practice `PuzzleOut`
  (no `answer_json`; `position_json` carries only the square —
  the public question; square colors are never stored, `a1` is dark).
- Practice submits `{square}` (tap the asked square);
  speed submits `{choice: "white" | "black"}` (no board shown).
  Registered scorer: CORRECT +5 / WRONG −3, negatives kept.
- `POST .../sessions` → `preparing` (60s default);
  `POST .../sessions/{id}/puzzles` `{count}` → buffer (cap 60);
  `POST .../start` requires ≥20; submit → `{attempt,
  feedback_key, detail, session}`; summary/report/finish as usual.
  Same error codes as Exercise 1.

## Blindfold Calculation (Exercise 15)

Same lifecycle and contract as Exercises 1–7 (open → prepare ≥20
→ start 60s clock → submit loop → finish/report), under
`/api/v1/blindfold-calculation`:

- `POST /api/v1/blindfold-calculation/next`
  `{exclude_ids?: []}` → fresh random ≤12-piece practice `PuzzleOut`
  (no `answer_json`; `Puzzle.fen` stays NULL — the position is
  conveyed only as a server-generated structured Persian
  description; the stored Lichess solution's first UCI is the
  single authoritative answer).
- Submit `answer: {move: "<SAN>"}` (parsed with `board.parse_san`
  against the stored FEN, normalized to UCI; `+`/`#` suffixes and
  whitespace tolerated). CORRECT or WRONG only; shared default
  scoring; practice attempts never set `rating_delta`.
- Sessions (`POST .../sessions`, `/puzzles`, `/start`, `/submit`,
  summary/report/finish) mirror the shared lifecycle; same error
  codes as Exercise 1.

## Mental Opening (Exercise 16)

No dedicated router and no speed sessions. Puzzles are served
through `GET /api/v1/puzzles?exercise=opening-traps` and answered
through standard `POST /api/v1/attempts` with
`answer: {move: "<SAN>"}` (parsed with `board.parse_san`;
malformed, illegal, and ambiguous input is WRONG). CORRECT when
the normalized UCI belongs to the puzzle's explicit solution set
(one tactical move from a genuine opening-trap position;
checkmate is not required). CORRECT or WRONG only; shared default
scoring. `Puzzle.fen` stays NULL — FEN + solution UCIs live in
server-only `answer_json`.

## Reverse Opening (Exercise 17)

Step oracle plus standard attempts; no `/next`, no speed sessions:

- `POST /api/v1/reverse-opening/step` — legality-only move
  assistance: replays the claimed history from the stored start,
  applies one legal move, returns the new FEN plus server-generated
  SAN and an on-track flag; reveals no solution data.
- Final grading revalidates the whole sequence through standard
  `POST /api/v1/attempts` with `answer: {moves: [...]}` (UCIs
  replayed with python-chess from the stored start; CORRECT only
  when placement + side to move + castling rights + en-passant
  square equal the stored target, so transpositions are accepted).
  CORRECT or WRONG only; shared default scoring.

## Trapped Piece (Exercise 18)

Same lifecycle and contract as Exercises 1–7 (open → prepare ≥20
→ start 60s clock → submit loop → finish/report), under
`/api/v1/trapped-pieces`:

- `POST /api/v1/trapped-pieces/next` `{exclude_ids?: []}` →
  fresh random practice `PuzzleOut` (no `answer_json`; practice
  holds 1–3 trapped pieces, speed buffers hold exactly-one
  positions for tap-to-submit grading).
- Submit `answer: {selected_squares: [...]}` (exact set match;
  malformed squares count as wrong; client FEN/answer/score
  ignored). A non-pawn piece (King included, either color) is
  trapped iff it has zero SAFE destinations (post-move Static
  Exchange Evaluation ≥ 0). Registered per-square scorer:
  +5 correct / −2 missed / −2 wrong, negatives kept (+5 bonus for
  correctly answered zero-target legacy rows).
- Sessions (`POST .../sessions`, `/puzzles`, `/start`, `/submit`,
  summary/report/finish) mirror the shared lifecycle; same error
  codes as Exercise 1.

## Castling Rights (Exercise 21)

No dedicated router and no speed sessions. Puzzles are served
through `GET /api/v1/puzzles?exercise=castling-rights` and answered
through standard `POST /api/v1/attempts` with
`answer: {options: [...]}` (each option must appear in that
color's python-chess legal moves on a turn-flipped board, with
explicit king/rook presence guards). Shared default scoring.
