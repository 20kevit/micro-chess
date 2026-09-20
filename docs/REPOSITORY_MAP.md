# MicroChess Repository Map

Navigation aid for coding agents: **where to look first**, not a second
`ARCHITECTURE.md`. Read this, then inspect the actual source files before
changing anything — the map is a guide, not a substitute for evidence.

Conventions: backend paths are under `backend/`; frontend paths under
`frontend/src/`. Every path listed here was verified against the repo.

## 1. Top-level layout

```text
AGENTS.md                  Agent rules (read first; Persian UI, boundaries, gates)
README.md                  Product overview and implemented-feature summary
CHANGELOG.md               Deployment/platform change log
CONTRIBUTING.md / SECURITY.md
.cpanel.yml                cPanel push-deployment task list (code-only replace)
docs/                      All documentation (see section 7)
backend/                   FastAPI backend (authoritative logic)
  app/main.py              ASGI entry; thin router wiring only
  app/core/                Cross-cutting: config, auth deps, errors, API prefix,
                           SPA static serving (frontend.py), logging, rate limit
  app/db/                  base.py, session.py, migration.py (SCHEMA_VERSION)
  app/modules/             Domain modules (router/service split, section 3)
  app/tools/               Offline-only Lichess puzzle ingestion (never imported
                           by the runtime)
  tests/                   pytest suite, one file per area (test_*.py)
  passenger_wsgi.py        cPanel Passenger WSGI entry (lazy per-PID middleware)
  pyproject.toml           Dependency source of truth; requirements.txt mirrors it
frontend/                  React + Vite + Tailwind v4 SPA (renders only)
  src/main.tsx             Router entry (all routes defined here)
  src/App.tsx              Placeholder (kept for tooling compat)
  src/pages/               Route screens (HomePage, *Page per exercise, dashboards)
  src/components/          chess/ exercise/ landing/ player/ ui/
  src/exercises/catalog.ts Central exercise registry (slug, route, status, modes)
  src/api/                 Typed HTTP client (client.ts, types.ts, *.test.ts)
  src/lib/                 auth-context, route guards, display helpers, sounds
  src/i18n/fa.ts           All Persian UI strings (t("key") only)
  src/index.css            Vazirmatn + design-system tokens
  public/chess-pieces/     Local Cburnett SVG pieces (never Unicode glyphs)
  dist/                    Committed prebuilt bundle (generated, do not edit)
  qa/*.cjs                 Puppeteer manual QA scripts (not part of CI)
```

## 2. Important entry points

| Concern | File |
|---|---|
| Backend app boot | `backend/app/main.py` |
| cPanel WSGI entry | `backend/passenger_wsgi.py` |
| Frontend routes | `frontend/src/main.tsx` |
| Anonymous landing vs role home | `frontend/src/pages/HomePage.tsx` |
| Public landing page | `frontend/src/components/landing/LandingPage.tsx` |
| Exercise catalog (menu, not play) | `frontend/src/pages/ExercisesPage.tsx` + `frontend/src/exercises/catalog.ts` |
| Exercise play shells | `frontend/src/pages/*Page.tsx` → `frontend/src/components/exercise/*Play.tsx` |
| Player dashboard | `frontend/src/pages/DashboardPage.tsx` |
| Progress, XP, recommendations, adaptive | `frontend/src/pages/ProgressPage.tsx` + `frontend/src/components/player/` |
| Auth state / guards | `frontend/src/lib/auth-context.tsx`, `require-auth.tsx`, `require-role.tsx`, `require-admin.tsx` |
| Attempt submission (server) | `backend/app/modules/progress/` + per-exercise `router.py` |
| Recommendations | `backend/app/modules/recommendations/service.py` (read-only) |
| Adaptive training | `backend/app/modules/adaptive/service.py` |
| Evidence → skill → mastery | `backend/app/modules/evidence/`, `skill_state/`, `mastery/` (all read-only derivations) |
| Ratings | `backend/app/modules/rating_engine/service.py` (Elo-style; practice never sets `rating_delta`) |
| Schema source of truth | `backend/app/db/migration.py` (`SCHEMA_VERSION`) + `docs/platform/DATA_MODEL.md` |
| SPA serving + fallback | `backend/app/core/frontend.py` (serves `backend/static/`) |

## 3. Backend module map (one line each)

Platform:

