# Architecture

## Layout

```text
frontend/  React + Vite + TS + Tailwind + Router, RTL Persian shell
backend/   FastAPI + SQLAlchemy + Pydantic, modular by responsibility
docs/      product + architecture + api + exercises
```

## Backend modules

| Module | Role |
|---|---|
| `auth` | register/login, JWT |
| `users` | account model + `/me` |
| `exercises` | catalog model + validator `registry` |
| `puzzles` | puzzle model + publish/archive service |
| `positions` | shared read-only `puzzles.db` access (FEN only) + fallback FENs; no exercise logic |
| `chess_engine` | python-chess wrapper ONLY (standard rules) |
| `rule_engine` | `AttemptResult`/`AttemptMode`/`ValidationResult` contract |
| `rating_engine` | stub; Glicko-2 later |
| `scoring_engine` | pure result → score |
| `feedback_engine` | pure result → i18n key |
| `learning` | placeholder (educational content later) |
| `progress` | `Attempt` model + submit flow |
| `piece_recognition` | exercise 1: validator + generator + speed sessions + router (registers `piece-recognition`) |
| `legal_destinations` | exercise 2: validator + scorer + white-only generator + speed sessions + router (registers `legal-destinations`) |
| `captures` | exercise 3: validator + scorer + hunter-vs-black generator + speed sessions + router (registers `captures`) |
| `undefended_pieces` | exercise 4: validator + scorer + shared-position generator + speed sessions + router (registers `undefended-pieces`) |
| `give_check` | exercise 5: validator + scorer + shared-position generator (in-check rejection) + speed sessions + router (registers `give-check`) |
| `pathfinding` | exercise 6: movement geometry + BFS (`moves.py`) + validator + scorer + weighted generator + speed sessions + router (registers `pathfinding`) |
| `assignments` | placeholder |
| `audio` | `AudioPort` boundary only |
| `admin` | placeholder |

Placeholders are single `__init__.py` files with a docstring. No framework code.

## Request flow (attempt)

```text
POST /api/v1/attempts
→ progress/router (thin)
→ progress/service.submit_attempt
  → puzzles lookup (published + not archived only)
  → exercises/registry.validate_answer (exercise validator or WRONG fallback)
  → exercises/registry.score_for_answer (exercise scorer or shared default)
  → rating_engine.preview_rating_delta (only rated + logged in; None for now)
  → feedback_engine.feedback_key_for
  → persist Attempt with raw answer_json
```

Exercise 1 extras (same pattern, no core-flow changes):

```text
puzzles.db (shared, read-only, FEN only; indexed rowid sampling)
→ positions/repository (data access; skips invalid rows; fallback FENs;
  pinned paths are authoritative)
→ piece_recognition/generator (random FEN + random canonical question
  → prompt/explanation/hint → persisted published Puzzle; identical
  (position, question) rows reused, exclude_ids steer variety)
→ POST /api/v1/piece-recognition/next (practice, current+next prefetch
  buffer client-side) — returns PuzzleOut, no answer
→ POST /api/v1/attempts (standard submit; per-square 5/-1/-2 scorer)

Speed sessions (prepare-then-clock in piece_speed_sessions):
→ POST .../sessions (preparing, no clock)
→ POST .../sessions/{id}/puzzles {"count": 20} (initial buffer; refill later)
→ POST .../sessions/{id}/start (requires ≥20; sets ends_at; 60s run)
→ POST .../sessions/{id}/submit (reuses submit_attempt, mode=practice)
→ 410 session_expired when server time passes ends_at
→ GET .../sessions/{id}/report (per-puzzle entries rebuilt from attempts)
```

No `if/elif` per exercise in core flow. New exercise = new validator function + `register_validator(slug, fn)`.

## Database (foundation)

- `users(id, email!, password_hash, display_name, is_active, created_at)`
- `exercises(slug PK, title_fa, title_en, description, is_active, sort_order)`
- `puzzles(id, exercise_slug FK, fen?, position_json, answer_json, hint_json, initial_rating, is_published, is_archived, published_at, created_at)`
- `attempts(id, user_id? FK, puzzle_id FK, exercise_slug, mode, result, answer_json, score, rating_delta?, created_at)`

Piece Recognition additions (same tables, new columns only):

