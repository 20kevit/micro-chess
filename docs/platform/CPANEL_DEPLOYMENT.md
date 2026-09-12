# MicroChess — cPanel Deployment (Phase 13)

This document is the single operator reference for deploying MicroChess
on the `kevitir` cPanel shared-hosting account. Code references are
VERIFIED FROM REPOSITORY; anything the agent cannot observe from the
repository is marked MUST BE VERIFIED ON THIS CPANEL ACCOUNT.

## 1. Deployment model

```text
GitHub (20kevit/micro-chess, branch master)
  ↓  cPanel "Git Version Control" → Update from Remote
  ↓  Deploy HEAD Commit
  ↓  .cpanel.yml tasks run with the clone as working directory
  ↓  Production application under $DEPLOYPATH
```

## 2. Paths and application wiring

VERIFIED FROM REPOSITORY (`.cpanel.yml`, `backend/passenger_wsgi.py`):

```text
Git repository (cPanel-managed clone — NEVER deploy into it):
  /home/kevitir/repositories/micro-chess

Deployment root (DEPLOYPATH):
  /home/kevitir/microchess

Backend (Python Application Root):
  /home/kevitir/microchess/backend

Startup File (relative to the Application Root):
  passenger_wsgi.py

Entry Point (WSGI callable):
  application

Frontend bundle (built locally, uploaded as static files):
  <document-root-of-micro.20kevit.ir>  (MUST BE VERIFIED ON THIS CPANEL ACCOUNT)
```

MUST BE VERIFIED ON THIS CPANEL ACCOUNT: the exact document root that
serves `micro.20kevit.ir` (often `~/public_html` or an addon-domain
folder) and whether the Python app is mounted under the same domain
(same-origin, preferred) or a subdomain/path.

## 3. Why passenger_wsgi.py exists

cPanel runs Python apps through Passenger, which requires a synchronous
WSGI callable named `application`. MicroChess is FastAPI, i.e. ASGI, so
`app.main:app` cannot be exposed directly. `backend/passenger_wsgi.py`
bridges with `a2wsgi.asgi.ASGIMiddleware` (pure Python, maintained,
Python 3.12 compatible, no compiler needed — verified installable from
PyPI). No framework or server stack was added; the FastAPI app is
imported unchanged and wrapped, never duplicated.

Lifespan behavior (VERIFIED FROM REPOSITORY): the bridge never sends
ASGI lifespan events, so the `lifespan` in `backend/app/main.py` does
NOT run under Passenger. The startup init (logging, production config
guard, idempotent `init_db()` schema setup) therefore runs once at
process import in `passenger_wsgi.py:run_startup()`, mirroring the
lifespan. `init_db()` (`ensure_schema`) is idempotent and
non-destructive: safe on fresh and existing databases, never deletes
data, never runs per request. Under local `uvicorn` the lifespan still
runs as before (double init is a harmless no-op).

## 4. Dependencies

Source of truth: `backend/pyproject.toml` (`requires-python >= 3.12`).
cPanel mirror: `backend/requirements.txt` (same package floors; header
documents the relationship). After changing `pyproject.toml`
dependencies, update `requirements.txt` to match —
`tests/test_passenger_wsgi.py::test_requirements_mirror_pyproject`
fails otherwise. `backend/requirements.txt` is deployed by
`.cpanel.yml`; install once via cPanel's Python-App UI
(`pip install -r requirements.txt` into the app virtualenv), then only
when dependencies change — never on every deploy.

## 5. Environment variables (operator checklist)

`.env` is never committed and never copied by `.cpanel.yml`. Configure
these in cPanel's Python-App environment (values are operator secrets —
nothing is invented here):

```text
ENVIRONMENT=production
DATABASE_URL=<production database URL, see section 6>
JWT_SECRET=<long random secret, REQUIRED — boot refuses the dev default>
CORS_ORIGINS=["https://micro.20kevit.ir"]
LOG_LEVEL=INFO
RATE_LIMIT_ENABLED=true
AUTH_RATE_LIMIT_PER_MINUTE=30
```

VERIFIED FROM REPOSITORY (`backend/app/core/config.py`,
`backend/.env.example`): with `ENVIRONMENT=production` and the default
`JWT_SECRET`, the process fails fast at startup (safe, loud). Debug
mode does not exist in the codebase; CORS is env-driven (production
must list only the production origin).

Frontend build-time variable (`frontend/.env.example`,
`frontend/src/api/client.ts`): `VITE_API_BASE_URL`. For same-origin
deployment (preferred: domain serves `dist/` and proxies `/api` to the
Python app) build with it **empty/unset** — the client then uses
relative `/api/v1/...` URLs and no dev URL can leak. Only set it to an
absolute URL when the API lives on a different origin, and then add
that exact origin to `CORS_ORIGINS`.

