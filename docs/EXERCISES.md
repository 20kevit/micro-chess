# Exercises (catalog of future work)

No exercise is implemented in the foundation. Each gets its own spec from the user
before implementation. New exercise = catalog row + validator + tests + UI.

Roadmap (final numbering; Exercises 1–6 are production vertical slices):

1. Piece Recognition (`piece-recognition`)
2. Legal Destinations (`legal-destinations`)
3. Captures (`captures`)
4. Undefended Pieces (`undefended-pieces`)
5. Giving Check (`give-check`)
6. Pathfinding (`pathfinding`)
7. Pathfinding with Obstacles (`pathfinding-obstacles`)
8. Pin (`pin`)
9. Balance Scale (`balance-scale`)
10. Which Side is Heavier? (`heavier-side`)
11. Is it Checkmate? (`is-checkmate`)
12. Memory Board (`memory-board`)
13. Blindfold Square Vision (`blindfold-square-vision`)
14. Blindfold Calculation (`blindfold-calculation`)
15. Opening Traps Blindfold (`opening-traps`)
16. Opening Move Reconstruction (`opening-move-reconstruction`)
17. Trapped Pieces (`trapped-pieces`)
18. Rule of the Square (`rule-of-the-square`)
19. Castling Rights (`castling-rights`, moved to the end of the roadmap)

Get Out of Check (`get-out-of-check`) is postponed: the implementation
remains in the repo and playable, but it holds no numbered roadmap slot
until it returns to active development.

Coming soon (no number yet): Reverse Opening, Avoid Stalemate.

Removed (no placeholders left): the former Exercises 5 (Hanging
Pieces, `hanging-pieces`) and 6 (Equal Attackers & Defenders,
`equal-attackers-defenders`) were deleted from the project — backend
modules, frontend pages, routes, catalog entries, tests, and docs.
Everything after them moved two numbers back.

## How to add an exercise (later)

1. Add `Exercise` row (slug, Persian title, description).
2. Write validator `(puzzle_answer, attempt) -> ValidationResult` in the exercise's module.
3. `register_validator(slug, fn)` at startup.
4. Add backend tests (validation, scoring edge cases, custom rules).
5. Add frontend page + Persian strings; call `POST /api/v1/attempts`; render `feedback_key` via `t()`.

## First slice

**Piece Recognition** — MVP (`piece-recognition`). Full spec:
`docs/exercises/01-piece-recognition.md`.

- Route: `/exercises/piece-recognition` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons.
- Play loop: `frontend/src/components/exercise/PieceRecognitionPlay.tsx`
  (practice + speed, timer, hints, feedback legend); correctness, scoring,
  and the speed clock stay backend-authoritative.
- Position source: shared `puzzles.db` via `positions/repository.py`
  (read-only, FEN only, fallback FENs when absent); per-puzzle questions
  built by `piece_recognition/generator.py` (12 canonical color×kind
  targets, zero-target questions valid, answers server-side only).
- Validator: `backend/app/modules/piece_recognition/validator.py` (exact
  set match incl. empty==empty; malformed squares count as wrong).
- Practice: `POST /api/v1/piece-recognition/next` issues fresh random
  published puzzles (identical rows reused; `exclude_ids` steers variety);
  the client keeps a current+next prefetch buffer. Answers go through
  standard `POST /api/v1/attempts`.
- Speed: `piece_recognition/sessions.py` + `router.py` (open → prepare ≥20
  → start 60s clock → submit loop with ~450ms auto-advance, no manual next
  → server-rebuilt per-puzzle report; per-answer rows reuse `attempts`).
- Scoring: registered per-square scorer (+5 correct / −1 missed / −2 wrong,
  +5 bonus for correctly answered zero-target, negatives kept, independent
  of the CORRECT/PARTIAL/WRONG label).
- Seed: `python -m app.modules.piece_recognition.seed` (15 legacy demo
  puzzles, still served read-only; covered by tests).

## Second slice

**Legal Destinations** — IMPLEMENTED (`legal-destinations`). Full spec:
`docs/exercises/02-legal-destinations.md`.

