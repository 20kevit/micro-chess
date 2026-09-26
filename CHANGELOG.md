# MicroChess Changelog

Deployment and platform changes. Product behavior is documented
per phase in `docs/platform/IMPLEMENTATION_STATE.md`.

## 2026-09-26 — Public repository sanitization (documentation only)

No application behavior changed. No application source, test, database,
or runtime file was modified.

* Host-specific operational detail was removed from the tracked
  documentation: real filesystem paths, service accounts, service unit
  names, loopback ports, backup locations, ACME/certificate paths,
  reverse-proxy vhost paths, and references to unrelated services on the
  same host. `docs/DEPLOYMENT.md` now uses neutral placeholders
  (`<PROJECT_ROOT>`, `<PRODUCTION_SERVICE>`, `<BETA_SERVICE>`,
  `<INTERNAL_PORT>`, `<APP_USER>`, `<BACKUP_ROOT>`, `<SERVER_IP>`).
* `ops/deploy.sh` no longer contains host values. It resolves its
  layout from its own location and reads paths, unit names, ports, and
  database files from a private, never-committed env file
  (`MICROCHESS_*`), failing closed with a clear error when a value is
  missing instead of guessing. No deployment invariant changed.
* `AGENTS.md` now states the public-repository rule for agents: keep
  host detail out of tracked files, and keep operator-only detail in a
  private runbook outside the repository.
* No credential, token, key, or password was found in the tracked tree.
  The existing `.gitignore` rules for `.env` and `*.db` remain the
  primary control.
* The retired cPanel artifacts (`.cpanel.yml`, `backend/passenger_wsgi.py`,
  `backend/lswsgi`, `docs/platform/CPANEL_DEPLOYMENT.md`) are unchanged:
  they describe a different, retired hosting account, and
  `backend/tests/test_passenger_wsgi.py` asserts against their content.

## 2026-09-25 — Single-host deployment architecture (infrastructure only)

No application behavior changed. This entry records the move to a
single-host, two-runtime deployment and the documentation that now
describes it.

* Production is served from a single host: Nginx, as a reverse proxy,
  fronts two independent Uvicorn runtimes — one production service and
  one beta service — each with its own non-root service account,
  virtualenv, `.env`, and SQLite database. Each binds to loopback only;
  Nginx is the single public entry point.
* `repo/` is the only Git working tree. `beta/` and `production/` are
  runtime deployments, not repositories, and are never hand-edited.
* `main` is the only permanent branch. `master` and the two superseded
  feature branches are gone; the one commit unique to the abandoned P11
  SMS line is preserved as the tag `archive/p11-sms-kavenegar-status`.
* `ops/deploy.sh` is the deployment helper. It refuses a dirty working
  tree, deploys the committed tree via `git archive`, requires an
  explicit commit for production, takes a verified database backup
  first, replaces code paths only, and health-checks the result.
* `.gitignore` now covers runtime secrets and SQLite artifacts
  (`.env`, `*.db`, `*.sqlite`, `*.sqlite3`, and WAL/journal sidecars)
  in the tracked tree instead of a local-only exclude file.
* The cPanel push deployment is retired. `.cpanel.yml`,
  `backend/passenger_wsgi.py`, and `docs/platform/CPANEL_DEPLOYMENT.md`
  are kept for the historical record and are clearly marked as such.
* `docs/DEPLOYMENT.md` is now the canonical deployment and operations
  reference. AGENTS.md, README, CONFIGURATION, SETUP, TESTING,
  ARCHITECTURE, REPOSITORY_MAP, SECURITY, and the platform architecture
  map were synchronised with it.
* Telegram verification remains disabled; production messaging-bot
  credentials remain in production only.

### Known limitation

TLS is not installed. The ACME HTTP-01 webroot is configured on every
vhost, but certificate validators time out reaching this host on port
80, so no certificate can be issued from here yet. Both domains are
served over plain HTTP until inbound 80/443 is reachable from the
validation networks. Details in `docs/DEPLOYMENT.md` section 9.

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
