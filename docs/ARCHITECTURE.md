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
| `chess_engine` | python-chess wrapper ONLY (standard rules) |
| `rule_engine` | `AttemptResult`/`AttemptMode`/`ValidationResult` contract |
| `rating_engine` | stub; Glicko-2 later |
| `scoring_engine` | pure result → score |
| `feedback_engine` | pure result → i18n key |
| `learning` | placeholder (educational content later) |
| `progress` | `Attempt` model + submit flow |
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
  → scoring_engine.score_for
  → rating_engine.preview_rating_delta (only rated + logged in; None for now)
  → feedback_engine.feedback_key_for
  → persist Attempt with raw answer_json
```

No `if/elif` per exercise in core flow. New exercise = new validator function + `register_validator(slug, fn)`.

## Database (foundation)

- `users(id, email!, password_hash, display_name, is_active, created_at)`
- `exercises(slug PK, title_fa, title_en, description, is_active, sort_order)`
- `puzzles(id, exercise_slug FK, fen?, position_json, answer_json, hint_json, initial_rating, is_published, is_archived, published_at, created_at)`
- `attempts(id, user_id? FK, puzzle_id FK, exercise_slug, mode, result, answer_json, score, rating_delta?, created_at)`

Notes:

- Portable types only; `DATABASE_URL` switch + Alembic later for PostgreSQL.
- Fresh DB allowed; no migration compat needed at this stage.
- Future tables (ratings, assignments, audio assets): add when the feature lands.

## Frontend

- Routes: `/`, `/exercises`, `*` → NotFound. Exercise detail pages come with Piece Recognition.
- `api/client.ts` transports data only. `i18n/` holds Persian strings (`fa.ts`).
- `components/ui/` design system; `components/chess/` SVG board + pieces.
- `lib/localProgress.ts` anonymous localStorage stub.

## Decisions log

1. JWT bearer auth (simplest for mobile + future apps) over sessions.
2. Registry dict over plugin framework — explicit, searchable, testable.
3. `score_for`: correct=1.0, partial=0.5, else 0. Practice still scores; only rating is gated.
4. `rating_delta` nullable now; `preview_rating_delta` returns None until Glicko-2.
5. Tailwind v4 (`@import "tailwindcss"`) to avoid config boilerplate.
6. No Alembic yet — `init_db()` + `create_all` is enough for the foundation stage.
