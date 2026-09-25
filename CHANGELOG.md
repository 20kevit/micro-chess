# MicroChess Changelog

Deployment and platform changes. Product behavior is documented
per phase in `docs/platform/IMPLEMENTATION_STATE.md`.

## 2026-09-25 — P13/P13.1 admin and content lifecycle hardening

* Completed the Admin control center across content, exercises, review,
  users, commerce, analytics, audit, support, and system health.
* Exercise-local generators and seeds now persist validated, unpublished
  candidates with provenance and lifecycle history; player issuance fails
  closed until an administrator explicitly publishes reviewed content.
* Direct construction with `is_published=true` no longer auto-enters the
  published lifecycle state.

### Verification

* Backend: `1501 passed, 1 skipped`.
* Frontend: `npm ci`, `npm run typecheck`, `npm test -- --run`
  (60 files / 430 tests), and `npm run build` pass on Node 22.23.3.

## 2026-09-23 — Exercise & Content Management System (Phase 12)

Admin is now a professional content-management surface; no database
access, SQL, or code changes are needed for normal content operations.
No migration, no new tables, no new capabilities.

### Added (backend, thin routes over `admin/content.py`)

* Typed answer contracts for all 19 exercise validators
  (`GET /admin/exercises/{slug}/answer-contract`).
* Authoritative unsaved-content validation
  (`POST /admin/puzzles/preview-validate`, never writes).
* Lifecycle-safe bulk ops (`POST /admin/puzzles/bulk`, max 50,
  per-item gates, reason required for destructive actions).
* Exercise creation gated on a registered validator
  (`POST /admin/exercises`, capability `exercises.create`).
* Per-exercise quality, learning, and generator endpoints;
  global content health (`GET /admin/content-health`);
  per-puzzle usage (`GET /admin/puzzles/{id}/usage`).
* Richer puzzle listing: difficulty/source/search/rating filters
  plus sorting.
* Editing meaning of validated/reviewed/approved content applies
  the edit and demotes to draft (`content_edited`, audited);
  published/retired/rejected/quarantined stay immutable.

### Added (frontend, Persian RTL)

* Exercise Workspace (`/admin/exercises/:slug`, 9 tabs), Puzzle
  Library (`/admin/puzzles`, server-side paging/filtering/bulk),
  Puzzle Detail (`/admin/puzzles/:id`), Puzzle Editor
  (`/admin/puzzles/new`, `/admin/puzzles/:id/edit`) with a
  professional Board Editor and typed Answer Editors, Content
  Health (`/admin/content-health`), exercise creation form,
  review-queue deep links, and product-insight workspace links.

### Tests

* `backend/tests/test_phase12_content.py` (22 cases); full backend
  suite: 1501 passed, 1 skipped.
* Frontend: `tsc`, production build, and full vitest suite
  (60 files / 430 tests) pass.

## 2026-09-14 — Passenger fork-safety fix (`1816bdc`)

Live symptom on microchess.ir: requests reached the WSGI layer but
no response was ever written (LiteSpeed logged `200 0`, clients
timed out).

### Fixed

* `backend/passenger_wsgi.py` builds the `a2wsgi.ASGIMiddleware`
  lazily, keyed by `os.getpid()`. `ASGIMiddleware` spawns an asyncio
  event-loop thread in its constructor, but LiteSpeed mod_lsapi
  pre-forks workers (`LSAPI_CHILDREN`) that inherit only a fork-time
  thread — the eager instance deadlocked on the first `next()` of
  the WSGI generator. Each forked worker now constructs its own
  live loop thread on first request.
* The venv `site-packages` (plus `lib64` for binary wheels such as
  pydantic-core) are added to `sys.path`, covering LiteSpeed's own
  interpreter (`/opt/alt/python312`).
* Verified live after the fix: `/health` → `200 {"status":"ok"}`,
  `/` → SPA index over HTTPS; `backend/tests/test_passenger_wsgi.py`
  passes.

## 2026-09-13 — Production account paths (`5cefa02`)

### Fixed

* `.cpanel.yml` deployment paths pointed at `/home/kevitir/...`;
  the operator account is `microche`. The venv `pip` invocation now
  targets `/home/microche/virtualenv/microchess/backend/3.12/bin/pip`,
  and all deployment paths use `/home/microche/...`
  (see `docs/platform/CPANEL_DEPLOYMENT.md`).

## 2026-09-13 — Prebuilt-frontend push deployment

Commits `a8d4d57`, `c72e74b`, `d2bf352`, `cac55fa`.

### Added

* FastAPI now serves the prebuilt frontend from `backend/static/`
  with SPA fallback (`backend/app/core/frontend.py`): `/api/*` keeps
  the JSON 404 contract, existing static assets serve with
  deterministic Content-Types, `/` and all frontend routes return
  `index.html`.
* `frontend/dist/` (~1 MB, content-hashed) is committed to Git as
  the production artifact enabling `git push`-only deployment.
* `backend/tests/test_spa_frontend.py` (13 tests): fallback, asset
  serving, API precedence, traversal isolation, committed-artifact
  production safety (no dev URLs).
* Push-deployment `.cpanel.yml`: committed bundle →
  `backend/static/`, idempotent venv `pip install` on every deploy,
  code-path-only replacement (beside-the-code `.env`/database files
  survive), `restart.txt` reload, no Node/npm on the server.

### Notes

* The frontend build happens locally because the current hosting
  environment imposes a process/thread limitation that makes esbuild
  unreliable. This is a hosting-specific operational constraint, not
  a MicroChess architecture limitation; a future host can regain
  server-side builds via `.cpanel.yml` alone.
* Diagnosis + log retrieval steps for the HTTP 500s seen at
  implementation time are in `docs/platform/CPANEL_DEPLOYMENT.md`
  section 13.

## Phase 13 — cPanel deployment readiness

* Passenger WSGI adapter (`backend/passenger_wsgi.py`, `a2wsgi`
  bridge) with lifespan-preserving startup; deterministic
  `backend/requirements.txt` mirror of `backend/pyproject.toml`;
  finalized `.cpanel.yml` with `restart.txt` reload.
  (Historical note: Phase 13 records used the `kevitir` account
  paths; the current account is `microche` — fixed 2026-09-13/14
  above.)

## Phase 12 — Beta readiness

* Active-role sessions with login role selection and switching;
  admin bootstrap CLI (`python -m app.cli create-admin`); initial
  cPanel deployment configuration.
