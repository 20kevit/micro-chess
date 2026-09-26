# MicroChess

Mobile-first educational chess exercise platform for children.
Persian-first, RTL by default. The backend is authoritative for
validation, scoring, and rating — the frontend only renders boards
and transports answers.

## Status

Active development. Nineteen exercises are registered and playable
(see `docs/EXERCISES.md` for the official roadmap): fourteen with
full practice + 60-second speed modes, five as practice/attempt
play from seeded positions (no speed clock yet). Account, training,
admin, analytics, and deployment subsystems are implemented and
covered by tests — see `docs/platform/IMPLEMENTATION_STATE.md`
for the verified phase-by-phase state.

## Features (implemented)

- **Exercises** — 19 registered validators: piece recognition,
  legal destinations, captures, undefended pieces, giving check,
  get out of check, pathfinding (+ obstacles), balance scale,
  heavier side, pin, memorization board, blindfold square vision,
  blindfold calculation, trapped pieces, plus checkmate,
  mental opening, reverse opening, and castling rights from
  seeded positions.
- **Authoritative play loop** — per-exercise practice endpoints
  plus prepare-then-clock speed sessions; answers never leave
  the server before submission.
- **Accounts & roles** — register/login, JWT sessions, guest
  sessions, active-role switching (player/coach/parent/admin).
- **Training platform** — attempt history, per-exercise ratings,
  gamification (XP/streaks/achievements), adaptive training,
  coach/parent relationships and assignments.
- **Admin & content** — admin panel API, puzzle lifecycle
  (publish/archive, answers immutable once published), content
  generators, analytics, support tickets, in-app notifications.
- **Deployment** — single-host, two-runtime deployment (beta then
  production) driven by explicit Git commits; FastAPI serves the
  prebuilt frontend with SPA fallback. See `docs/DEPLOYMENT.md`.

## Architecture (short)

```text
frontend/  React + Vite + TS + Tailwind, RTL Persian shell
backend/   FastAPI + SQLAlchemy + Pydantic, modular by responsibility
docs/      product + architecture + api + exercises + platform
```

- `frontend/` never decides correctness.
- Standard chess rules live only in `backend/app/modules/chess_engine/`
  (python-chess wrapper); exercise-specific rules live in that
  exercise's validator, registered in
  `backend/app/modules/exercises/registry.py` — no per-exercise
  branches in the core attempt flow.
- Details: `docs/ARCHITECTURE.md` (exercise pipeline) and
  `docs/platform/ARCHITECTURE.md` (platform subsystems).

## Tech stack

- Backend: Python ≥3.12, FastAPI, SQLAlchemy, Pydantic,
  python-chess, SQLite (PostgreSQL-ready via `DATABASE_URL`).
- Frontend: React 18, Vite 6, TypeScript, Tailwind CSS v4,
  React Router 6, self-hosted Vazirmatn font.
- Production: a single host running two independent FastAPI/Uvicorn
  runtimes (beta and production) behind Nginx as a reverse proxy,
  serving the prebuilt `frontend/dist/` from `backend/static/`. The
  legacy cPanel/Passenger deployment is retired; see
  `docs/DEPLOYMENT.md`.

## Local setup

Prerequisites: Python 3.12+, Node 18+.

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[test]"
cp .env.example .env
uvicorn app.main:app --reload   # http://localhost:8000, health at /health
```

```bash
# Frontend (second terminal)
cd frontend
npm install
cp .env.example .env
npm run dev                   # http://localhost:5173, /api proxied to :8000
```

Seed demo puzzles (from `backend/`, one module per exercise, e.g.):

```bash
python -m app.modules.piece_recognition.seed
python -m app.modules.pin.seed
```

Full guide (environment variables, database, all seed modules,
clean dev reset): `docs/SETUP.md`.

## Tests

```bash
cd backend && pytest
cd ../frontend && npm run typecheck && npm run build && npm test
```

What each gate covers: `docs/TESTING.md`.

## Frontend build

```bash
cd frontend
npm ci
VITE_API_BASE_URL= npm run build   # empty => same-origin /api/v1/...
```

`frontend/dist/` is intentionally committed: it is the production
artifact for push deployment (no server-side build on the host).

## Deployment (overview)

`git push` to `main` → the deployment host installs the committed tree
into the beta runtime → verify `beta.microchess.ir` → deploy that exact,
tested commit to the production runtime.

```text
GitHub main
   ↓
<PROJECT_ROOT>/repo           ← only Git working tree (source of truth)
   ↓  ops/deploy.sh beta
<PROJECT_ROOT>/beta           ← beta environment (beta.microchess.ir)
   ↓  verify, then promote the tested commit
<PROJECT_ROOT>/production     ← production environment (microchess.ir)
```

Alongside them sits `<PROJECT_ROOT>/private/`, the operator-only
configuration directory (host paths, service names, ports, backup
locations, and the private runbook). It is a sibling of `repo/`, so it is
outside the Git working tree and is never committed or pushed.

`beta/` and `production/` are runtime deployments, not Git repositories,
and are never hand-edited. Each has its own service, port, database, and
`.env`. Host paths, service names, ports, and backup locations are
operator-side configuration and are intentionally not in this public
repository. Architecture and principles: `docs/DEPLOYMENT.md`
(canonical).
`docs/platform/CPANEL_DEPLOYMENT.md` is the retired cPanel runbook, kept
for the historical record only.

## Documentation

- Setup / testing / configuration / deployment:
  `docs/SETUP.md`, `docs/TESTING.md`, `docs/CONFIGURATION.md`, `docs/DEPLOYMENT.md`
- Product & architecture: `docs/PRD.md` (original),
  `docs/platform/PRODUCT_SCOPE.md` (current),
  `docs/ARCHITECTURE.md`, `docs/platform/ARCHITECTURE.md`
- API: `docs/API.md` (implemented endpoints),
  `docs/platform/API_CONTRACTS.md` (conventions)
- Exercises: `docs/EXERCISES.md` (roadmap, single source of truth),
  `docs/exercises/` (per-exercise specs)
- Platform state & runbooks: `docs/platform/IMPLEMENTATION_STATE.md`,
  `docs/platform/SECURITY.md` (the cPanel runbook
  `docs/platform/CPANEL_DEPLOYMENT.md` is historical only)
- Design: `docs/DESIGN_SYSTEM.md`
- Changes: `CHANGELOG.md`

## Roadmap

Near term (blocked only on an admin position-entry workflow):
content expansion for checkmate, mental opening, reverse opening,
and castling rights. Explicitly deferred: PostgreSQL migration
(config-only when it happens), Glicko-2 rating, TTS provider.
Exercise numbering and status: `docs/EXERCISES.md`;
platform phases: `docs/platform/IMPLEMENTATION_STATE.md`.

## Contributing

See `CONTRIBUTING.md` — setup, quality gates (`pytest`,
`typecheck`, `build`), and agent/architecture boundaries
(`AGENTS.md`). UI text is Persian; code, comments, commits,
and docs are English.

## License

No license file is present yet. Until the maintainer adds one
(e.g. MIT), the code is not offered for reuse.