- `puzzles.prompt_fa` (question text), `puzzles.explanation` (shown after answering).
- `puzzles.answer_json` convention: `{"squares": [...], "target": "<key>"}`.
- `puzzles.hint_json` convention: `{"hints": [{"id", "text_fa", "rating_cost"}]}`.
- `attempts.started_at?`, `attempts.duration_ms?` (server-computed), `attempts.hints_used` (JSON list).
- `ValidationResult.detail` carries `{"correct", "missed", "wrong"}` back to the client.
- `piece_speed_sessions(id, exercise_slug, user_id?, status, duration_s=60,
  started_at, ends_at? (null while preparing), puzzle_ids[], attempt_ids[],
  attempted/correct/partial/wrong_count, score)` — prepare-then-clock 60s
  sessions for Exercise 1 Speed Mode; per-answer rows still live in
  `attempts` (mode=practice), and the final report rebuilds from them.
- `legal_speed_sessions` — same shape for Exercise 2 Speed Mode
  (`legal_destinations/sessions.py` mirrors the Exercise 1 lifecycle).
- `capture_speed_sessions` — same shape for Exercise 3 Speed Mode
  (`captures/sessions.py` mirrors the same lifecycle; hunter-vs-black
  puzzles from `captures/generator.py`).
- `undefended_speed_sessions` — same shape for Exercise 4 Speed Mode
  (`undefended_pieces/sessions.py` mirrors the same lifecycle; random
  shared `puzzles.db` positions evaluated by `undefended_squares`).
- `giving_check_speed_sessions` — same shape for Exercise 5 Speed Mode
  (`give_check/sessions.py` mirrors the same lifecycle; random shared
  `puzzles.db` positions evaluated by `checking_moves`, in-check
  positions rejected at generation).
- `pathfinding_speed_sessions` — same shape for Exercise 6 Speed Mode
  (`pathfinding/sessions.py` mirrors the same lifecycle; weighted
  single-piece puzzles from `pathfinding/generator.py`, BFS optimals
  stored server-side).

Notes:

- Portable types only; `DATABASE_URL` switch + Alembic later for PostgreSQL.
- Fresh DB allowed; no migration compat needed at this stage.
- Future tables (ratings, assignments, audio assets): add when the feature lands.

## Frontend

- Routes: `/`, `/exercises`, `/exercises/<slug>` (practice/speed via `?mode=`), `*` → NotFound.
- `api/client.ts` transports data only. `i18n/` holds Persian strings (`fa.ts`).
- `components/ui/` design system; `components/chess/` SVG board + pieces + reusable multi-arrow layer (`BoardArrow`, toned feedback arrows, `arrowDrawMode`, shaft-shortened `computeArrowGeometry` in board units).
- `components/exercise/` play loops (shared `ExercisePlay` + dedicated loops
  like `PieceRecognitionPlay`); `exercises/catalog.ts` is the central registry
  (entries may declare explicit `modes`, e.g. practice/speed).
- `lib/localProgress.ts` anonymous localStorage stub; `lib/sound.ts` tiny
  WebAudio blips (error/success) with no dependencies.
- Visual language documented in `docs/DESIGN_SYSTEM.md`; tokens in `index.css`.

## Decisions log

1. JWT bearer auth (simplest for mobile + future apps) over sessions.
2. Registry dict over plugin framework — explicit, searchable, testable.
3. `score_for`: correct=1.0, partial=0.5, else 0 — the SHARED default.
   Exercises needing different math register a scorer
   (`register_scorer(slug, fn)`); Piece Recognition scores per square
   (+5 correct / −1 missed / −2 wrong, negatives allowed, never clamped).
   Practice still scores; only rating is gated.
4. `rating_delta` nullable now; `preview_rating_delta` returns None until Glicko-2.
5. Tailwind v4 (`@import "tailwindcss"`) to avoid config boilerplate.
6. No Alembic yet — `init_db()` + `create_all` is enough for the foundation stage.
7. Piece Recognition: exact set-match validator (empty==empty is CORRECT;
   malformed squares count as wrong); targets are data (`color` + `kinds`),
   canonical 12 color×kind for generation plus legacy `queen-any`/minor targets.
8. No target-piece highlighting on the board — avoids leaking the answer.
9. Hints recorded per attempt (`hints_used` + `rating_cost` in data); rating math still stubbed.
10. `puzzles.db` is a shared read-only position source (FEN only, indexed
    rowid sampling, pinned paths authoritative); exercise
    question/answer/score generation happens server-side per exercise;
    zero-target questions are valid; Practice is untimed with a
    current+next prefetch buffer; Speed prepares ≥20 before its
    backend-authoritative 60s clock starts and reports from stored
    attempts; the frontend never receives the answer before submission;
    the board never exceeds the viewport; the MicroChess Design System
    (`docs/DESIGN_SYSTEM.md`) is shared by future exercises.
