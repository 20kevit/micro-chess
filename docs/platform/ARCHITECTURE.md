# MicroChess Platform — Architecture

## 1. Document Status

**Status:** Accepted
**Document Type:** System Architecture (repository reality)
**Scope:** backend/frontend structure, subsystem boundaries,
request flows, persistence, deployment

This document describes the system as implemented. The exercise
pipeline detail lives in `docs/ARCHITECTURE.md`; the logical data
model in `DATA_MODEL.md`; API conventions in `API_CONTRACTS.md`;
the security model in `SECURITY.md`. Those documents are not
duplicated here — this one maps the code to the subsystems.

Conventions follow `AGENTS.md`: routers are thin wiring, business
logic lives in services or pure functions, and the frontend never
decides correctness.

## 2. System layout

```text
backend/                 FastAPI app + Passenger entry + requirements mirror
  app/main.py            composition root: lifespan, middleware, router mounts, SPA mount
  app/core/              config, error envelope, auth deps, capabilities,
                         rate limits, logging, pagination, SPA fallback
  app/db/                session/engine + idempotent ensure_schema (SCHEMA_VERSION = 16)
  app/modules/*/        one responsibility per module (section 3)
  app/cli.py             admin bootstrap (create-admin)
  passenger_wsgi.py      cPanel Passenger entry (WSGI callable `application`)
  requirements.txt       generated mirror of pyproject.toml (cPanel installs this)
frontend/                React + Vite + TS + Tailwind, RTL Persian shell
  src/main.tsx           routes (public, exercise, player, mentor, admin, NotFound)
  src/exercises/         catalog.ts — central exercise registry (19 active entries)
  src/api/               thin fetch transport (Bearer token, api_error envelope)
  src/components/        ui/ design system, chess/ board+pieces, exercise/ play loops
  src/i18n/              Persian strings (fa.ts); t("key") everywhere
  dist/                  committed production bundle (see docs/DEPLOYMENT.md)
docs/                    product + architecture + api + exercises + platform
.cpanel.yml              push-deployment task list (code paths only, pip, restart.txt)
```

## 3. Backend subsystems

All routers mount under `/api/v1` (`app/core/api.py`);
`GET /health` returns `{"status":"ok"}`. Wiring only — see
`backend/app/main.py`.

| Subsystem | Modules | Exposes |
|---|---|---|
| Identity & sessions | `auth`, `users` | `/auth/register`, `/auth/login`, `/auth/active-role`, `/auth/logout`, guest sessions + migrate, `/users/me` |
| Player platform | `player` | `/me/*`: profile, identities, training history, progress, ratings, gamification, analytics, dashboard |
| Exercise pipeline | `exercises` (catalog + validator/scorer `registry`), `puzzles`, `progress` (attempts), `positions` (shared read-only `puzzles.db`), `chess_engine` (python-chess wrapper only), `rule_engine`, `scoring_engine`, `feedback_engine`, `rating_engine` (Elo-style; Glicko-2 deferred) | `GET /exercises`, `GET /puzzles`, `POST /attempts` |
| Exercises 1–12, 14, 15, 18 | `piece_recognition`, `legal_destinations`, `captures`, `undefended_pieces`, `give_check`, `get_out_of_check`, `pathfinding`, `pathfinding_obstacles`, `balance_scale`, `material_comparison`, `chinese_board`, `blindfold_square_vision`, `blindfold_calculation`, `trapped_pieces` | per-exercise practice (`POST .../next`) + prepare-then-clock speed sessions (`/sessions`, `/puzzles`, `/start`, `/submit`, `/report`, `/finish`); 60s clock, ≥20 prepared buffer |
| Seeded-attempt exercises | `pin`, `checkmate`, `opening_traps`, `castling_rights` | validator + seed only — played via `/puzzles` + `/attempts`, no speed mode |
| Reverse opening | `reverse_opening` | validator + seed + legality-only `POST /reverse-opening/step`; grading via `/attempts` |
| Ratings | `rating_engine` | server-decided eligibility, Elo-style update vs puzzle rating, `PlayerRating` + immutable `RatingEvent`; practice attempts never rate |
| Gamification | `gamification_engine` | XP, streaks, achievements |
| Administration | `admin` | `/admin/*`: dashboard, users, exercises, puzzles, generators, analytics, support, audit |
| Content & generators | `generators` + per-exercise generators | content jobs; puzzle lifecycle (publish immutable answers, archive never hard-delete) |
| Analytics | `analytics` | player + admin + observed-difficulty queries |
| Relationships | `relationships` | coach–student and parent–student edges, scoped reads, assignments |
| Adaptive training | `adaptive` | `/me/adaptive/*`, `/coach/*`, `/parent/*` selection policy |
| Support & notifications | `support`, `notifications` | tickets + messages, in-app notifications + preferences |
| Placeholders | `assignments`, `learning`, `audio` (TTS boundary only) | single-`__init__` modules; no framework code |

