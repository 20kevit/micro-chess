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

**Piece Recognition** — IMPLEMENTED (`piece-recognition`).

- Route: `/exercises/piece-recognition` (entry → play → feedback → next).
- Validator: `backend/app/modules/piece_recognition/validator.py` (set compare;
  correct/partial/wrong per spec; malformed squares count as wrong).
- Targets are data (`color` + piece `kinds`, incl. `minor-white`/`minor-black`
  and `queen-any`); new targets need no flow changes.
- Seed: `python -m app.modules.piece_recognition.seed` (15 puzzles, answers
  derived from FEN and covered by `tests/test_piece_recognition.py`).

## Second slice

**Legal Destinations** — IMPLEMENTED (`legal-destinations`).

- Route: `/exercises/legal-destinations` (shared `ExercisePlay` loop; target
  square highlighted, destinations server-authoritative).
- Validator: `backend/app/modules/legal_destinations/validator.py`.
- Rule profiles are data (`RULE_PROFILES`: `standard` via `legal_moves`,
  `ignore-enemy-attacks` via `pseudo_legal_moves`); new profiles plug in
  without touching the attempt flow.
- Seed: `python -m app.modules.legal_destinations.seed` (15 puzzles covering
  all six piece kinds, blockers, pawn/king edge cases, both profiles).

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
