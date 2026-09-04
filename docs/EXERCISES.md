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