- Route: `/exercises/legal-destinations` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons directly
  (no intermediate mode screen), same pattern as Exercise 1.
- Play loop: `frontend/src/components/exercise/LegalDestinationsPlay.tsx`
  (practice + speed reusing `PieceGameLayout` shell, timer, hints, feedback;
  target piece highlighted via the shared `target` board state, destinations
  server-authoritative); correctness, scoring, and the speed clock stay
  backend-authoritative.
- Position source: dynamic white-only generator
  (`legal_destinations/generator.py` — uniform target type, exactly one
  white king, 2–6 deliberately placed blockers, no black pieces/king,
  zero-target possible but throttled, answers server-side only).
- Validator: `backend/app/modules/legal_destinations/validator.py` (exact
  set match incl. empty==empty; duplicates/order-insensitive; malformed
  squares count as wrong). Rule profiles are data (`RULE_PROFILES`:
  `standard` via `legal_moves`, `ignore-enemy-attacks` via
  `pseudo_legal_moves`); generated positions use `ignore-enemy-attacks`.
- Practice: `POST /api/v1/legal-destinations/next` issues fresh random
  published puzzles (identical rows reused; `exclude_ids` steers variety);
  the client keeps a current+next prefetch buffer. Answers go through
  standard `POST /api/v1/attempts`.
- Speed: `legal_destinations/sessions.py` + `router.py` (open → prepare ≥20
  → start 60s clock → submit loop with ~450ms auto-advance, no manual next
  → server-rebuilt per-puzzle report; per-answer rows reuse `attempts`).
- Scoring: registered per-square scorer (+5 correct / −1 missed / −2 wrong,
  +5 bonus for correctly answered zero-target, negatives kept, independent
  of the CORRECT/PARTIAL/WRONG label).
- Seed: `python -m app.modules.legal_destinations.seed` (15 legacy demo
  puzzles incl. captures/black pieces/both profiles, still served
  read-only; covered by tests).

## Third slice

**Captures** — IMPLEMENTED (`captures`). Full spec:
`docs/exercises/03-captures.md`.

- Route: `/exercises/captures` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons directly
  (no intermediate mode screen), same pattern as Exercises 1–2.
- Play loop: `frontend/src/components/exercise/CapturesPlay.tsx`
  (practice + speed reusing `PieceGameLayout` shell, timer, hints, feedback;
  hunter highlighted via the shared `target` board state, capturable
  squares server-authoritative); correctness, scoring, and the speed clock
  stay backend-authoritative.
- Position source: dynamic hunter-vs-black generator
  (`captures/generator.py` — uniform hunter type, exactly one white
  hunter, 3–8 black pieces with deliberate capturable/shielded/decoy
  patterns, no kings, zero-capture throttled, answers server-side only).
- Defense is explicitly irrelevant: answers use the
  `ignore-enemy-attacks` profile (pseudo-legal captures), so defended
  black pieces stay correct. There are no king hunters (a king cannot
  capture a defended piece); hunter kinds are pawn/knight/bishop/
  rook/queen.
- Validator: `backend/app/modules/captures/validator.py` (exact set
  match incl. empty==empty; duplicates/order-insensitive; malformed
  squares count as wrong). Rule profiles are data (`RULE_PROFILES`:
  `standard` via `legal_moves`, `ignore-enemy-attacks` via
  `pseudo_legal_moves`); generated positions use `ignore-enemy-attacks`,
  legacy seed rows keep `standard`.
- Practice: `POST /api/v1/captures/next` issues fresh random published
  puzzles (identical rows reused; `exclude_ids` steers variety); the
  client keeps a current+next prefetch buffer. Answers go through
  standard `POST /api/v1/attempts`.
- Speed: `captures/sessions.py` + `router.py` (open → prepare ≥20 →
  start 60s clock → submit loop with ~450ms auto-advance, no manual next
  → server-rebuilt per-puzzle report; per-answer rows reuse `attempts`).
- Scoring: registered per-square scorer (+5 correct / −1 missed / −2 wrong,
  +5 bonus for correctly answered zero-target, negatives kept, independent
  of the CORRECT/PARTIAL/WRONG label).