## 6. Database strategy

VERIFIED FROM REPOSITORY (`backend/app/db/session.py`,
`backend/app/db/migration.py`, `backend/.env.example`):

* Schema is managed by idempotent `ensure_schema` (currently
  `SCHEMA_VERSION = 11`); fresh databases boot to v11, older databases
  upgrade with data preserved; newer-than-code databases refuse to boot.
* Models use only portable SQLAlchemy column types (PostgreSQL migration
  later is config + `DATABASE_URL`).
* The local dev database (`backend/microchess.db`) is gitignored and is
  NEVER copied by `.cpanel.yml`.

Operator decision (no PostgreSQL evidence exists for this account, so
nothing is assumed): use SQLite on the account with the file OUTSIDE
the cleared code dirs, e.g.
`DATABASE_URL=sqlite:////home/kevitir/microchess-data/microchess.db`
(absolute path, directory created once, backed up by the operator).
Because the file lives outside `/home/kevitir/microchess/{backend,
frontend,docs}`, redeploys (which clear only those three dirs) can
never delete production data. First boot creates and stamps the schema
automatically via `run_startup()`; no manual migration step, no
destructive operations, ever.

## 7. Frontend deployment (no on-server build)

VERIFIED FROM REPOSITORY (`frontend/package.json`,
`frontend/vite.config.ts`): the dev server proxies `/api` to
`localhost:8000`; production uses the baked `VITE_API_BASE_URL`.

Procedure (local machine, per release):

```text
cd frontend
npm install
VITE_API_BASE_URL= npm run build     # empty => same-origin relative /api/v1/...
```

Upload the resulting `frontend/dist/` CONTENTS to the domain document
root through the account's static hosting (File Manager / FTP — MUST BE
VERIFIED ON THIS CPANEL ACCOUNT). cPanel never runs `npm install` or
`npm run build` (`.cpanel.yml` contains neither; enforced by test).

## 8. Deploy workflow (operator)

1. Push to GitHub `master`.
2. cPanel → Git Version Control → `micro-chess` → Update from Remote.
3. Deploy HEAD Commit (runs `.cpanel.yml`).
4. First deploy only: create the Python App (Application Root
   `/home/kevitir/microchess/backend`, Startup File
   `passenger_wsgi.py`, Python 3.12), install
   `backend/requirements.txt` into its virtualenv, set section-5
   variables, create the data dir from section 6.
5. The deploy touches `backend/tmp/restart.txt`, reloading Passenger
   (at most once per deploy; never per request).
6. Run the post-deploy smoke test (section 10).

## 9. Rollback

cPanel Git keeps full history; the deploy is code-only (DB/env
untouched), so rollback is redeploy of a known-good commit:

1. Identify the known-good commit (`git log --oneline` locally).
2. In cPanel Git Version Control, deploy that commit (or push a revert
   to `master` and Deploy HEAD Commit — preferred, keeps history
   linear and auditable).
3. Re-upload the `frontend/dist/` built from the same commit.
4. Confirm `tmp/restart.txt` was touched (redeploy does it) so
   Passenger reloads.
5. Run the smoke test (section 10). Database needs no action:
   migrations are forward-compatible and additive.

## 10. Post-deployment smoke test

```text
GET https://micro.20kevit.ir/            -> frontend loads (Persian RTL)
GET /api/v1/exercises (via domain)       -> 200 (after content seeds)
POST /api/v1/auth/register + /auth/login -> 200, token issued
GET /api/v1/users/me                     -> 200 with active_role
GET /api/v1/admin/dashboard (player)     -> 403
```

The full 34-check fresh-DB matrix (register → roles → relationships →
attempt → rating → gamification → support → notifications) is automated
locally; see IMPLEMENTATION_STATE.md Phase 13 evidence.

## 11. Security review (Phase 13)

* `.env`, `*.db`, `.venv`, `.git`, `tests/`, `qa/`, `*.test.*`,
  `node_modules/`, `dist/` are never copied (explicit `cp` allowlist +
  regression test `test_cpanel_yml_deploys_adapter_safely`).
* No secrets, credentials, or tokens exist in `.cpanel.yml`,
  `passenger_wsgi.py`, or docs.
* Production refuses to boot with the dev JWT secret
  (`ensure_ready`, tested).
* Auth/authz/active-role/capability code is byte-identical in behavior:
  Phase 13 adds no product logic; the 1156-test backend suite
  (incl. all auth, role, relationship, and gamification tests) passes
  unchanged.
```