```text
auth/            Register/login, JWT sessions, guest sessions, active-role switching.
users/           User accounts and profiles (no password logic; lives in auth/).
billing/         Plans/prices, subscriptions, entitlements, coupons, campaigns,
                 attribution, payments + NullProvider boundary (schema v15).
admin/           Operational dashboard, user/exercise/puzzle management API.
analytics/       Trend/comparison aggregates recomputed from attempts on read.
support/         Support tickets and operator replies.
notifications/   In-app notifications + delivery preferences.
relationships/   Coach-student / parent-child edges; player-approved only.
assignments/     Placeholder: coach-assigned puzzle sets land here later.
player/          Player-facing read models (dashboard, profile, identities).
progress/        Attempt history, filters, per-exercise summaries; fans out to evidence.
puzzles/         Puzzle lifecycle (publish/archive); answer_json immutable once published.
generators/      Seeded content generators + run registry (admin-triggered).
positions/       Position repository backing generated content.
```

Training intelligence (read-only derivations; recompute on read, never persist):

```text
evidence/        Mistake classification + durable attempt evidence (taxonomy.py, classify.py).
skill_state/     Per-skill levels aggregated from evidence.
mastery/         Deterministic mastery from skill_state/evidence (Evidence -> Skill -> Mastery).
recommendations/ Next-exercise selection: direct assignment first, then engine; never writes.
adaptive/        Next-item selection with observed-difficulty reasons.
rating_engine/   Per-exercise Elo-style ability; practice attempts never write rating_delta.
scoring_engine/ Attempt scoring kept separate from validation and rating.
feedback_engine/ Feedback-key derivation kept separate from scoring.
rule_engine/     Shared rule base (base.py) for validators.
```