- Seed: `python -m app.modules.captures.seed` (15 legacy demo puzzles,
  still served read-only; covered by tests).

## Removed slices (no placeholders)

**Hanging Pieces** (`hanging-pieces`, former Exercise 5) and **Equal
Attackers & Defenders** (`equal-attackers-defenders`, former Exercise 6)
were completely removed: backend modules, frontend pages, routes,
catalog entries, tests, and docs. Everything below moved two numbers
back; Exercises 1–4 are untouched.

## Fifth slice

**Giving Check** — IMPLEMENTED (`give-check`). Full spec:
`docs/exercises/05-giving-check.md`.

- Route: `/exercises/give-check` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons
  directly (no intermediate mode screen), same pattern as Exercises 1–4.
- Play loop: `frontend/src/components/exercise/GivingCheckPlay.tsx`
  (practice + speed reusing the `PieceGameLayout` shell, timer, hints,
  feedback; multi-arrow board layer in `components/chess/ChessBoard.tsx`
  with press-drag-release drawing, per-arrow remove/promotion, toned
  feedback arrows); correctness, scoring, and the speed clock stay
  backend-authoritative.
- Position source: shared `puzzles.db` via `positions/repository.py`
  (read-only, FEN only, fallback FENs when absent), exactly like
  Exercise 4; per-puzzle answers built server-side by
  `give_check/generator.py` (bounded 25-candidate sampling that rejects
  positions with either king in check and prefers non-empty answers
  while keeping zero-target valid, answers server-side only).
