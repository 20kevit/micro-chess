# Exercises (catalog of future work)

No exercise is implemented in the foundation. Each gets its own spec from the user
before implementation. New exercise = catalog row + validator + tests + UI.

Planned types (examples, not specs):

1. Piece Recognition
2. Legal Destinations
3. Captures
4. Hanging Pieces
5. Equal Attackers & Defenders
6. Castling Rights
7. Give Check
8. Get Out of Check
9. Pathfinding
10. Pin
11. Balance Scale
12. Which Side is Heavier?
13. Is it Checkmate?
14. Memory Board
15. Blindfold Square Vision
16. Trapped Pieces
17. Blindfold Calculation
18. Opening Traps Blindfold
19. Reverse Opening
20. Avoid Stalemate
21. Square Rule

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

**Captures** — IMPLEMENTED (`captures`).

- Route: `/exercises/captures` (shared `ExercisePlay` loop; hunter square
  highlighted, capturable squares server-authoritative).
- Validator: `backend/app/modules/captures/validator.py` (legal captures via
  `is_capture` on `legal_moves`: sliding rays stop at first occupation, pawn
  pushes never count, king safety enforced; empty answer accepts only an
  empty submission).
- Seed: `python -m app.modules.captures.seed` (15 puzzles covering all six
  hunter kinds, friendly/enemy blockers, pawn diagonals, legal/illegal king
  captures, no-capture positions).

## Fourth slice

**Hanging Pieces** — IMPLEMENTED (`hanging-pieces`).

- Route: `/exercises/hanging-pieces` (shared `ExercisePlay` loop with no
  pre-highlight; only the user's selections are shown).
- Validator: `backend/app/modules/hanging_pieces/validator.py` (hanging =
  enemy attackers > 0 AND friendly defenders == 0, from python-chess attack
  geometry, never legal moves; own square never counts as a defender).
- Seed: `python -m app.modules.hanging_pieces.seed` (15 puzzles covering
  single/multiple/none hanging, multi-attack/defense, all piece types as
  attackers and defenders, blockers, king attack/defense, decoys).

## Fifth slice

**Equal Attackers & Defenders** — IMPLEMENTED (`equal-attackers-defenders`).

- Route: `/exercises/equal-attackers-defenders` (shared `ExercisePlay` loop
  with no pre-highlight; only the user's selections are shown).
- Validator: `backend/app/modules/equal_attackers_defenders/validator.py`
  (target = attackers > 0 AND attackers == defenders, from python-chess
  attack geometry, never legal moves; own square never counts as a defender).
- Seed: `python -m app.modules.equal_attackers_defenders.seed` (15 puzzles
  covering 1v1/2v2/3v3, unequal counts, empty boards, all piece types as
  attackers and defenders, blockers, king attack/defense, decoys).

## Sixth slice

**Castling Rights** — IMPLEMENTED (`castling-rights`).

- Route: `/exercises/castling-rights` (shared `ExercisePlay` loop extended
  with a fixed four-option mode; board shows the position as context only).
- Validator: `backend/app/modules/castling_rights/validator.py` (each option
  must appear in that color's python-chess legal moves on a turn-flipped
  board; explicit king/rook presence guards stale FEN flags safely).
- Seed: `python -m app.modules.castling_rights.seed` (15 puzzles covering all
  four options, single-option cases, absent rights, blocked paths incl. b-file,
  check, transit/destination attacks, stale rook/king flags, partial subsets).

## Seventh slice

**Give Check** — IMPLEMENTED (`give-check`).

- Route: `/exercises/give-check` (shared `ExercisePlay` loop extended with a
  from→to move-input mode, promotion picker and exercise-mode toggle; the
  modes `all-checks`/`appropriate-checks` currently behave identically).
- Validator: `backend/app/modules/give_check/validator.py` (any legal
  python-chess move that leaves the opponent king in check; FEN travels in
  the server-only `answer_json`, never exposed).
- Seed: `python -m app.modules.give_check.seed` (15 hand-designed puzzles
  covering all piece types, discovered/capture/blocked/pinned/multi-answer
  and promotion checks; every example independently verified at seed time).

## Eighth slice

**Get Out of Check** — IMPLEMENTED (`get-out-of-check`).

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

## Ninth slice

**Pathfinding** — IMPLEMENTED (`pathfinding`).

- Route: `/exercises/pathfinding` (dedicated `PathfindingPlay` loop reusing
  board/attempt/timing/hint/feedback primitives: per-move drag validated by
  `POST /api/v1/pathfinding/step`, star-marked target, full path auto-submitted
  as one attempt on arrival).
- Validator: `backend/app/modules/pathfinding/validator.py` (legal
  python-chess move plus exercise rule: captures only onto enemies, empty
  squares only when unattacked; control recalculated after every move).
- Generator + seed: `python -m app.modules.pathfinding.seed` (deterministic
  templates for all six piece types, every template proven solvable by BFS;
  15 persisted puzzles).

## Tenth slice

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

## Eleventh slice

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

## Twelfth slice

**Which Side is Heavier?** — IMPLEMENTED (`heavier-side`).

- Route: `/exercises/heavier-side` (shared `ExercisePlay` options loop with
  board hidden: three fixed choices, both sides rendered as SVG pieces with
  no values shown, totals revealed after submit).
- Validator: `backend/app/modules/material_comparison/validator.py` (no
  python-chess: choice matched against the relation derived from stored
  totals; client-supplied totals ignored).
- Seed: `python -m app.modules.material_comparison.seed` (15 hand-designed
  puzzles, 6 left / 6 right / 3 equal, with independent total verification).

## Thirteenth slice

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

## Fourteenth slice

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

## Fifteenth slice

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

## Sixteenth slice

**Trapped Pieces** — IMPLEMENTED (`trapped-pieces`).

- Route: `/exercises/trapped-pieces` (shared `ExercisePlay` loop with no
  pre-highlight; only the user's selections are shown).
- Validator: `backend/app/modules/trapped_pieces/validator.py` (trapped =
  non-king piece with zero pseudo-legal moves via `generate_pseudo_legal_moves`;
  pinned pieces have pseudo moves so they are NOT trapped; kings excluded).
- Seed: `python -m app.modules.trapped_pieces.seed` (15 hand-designed puzzles
  covering all five trappable kinds, pawn mutual blocks, pinned-not-trapped,
  king-excluded and empty cases; every answer independently verified).

## Seventeenth slice

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

## Eighteenth slice

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

## Nineteenth slice

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

## Twenty-first slice

**Rule of the Square** — IMPLEMENTED (`rule-of-the-square`).

- Exercise 20 stays intentionally absent; the catalog moves from 19 to 21.
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