Content (one module per exercise family; custom rules live in that
exercise's `validator.py`, registered via `modules/exercises/registry.py`):

```text
exercises/       Exercise registry + enable/disable (never per-slug if/elif in core flow).
piece_recognition/, legal_destinations/, captures/, undefended_pieces/,
pin/, trapped_pieces/, give_check/, get_out_of_check/, castling_rights/,
checkmate/, balance_scale/, heavier_side/ (material_comparison/),
pathfinding/, pathfinding_obstacles/, chinese_board/ (memory_board/),
blindfold_square_vision/, blindfold_calculation/, opening_traps/,
reverse_opening/
  Full shape: validator.py, generator.py, seed.py, content.py, sessions.py,
  scoring.py, models.py, schemas.py, router.py (see piece_recognition/).
chess_engine/    python-chess wrapper ONLY (board.py); standard chess logic lives here.
audio/           TTS boundary (ports.py); vendor SDKs never enter domain code.
learning/        Placeholder: hints/explanations attach to puzzles later.
memory_board/, rule_of_the_square/  Empty dirs; no code yet, do not reference.
```

## 4. Frontend map (where to look)

| Want to change… | Look at… |
|---|---|
| Public landing page | `components/landing/LandingPage.tsx` + `landing.css`; strings in `i18n/fa.ts` (`landing.*`); anonymous branch of `pages/HomePage.tsx` |
| Exercise catalog menu | `pages/ExercisesPage.tsx` + `exercises/catalog.ts` (status-driven; no per-slug conditionals) |
| Exercise play UI | `pages/<Exercise>Page.tsx` (thin) → `components/exercise/<Exercise>Play.tsx`; shared layout `PieceGameLayout.tsx`, `ExercisePlay.tsx` |
| Board / pieces | `components/chess/ChessBoard.tsx`, `ChessPiece.tsx` (local SVG; board islands are `dir="ltr"`) |
| Dashboard / progress | `pages/DashboardPage.tsx`, `pages/ProgressPage.tsx`; `components/player/` (`Recommendation`, `Adaptive`, `Gamification`, `Analytics`, `Ratings` sections) |
| Auth screens / session | `pages/LoginPage.tsx`, `RegisterPage.tsx`, `AccountPage.tsx`; `lib/auth-context.tsx` |
| Pricing / subscription | `pages/PricingPage.tsx` (`/pricing`); `lib/attribution.ts` (first-touch localStorage); `api/client.ts` (`billingApi`, `adminBillingApi`) |
| Coach / parent views | `pages/MentorStudentsPage.tsx`, `pages/RelationshipsPage.tsx` |
| Admin views | `pages/Admin*Page.tsx` (mirror `backend/app/modules/admin/`) |
| Shared UI primitives | `components/ui/` (`Button`, `Card`, `PageHeader`, `Badge`, `AppShell`); reuse, don't restyle per page |
| Persian text | `i18n/fa.ts` via `t("key")`; never hard-code UI strings |
| Styles / tokens | `index.css` (`--mc-*` tokens; documented in `docs/DESIGN_SYSTEM.md`) |
| API transport | `api/client.ts` + `api/types.ts`; pages fetch, backend decides |
| Anonymous local progress | `lib/localProgress.ts` (localStorage; server is truth for accounts) |
| Frontend tests | Colocated `*.test.ts(x)` next to the file under test (`vitest run`) |

## 5. Established architecture boundaries (from AGENTS.md + source)

- Backend is authoritative for validation, scoring, rating, feedback.
  `frontend/` renders boards and transports answers; it never decides correctness.
- `app/main.py` and `*/router.py` are thin wiring. Business logic lives in
  `*/service.py` or pure functions.
- Standard chess logic: `modules/chess_engine/` only. Exercise-specific
  rules: that exercise's validator (registered in `modules/exercises/registry.py`).
- Keep separate: Exercise / Puzzle / Position / Attempt; and validation
  vs scoring vs rating vs feedback.
- `recommendations/`, `mastery/`, `skill_state/`, `analytics/` are read-only:
  recompute from authoritative state on read, never persist derived rows.
- Data: puzzle `answer_json` immutable once published; never hard-delete
  puzzles with history (`archive()`); portable SQLAlchemy types only.
- Frontend: Persian RTL pages, `dir="ltr"` board islands, SVG pieces only,
  mobile-first 44px targets, shared `components/ui` design system, `t("key")` i18n.
- Home routing: `/` is anonymous landing OR active-role dashboard
  (PLAYER/COACH/PARENT/ADMIN) — never mix; landing stays separate from `/exercises`.

## 6. Common change locations

| Task | Start here |
|---|---|
| Change public landing | `components/landing/LandingPage.tsx`, `i18n/fa.ts` (`landing.*`) |
| Change exercise catalog | `exercises/catalog.ts`, `pages/ExercisesPage.tsx` |
| Change exercise play UI | `components/exercise/<Name>Play.tsx` |
| Change exercise rules | `backend/app/modules/<slug>/validator.py` (+ `backend/tests/test_<slug>.py`) |
| Change attempt submission | `backend/app/modules/progress/service.py`, exercise `sessions.py` |
| Change recommendations | `backend/app/modules/recommendations/service.py` (+ `test_p7/p8_*.py`) |
| Change adaptive | `backend/app/modules/adaptive/service.py` (+ `test_adaptive.py`) |
| Change Persian UI text | `frontend/src/i18n/fa.ts` only |
| Change pricing/commerce | `backend/app/modules/billing/` + `docs/PRICING_AND_BILLING.md`; schema via `migration.py` |
| Change shared UI | `frontend/src/components/ui/` |
| Add backend tests | `backend/tests/test_<area>.py` (`pytest`) |
| Add frontend tests | Colocated `<Name>.test.tsx` (`npm test`) |
| Change schema | `backend/app/db/migration.py` + `docs/platform/DATA_MODEL.md` |
| Change deployment | `.cpanel.yml`, `backend/passenger_wsgi.py`, `docs/DEPLOYMENT.md` |

## 7. Generated / do-not-edit-manually

- `frontend/dist/` — committed prebuilt bundle; regenerate via `npm run build`, never hand-edit.
- `frontend/node_modules/`, `backend/.venv/` — tool installs, never committed logic.
- `__pycache__/`, `*.pyc` — interpreter cache.
- `backend/microchess.db`, `*.db`, `.env` files — local/production state and secrets; gitignored, never copied by deploys.
- `frontend/qa/*.cjs` — manual Puppeteer scripts, not CI gates.

## 8. Quality gates

- Backend: `pytest` (from `backend/`). Add focused tests for rules, scoring, rating.
- Frontend: `npm run typecheck` and `npm run build` (from `frontend/`); `npm test` for vitest.
- Docs-only changes (like this file) need no gates; verify paths instead.

## 9. Key docs (don't duplicate them here)

- `docs/ARCHITECTURE.md` — patterns; `docs/platform/DATA_MODEL.md` — schema;
  `docs/PRICING_AND_BILLING.md` — commerce (plans, billing, coupons);
  `docs/EXERCISES.md` — exercise roadmap; `docs/platform/IMPLEMENTATION_STATE.md` —
  verified phase state; `docs/DEPLOYMENT.md` + `docs/platform/CPANEL_DEPLOYMENT.md` —
  runbook; `docs/DESIGN_SYSTEM.md` — visual tokens; `docs/API.md`,
  `docs/platform/API_CONTRACTS.md` — contracts; `docs/SETUP.md`, `docs/TESTING.md`,
  `docs/CONFIGURATION.md` — environment and workflow.