- Rule: every legal non-King move (UCI) that leaves the opponent king
  in check, evaluated for White AND Black regardless of side to move —
  direct, capture, discovered (moving piece's from→to),
  double (one arrow), promotion (distinct choices), en passant;
  kings/castling never answers.
- Validator: `backend/app/modules/give_check/validator.py` (exact UCI
  set match incl. empty==empty; direction-sensitive,
  duplicates/order-insensitive; malformed arrows count as wrong).
- Practice: `POST /api/v1/giving-check/next` issues fresh random
  published puzzles (identical FEN rows reused; `exclude_ids` steers
  variety); the client keeps a current+next prefetch buffer. Answers go
  through standard `POST /api/v1/attempts`.
- Speed: `give_check/sessions.py` + `router.py` (open → prepare ≥20 →
  start 60s clock → submit loop with ~450ms auto-advance, no manual next
  → server-rebuilt per-puzzle report; per-answer rows reuse `attempts`).
- Scoring: registered per-move scorer (+5 correct / −1 missed / −2 wrong,
  +5 bonus for correctly answered zero-target, negatives kept, independent
  of the CORRECT/PARTIAL/WRONG label).

## Sixth slice

**Get Out of Check** — IMPLEMENTED (`get-out-of-check`), currently
POSTPONED (no numbered roadmap slot; route stays playable).

- Route: `/exercises/get-out-of-check` (shared `ExercisePlay` move-input loop
  in drag-only mode: arrows stay off, from/to rings carry the selection).
- Validator: `backend/app/modules/get_out_of_check/validator.py` (position
  must start in check; any legal python-chess move leaving the mover's own
  king safe, tested via `is_attacked_by` after the push; FEN travels in the
  server-only `answer_json`, never exposed).
- Seed: `python -m app.modules.get_out_of_check.seed` (15 hand-designed
  puzzles covering king escapes, captures, blocks, knight/pawn checks,
  doubles, pinned and discovered-fail cases, single/multi answers and a
  black-to-move position; every example independently verified at seed time).

## Seventh slice (Exercise 6 spec-track)

**Pathfinding** — IMPLEMENTED (`pathfinding`, simple version). Full spec:
`docs/exercises/06-pathfinding.md`.

- Route: `/exercises/pathfinding` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons directly
  (no intermediate mode screen), same pattern as Exercises 1–5.
- Play loop: `frontend/src/components/exercise/PathfindingPlay.tsx`
  (practice + speed reusing the `PieceGameLayout` shell, timer, hints,
  feedback; one white knight/bishop/rook/queen walks to a star on an
  empty board — no king, no enemies, no captures; drag primary,
  click-to-move supported, piece stays selected, 220ms practice /
  110ms speed glide, illegal buzz + 700ms red flash; arrival
  auto-submits `{path, illegal_attempts}`); correctness, optimal counts,
  scoring, and the speed clock stay backend-authoritative.
- Position source: dynamic weighted generator
  (`pathfinding/generator.py` — knight 50 / bishop 20 / rook 20 /
  queen 10, uniform distinct start/target, BFS-verified reachable with
  stored `optimal_moves`, trivial-1-move throttled, answers server-side
  only). Movement geometry is pure (`moves.py`); BFS minimizes piece
  moves; no route is ever enforced.
- Validator: `backend/app/modules/pathfinding/validator.py` (exact
  path replay: correct iff every step is legal geometry AND the path
  ends on the star; single-step oracle at `POST /api/v1/pathfinding/step`
  with post-completion rejection).
- Practice: `POST /api/v1/pathfinding/next` issues fresh random
  published puzzles (identical rows reused; `exclude_ids` steers variety);
  the client keeps a current+next prefetch buffer. Answers go through
  standard `POST /api/v1/attempts`.
- Speed: `pathfinding/sessions.py` + `router.py` (open → prepare ≥20 →
  start 60s clock → walk-to-star loop with ~400ms auto-advance, no manual
  next → server-rebuilt per-puzzle report; per-answer rows reuse
  `attempts`).
- Scoring: registered scorer (`optimal×5 − extra×2 − illegal×3`,
  negatives kept, independent of the CORRECT/WRONG label).
- Seed: `python -m app.modules.pathfinding.seed` (15 weighted puzzles
  from the generator with a fixed seed, still served read-only).
- Note: the older obstacle/enemy-control pathfinding behavior that
  previously lived under this slug was replaced by this simple version;
  obstacle concepts move to future Exercise 7 and were not carried over.

## Eighth slice (Exercise 7 spec-track)

**Pathfinding with Obstacles** — IMPLEMENTED (`pathfinding-obstacles`,
obstacle/enemy-piece pathfinding). Full spec:
`docs/exercises/07-pathfinding-obstacles.md`.

- Route: `/exercises/pathfinding-obstacles` with `?mode=practice`
  (untimed) and `?mode=speed` (60s session); card renders both entry
  buttons directly (no intermediate mode screen), same pattern as
  Exercises 1–6.
- Play loop: `frontend/src/components/exercise/PathfindingObstaclesPlay.tsx`
  (practice + speed reusing the `PieceGameLayout` shell, timer, hints,
  feedback; one white knight/bishop/rook/queen walks to a star among
  1–5 black enemies — no kings at all; drag primary, click-to-move
  supported, piece stays selected, 220ms practice / 110ms speed glide,
  illegal buzz + 700ms red flash; arrival auto-submits
  `{path, illegal_attempts}`); correctness, optimal counts, scoring,
  and the speed clock stay backend-authoritative.
- Position source: dynamic solved generator
  (`pathfinding_obstacles/generator.py` — knight 50 / bishop 20 /
  rook 20 / queen 10 with per-kind retries, 2–10 optimal moves,
  capture-or-detour meaningfulness gate, BFS-verified reachable with
  stored `optimal_moves`, answers server-side only). Rules live in one
  authoritative layer (`transitions.py`: movement + blocking +
  destination safety + undefended-only captures, safety evaluated on
  the post-move board so uncoverings are illegal); BFS searches
  complete board states, never white squares alone.
- Validator: `backend/app/modules/pathfinding_obstacles/validator.py`
  (stateful path replay with capture updates; correct iff every step
  is a legal transition AND the path ends on the star; single-step
  oracle at `POST /api/v1/pathfinding-obstacles/step` rebuilds the
  live state from the client FEN with server-stored kind/target and
  returns updated FEN + `reached` + `captured`, with post-completion
  rejection).
- Practice: `POST /api/v1/pathfinding-obstacles/next` issues fresh
  solved puzzles (identical rows reused; `exclude_ids` steers
  variety); the client keeps a current+next prefetch buffer. Answers
  go through standard `POST /api/v1/attempts`.
- Speed: `pathfinding_obstacles/sessions.py` + `router.py` (open →
  prepare ≥20 → start 60s clock → walk-to-star loop with ~400ms
  auto-advance, no manual next → server-rebuilt per-puzzle report;
  per-answer rows reuse `attempts`).
- Scoring: registered scorer (`optimal×5 − extra×2 − illegal×3`,
  negatives kept, independent of the CORRECT/WRONG label).
- Seed: `python -m app.modules.pathfinding_obstacles.seed` (15 solved
  puzzles from the generator with a fixed seed, still served
  read-only).

## Eighth slice

**Pin** — IMPLEMENTED (`pin`).

- Route: `/exercises/pin` (shared `ExercisePlay` move-input loop in drag-only
  mode, same pattern as Get Out of Check).
- Validator: `backend/app/modules/pin/validator.py` (any legal python-chess
  move whose resulting position contains a classical pin absent before the
  move; ray-based detection independent of side to move; FEN travels in the
  server-only `answer_json`, never exposed).
- Seed: `python -m app.modules.pin.seed` (15 hand-designed puzzles covering
  absolute/relative pins with all three sliders, all six pinned types,
  pawn/knight/king-created pins, multi-answer, existing-pin and decoy cases;
  every example independently verified at seed time).

## Ninth slice

**Balance Scale** — IMPLEMENTED (`balance-scale`).

- Route: `/exercises/balance-scale` (dedicated `BalanceScalePlay` loop reusing
  design-system/api/i18n/hint/feedback primitives and SVG pieces; no
  chessboard — bank-to-pan drag plus tap fallback, tilting beam, live totals).
- Validator: `backend/app/modules/balance_scale/validator.py` (no
  python-chess: multiset bank check plus submitted total against the stored
  right-pan total; any valid combination accepted).
- Seed: `python -m app.modules.balance_scale.seed` (15 hand-designed puzzles
  of rising difficulty with independent subset-sum verification; 15 persisted
  puzzles).

## Tenth slice

**Which Side is Heavier?** — IMPLEMENTED (`heavier-side`).

- Route: `/exercises/heavier-side` (shared `ExercisePlay` options loop with
  board hidden: three fixed choices, both sides rendered as SVG pieces with
  no values shown, totals revealed after submit).
- Validator: `backend/app/modules/material_comparison/validator.py` (no
  python-chess: choice matched against the relation derived from stored
  totals; client-supplied totals ignored).
- Seed: `python -m app.modules.material_comparison.seed` (15 hand-designed
  puzzles, 6 left / 6 right / 3 equal, with independent total verification).

## Eleventh slice

**Is it Checkmate?** — IMPLEMENTED (`is-checkmate`).

- Route: `/exercises/is-checkmate` (shared `ExercisePlay` options loop with
  read-only board: three fixed choices مات/کیش/بدون کیش, no hints of the
  answer on the board).
- Validator: `backend/app/modules/checkmate/validator.py` (state derived
  from the stored FEN via `is_check`/`is_checkmate`; stalemate classifies as
  not_check; FEN travels in the server-only `answer_json`, never exposed).
- Seed: `python -m app.modules.checkmate.seed` (15 hand-designed puzzles,
  5 checkmate / 5 check / 5 not_check incl. stalemate, double checks,
  blockable/capturable/king-escape and decoy cases; every classification
  independently verified at seed time).

## Twelfth slice

**Memory Board** — IMPLEMENTED (`memory-board`).

- Route: `/exercises/memory-board` (dedicated `MemoryBoardPlay` loop reusing
  board/attempt/timing/hint/feedback primitives: memorize phase with
  countdown, rebuild phase with palette + turn selector on an empty board,
  full reconstruction auto-compared server-side).
- Validator: `backend/app/modules/memory_board/validator.py` (submitted
  placement must equal the stored FEN placement exactly, plus side to move;
  castling/en-passant metadata ignored; FEN travels in the server-only
  `answer_json`, never exposed).
- Seed: `python -m app.modules.memory_board.seed` (15 hand-designed puzzles
  of rising difficulty, 8s/6s/4s memorize durations, every FEN independently
  verified at seed time).

## Thirteenth slice

**Blindfold Square Vision** — IMPLEMENTED (`blindfold-square-vision`).

- Route: `/exercises/blindfold-square-vision` (dedicated
  `BlindfoldSquareVisionPlay` loop reusing attempt/timing/hint/feedback
  primitives: empty board with neutral start/target markers, piece info card
  with SVG icon, large numeric input, post-submit shortest path display).
- Validator: `backend/app/modules/blindfold_square_vision/validator.py`
  (closed-form distances for king/queen/rook/bishop, BFS for knight and
  forward-only pawn; task params travel in the server-only `answer_json`,
  never exposed; unreachable pairs fail closed).
- Seed: `python -m app.modules.blindfold_square_vision.seed` (15
  hand-designed puzzles, K3/Q2/R2/B2/N4/P2 with 1/2/3/6-move knight cases;
  every distance independently verified at seed time).

## Fourteenth slice

**Blindfold Calculation** — IMPLEMENTED (`blindfold-calculation`).

- MVP supports only Mate in 1. No Mate in 2, combinations, or engine
  evaluation (mate detection is `legal moves` + `board.is_checkmate()`,
  never Stockfish).
- Route: `/exercises/blindfold-calculation` (dedicated
  `BlindfoldCalculationPlay` loop: NO chessboard, NO piece images, NO FEN
  at any point; Persian position description + SAN text input).
- Validator: `backend/app/modules/blindfold_calculation/validator.py`
  (submitted SAN parsed with `board.parse_san` against the stored FEN;
  CORRECT only when the move is legal AND produces checkmate; any legal
  mating move counts; `#`/`+` suffixes optional; malformed input is WRONG).
- Description: `backend/app/modules/blindfold_calculation/description.py`
  (deterministic Persian text: side to move, then White/Black pieces in
  King/Queen/Rook/Bishop/Knight/Pawn order, squares sorted; square names
  stay algebraic; TTS-ready via the existing `audio/ports.py` boundary,
  no provider added).
- Security: `Puzzle.fen` stays NULL and `position_json` carries only the
  description/side/mode; the FEN lives in server-only `answer_json`, so
  the puzzle endpoints never leak the position or the expected SAN.
- Seed: `python -m app.modules.blindfold_calculation.seed` (15
  hand-designed puzzles, each independently verified to have exactly one
  mate-in-1: back-rank, queen, rook, bishop, knight incl. smothered,
  pawn capture, Scholar's, black-to-move and corner patterns).

## Fifteenth slice

**Opening Traps Blindfold** — IMPLEMENTED (`opening-traps`).

- MVP is one tactical move from a genuine opening-trap position.
  Checkmate is NOT required; correctness is membership of the parsed move
  (normalized to UCI, never raw SAN comparison) in the puzzle's explicit
  solution set, so several different winning moves can be accepted.
- Route: `/exercises/opening-traps` (dedicated `OpeningTrapsPlay` loop:
  NO chessboard, NO piece images, NO FEN and NO solution data at any
  point; opening/trap/theme context plus Persian description, SAN input).
- Validator: `backend/app/modules/opening_traps/validator.py`
  (submitted SAN parsed with `board.parse_san`; malformed, illegal and
  ambiguous input is WRONG; legal-but-not-tactical is WRONG; CORRECT or
  WRONG only; client-supplied FEN/solutions/theme ignored).
- Description: `backend/app/modules/opening_traps/description.py`
  (deterministic Persian text: trap, opening, side to move, then pieces
  in King/Queen/Rook/Bishop/Knight/Pawn order; generic wording that never
  hints the winning move; TTS-ready via `audio/ports.py`, no provider).
- Security: `Puzzle.fen` stays NULL and `position_json` carries only
  description/side/mode/opening/trap/theme; FEN + solution UCIs live in
  server-only `answer_json`, so puzzle endpoints never leak them.
- Seed: `python -m app.modules.opening_traps.seed` (15 hand-designed
  puzzles from real lines — Legal, Blackburne Shilling, Scholar's,
  Fool's, Siberian, Noah's Ark, Mortimer, Elephant, Damiano, Fried Liver,
  Stafford, Rubinstein, Kieninger, Evans, Caro-Kann mate — each solution
  independently verified legal with its declared capture/check/mate
  property; Noah's Ark and Evans accept two tactics each; 11 white +
  4 black to move).
- Known limitation: unlisted objectively-strong alternatives count as
  WRONG, because the exercise grades the documented trap tactic, not
  general engine evaluation (no Stockfish by design).

## Sixteenth slice

**Opening Move Reconstruction** — IMPLEMENTED (`opening-move-reconstruction`).

- Route: `/exercises/opening-move-reconstruction` (dedicated
  `OpeningReconstructionPlay` loop with two boards: the read-only TARGET
  board on top, the user-driven reconstruction board below starting from
  the standard initial position; tap or drag to move, server-generated
  SAN move list, undo/reset, promotion picker).
- Validator: `backend/app/modules/opening_move_reconstruction/validator.py`
  (submitted UCIs replayed with python-chess from the stored start;
  CORRECT only when placement + side to move + castling rights +
  en-passant square equal the stored target; clocks ignored; any line
  reaching the target counts, so transpositions are accepted; CORRECT or
  WRONG only; detail carries both sequences plus matched/expected plies
  as move-by-move feedback).
- Step oracle: `POST /api/v1/reconstruction/step` (legality-only move
  assistance following the pathfinding-step precedent: replays the
  claimed history from the stored start, applies one legal move, returns
  the new FEN plus server-generated SAN and an on-track flag; reveals no
  solution data; final grading still revalidates the whole sequence).
- Security: `answer_json` (start/target/solutions) is server-only;
  `position_json` exposes start/target FENs for rendering plus opening
  context, never the sequence; client FENs/solutions are ignored.
- Seed: `python -m app.modules.opening_move_reconstruction.seed` (15
  real opening lines of 5-10 plies from the standard start — Italian,
  Ruy Lopez, Sicilian Najdorf, French Winawer, Caro-Kann, QGD, KID,
  Scotch, Four Knights, London, Petrov, Vienna, Alapin, Caro Advance,
  Evans — targets generated from the lines, all independently verified,
  no duplicate targets, mixed sides to move).
- Known limitation: single canonical line per puzzle in the seed, though
  the position-based grader already accepts any equivalent line.

## Seventeenth slice

**Trapped Pieces** — IMPLEMENTED (`trapped-pieces`).

- Route: `/exercises/trapped-pieces` (shared `ExercisePlay` loop with no
  pre-highlight; only the user's selections are shown).
- Validator: `backend/app/modules/trapped_pieces/validator.py` (trapped =
  non-king piece with zero pseudo-legal moves via `generate_pseudo_legal_moves`;
  pinned pieces have pseudo moves so they are NOT trapped; kings excluded).
- Seed: `python -m app.modules.trapped_pieces.seed` (15 hand-designed puzzles
  covering all five trappable kinds, pawn mutual blocks, pinned-not-trapped,
  king-excluded and empty cases; every answer independently verified).

## Eighteenth slice

**Rule of the Square** — IMPLEMENTED (`rule-of-the-square`).

- Route: `/exercises/rule-of-the-square` (dedicated `RuleOfTheSquarePlay`
  loop: visible board, two large touch choices شاه می‌رسد / شاه نمی‌رسد,
  no piece movement; the square corners are marked only after submission).
- Validator: `backend/app/modules/rule_of_the_square/validator.py`.
  The verdict is exact optimal race play for the lone king-versus-pawn
  race (exhaustive solving, no engine/tablebase/heuristics), which
  coincides with the classical square on every teachable position and
  additionally adjudicates tempo corners exactly (attacker-to-move edge
  cases where the naive drawing misleads). The classical square geometry
  is still computed per puzzle and drives the post-submit visualization
  and the generated Persian explanations.
- Seed: `python -m app.modules.rule_of_the_square.seed` (15 generated
  minimum-material positions, 8 CAN_CATCH / 7 CANNOT_CATCH, White and
  Black pawns, edge/central files, starting-rank double-steps, inside /
  just-outside boundaries, both sides to move; every FEN generated from
  structured data and independently verified legal; the drawn square is
  tested to agree with the verdict on all seeds).
- Security: `answer_json` holds only the FEN; the visible board renders
  from the `Puzzle.fen` column, `position_json` carries just the mode;
  the verdict is recomputed from the stored FEN on every submission and
  client-supplied FENs are ignored.
- Known limitation: MVP is the simplified single-pawn race only; no
  opposition, zugzwang subtleties beyond the race, or multi-pawn
  endgames.

## Nineteenth slice (end of the roadmap)

**Castling Rights** — IMPLEMENTED (`castling-rights`).

- Moved here from the former Exercise 6 slot; it is parked at the end
  of the roadmap and is not under active development.
- Route: `/exercises/castling-rights` (shared `ExercisePlay` loop extended
  with a fixed four-option mode; board shows the position as context only).
- Validator: `backend/app/modules/castling_rights/validator.py` (each option
  must appear in that color's python-chess legal moves on a turn-flipped
  board; explicit king/rook presence guards stale FEN flags safely).
- Seed: `python -m app.modules.castling_rights.seed` (15 puzzles covering all
  four options, single-option cases, absent rights, blocked paths incl. b-file,
  check, transit/destination attacks, stale rook/king flags, partial subsets).

## Exercise 4 (spec-track)

**Undefended Pieces** — IMPLEMENTED (`undefended-pieces`). Full spec:
`docs/exercises/04-undefended-pieces.md`.

- Route: `/exercises/undefended-pieces` with `?mode=practice` (untimed)
  and `?mode=speed` (60s session); card renders both entry buttons
  directly (no intermediate mode screen), same pattern as Exercises 1–3.
- Play loop: `frontend/src/components/exercise/UndefendedPiecesPlay.tsx`
  (practice + speed reusing the `PieceGameLayout` shell, timer, hints,
  feedback; NO pre-highlight — the whole board is the question, only the
  user's selections are shown); correctness, scoring, and the speed clock
  stay backend-authoritative.
- Position source: shared `puzzles.db` via `positions/repository.py`
  (read-only, FEN only, fallback FENs when absent), exactly like
  Exercise 1; per-puzzle answers built server-side by
  `undefended_pieces/generator.py` (bounded 25-candidate sampling that
  prefers non-empty positions while keeping zero-target valid, answers
  server-side only).
- Rule: non-King piece with ≥1 valid enemy attacker AND 0 valid friendly
  defenders, from python-chess attack geometry; absolutely pinned pieces
  (`board.is_pinned`, King only) never count as attackers/defenders;
  pieces shielding a Queen still count; Kings never answers but still
  attack/defend.
- Validator: `backend/app/modules/undefended_pieces/validator.py` (exact
  set match incl. empty==empty; duplicates/order-insensitive; malformed
  squares count as wrong).
- Practice: `POST /api/v1/undefended-pieces/next` issues fresh random
  published puzzles (identical FEN rows reused; `exclude_ids` steers
  variety); the client keeps a current+next prefetch buffer. Answers go
  through standard `POST /api/v1/attempts`.
- Speed: `undefended_pieces/sessions.py` + `router.py` (open → prepare
  ≥20 → start 60s clock → submit loop with ~450ms auto-advance, no
  manual next → server-rebuilt per-puzzle report; per-answer rows reuse
  `attempts`).
- Scoring: registered per-square scorer (+5 correct / −1 missed / −2
  wrong, +5 bonus for correctly answered zero-target, negatives kept,
  independent of the CORRECT/PARTIAL/WRONG label).
- Seed: `python -m app.modules.undefended_pieces.seed` (15 puzzles
  covering single/multiple/both-colors/none, all piece types as
  attackers and defenders, blockers, king attack/defense/exclusion, and
  the three mandatory pin regressions; every answer independently
  verified).
