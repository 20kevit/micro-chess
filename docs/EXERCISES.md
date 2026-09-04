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

**Piece Recognition** — detailed spec comes separately. Do not invent requirements.