Exercise slugs registered (19): `piece-recognition`,
`legal-destinations`, `captures`, `undefended-pieces`,
`give-check` (served at route `/giving-check`), `get-out-of-check`,
`pathfinding`, `pathfinding-obstacles`, `balance-scale`,
`heavier-side`, `pin`, `chinese-board`, `is-checkmate`,
`blindfold-square-vision`, `blindfold-calculation`,
`opening-traps`, `reverse-opening`, `trapped-pieces`,
`castling-rights`. Official numbering: `docs/EXERCISES.md`.

## 4. Request flows

Attempt (core flow, no per-exercise branches):

```text
POST /api/v1/attempts
→ progress/router (thin)
→ progress/service.submit_attempt
  → puzzles lookup (published + not archived only)
  → exercises/registry.validate_answer (exercise validator or WRONG fallback)
  → exercises/registry.score_for_answer (exercise scorer or shared default)
  → rating_engine (rated + authenticated only; None otherwise)
  → feedback_engine.feedback_key_for
  → persist Attempt with raw answer_json
```

Speed session (all fourteen session exercises share the lifecycle):

```text
POST .../sessions                (preparing, no clock)
POST .../sessions/{id}/puzzles   (buffer/refill, cap 60)
POST .../sessions/{id}/start     (requires ≥20; starts 60s server clock)
POST .../sessions/{id}/submit    (reuses submit_attempt, mode=practice)
410 session_expired past ends_at
GET  .../sessions/{id}/report    (rebuilt from stored attempts)
```

## 5. Persistence

- Engine/session: `app/db/session.py` (`DATABASE_URL`,
  `check_same_thread=False` for SQLite only).
- Schema: `ensure_schema` (`app/db/migration.py`) imports every
  `app/modules/*/models.py`, runs `Base.metadata.create_all`,
  then applies ordered migrations v2–v11 once each, stamped in
  `schema_version`. Idempotent, non-destructive, downgrade-safe.
  Portable column types only.
- Full logical model: `DATA_MODEL.md`. Implemented phase evidence:
  `IMPLEMENTATION_STATE.md`.

## 6. Frontend

- Routes (`src/main.tsx`): `/`, `/exercises`,
  `/exercises/<slug>` (practice/speed via `?mode=`), account and
  player pages (`/login`, `/register`, `/account`, `/progress`,
  `/profile`, `/relationships`, `/support`, `/notifications`,
  coach/parent views), `/admin/*` behind `RequireAdmin`,
  `*` → NotFound.
- `src/exercises/catalog.ts` (19 active entries) drives
  `ExercisesPage` cards; entries declare their modes
  (practice/speed or practice-only).
- Play loops in `src/components/exercise/` reuse the `PieceGameLayout`
  shell; `ChessBoard` renders SVG pieces only. Anonymous progress in
  `src/lib/localProgress.ts`; the server is the source of truth for
  accounts. Visual language: `docs/DESIGN_SYSTEM.md`.

## 7. Deployment

FastAPI serves the committed `frontend/dist/` from
`backend/static/` with SPA fallback (`app/core/frontend.py`,
mounted last; `/api/*` never falls back). cPanel push deployment
via `.cpanel.yml` onto the `microche` account with the
`passenger_wsgi.py` adapter (lazy per-PID middleware for LiteSpeed
fork-safety). Overview: `docs/DEPLOYMENT.md`. Operator runbook:
`CPANEL_DEPLOYMENT.md`.

## 8. Invariants

1. Backend authoritative for validation/scoring/rating.
2. Puzzle answers immutable once published; archive, don't delete.
3. Practice attempts never affect rating.
4. Secrets only from the environment; production refuses the dev
   JWT secret (`Settings.ensure_ready()`).
5. Portable SQL only; no SQLite-only DDL.
6. No per-exercise branches in core flow — registry only.
7. Standard chess (python-chess) vs exercise-custom rules stay in
   separate modules.
