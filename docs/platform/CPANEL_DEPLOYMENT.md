# MicroChess — cPanel Deployment (prebuilt frontend)

This document is the single operator reference for deploying MicroChess
on the `microche` cPanel shared-hosting account. Code references are
VERIFIED FROM REPOSITORY; anything the agent cannot observe from the
repository is marked MUST BE VERIFIED ON THIS CPANEL ACCOUNT.

## 1. Deployment model

Push deployment (the model cPanel officially prefers over pull):

```text
local:  npm ci && npm run build (+ tests) → git commit → git push
  ↓  cPanel-managed repository receives via post-receive hook
  ↓  .cpanel.yml tasks run with the clone as working directory
  ↓  production application under $DEPLOYPATH
```

The pull fallback (`Update from Remote` + `Deploy HEAD Commit`) runs the
same `.cpanel.yml`, so both triggers produce the identical result. After
pushing, the operator only confirms the site responds (section 12) —
no SSH, no manual build, no file copy, no manual `pip install`.

## 2. Paths and application wiring

Operator-confirmed values (used verbatim in `.cpanel.yml`):

```text
Git repository (cPanel-managed clone — NEVER deploy into it):
  /home/microche/repositories/micro-chess

Deployment root (DEPLOYPATH):
  /home/microche/microchess

Backend (Python Application Root):
  /home/microche/microchess/backend

Startup File (relative to the Application Root):
  passenger_wsgi.py

Entry Point (WSGI callable):
  application

Python virtualenv (operator-confirmed):
  /home/microche/virtualenv/microchess/backend/3.12   (Python 3.12.14)

Domain:
  https://microchess.ir   (MUST BE VERIFIED ON THIS CPANEL ACCOUNT)
```

The prebuilt frontend is served by FastAPI itself (section 8), so no
document-root upload and no separate static hosting are involved.

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
fails otherwise.

`.cpanel.yml` runs this on EVERY deploy:

```text
/home/microche/virtualenv/microchess/backend/3.12/bin/pip install -r backend/requirements.txt
```

`pip install -r` without `--upgrade` is idempotent: satisfied
requirements are skipped, so an unchanged dependency set is a cheap
no-op and a changed one installs automatically — no manual `pip`
step in normal deployments. A wrong venv path fails the deploy loudly
instead of booting half-installed (fail fast, enforced by test).

## 5. Environment variables (operator checklist)

`.env` is never committed and never copied by `.cpanel.yml`. Configure
these in cPanel's Python-App environment (values are operator secrets —
nothing is invented here):

```text
ENVIRONMENT=production
DATABASE_URL=<production database URL, see section 6>
JWT_SECRET=<long random secret, REQUIRED — boot refuses the dev default>
CORS_ORIGINS=["https://microchess.ir"]
LOG_LEVEL=INFO
RATE_LIMIT_ENABLED=true
AUTH_RATE_LIMIT_PER_MINUTE=30
```

VERIFIED FROM REPOSITORY (`backend/app/core/config.py`,
`backend/.env.example`): with `ENVIRONMENT=production` and the default
`JWT_SECRET`, the process fails fast at startup (safe, loud). Debug
mode does not exist in the codebase; CORS is env-driven. The deploy
script never wipes the backend directory itself, so a `.env` file
living beside the code survives every deploy — but the recommended
location remains outside the replaced code paths (MUST BE VERIFIED ON
THIS CPANEL ACCOUNT where the production `.env`/database currently
live).

Frontend build-time variable (`frontend/.env.example`,
`frontend/src/api/client.ts:55`): `VITE_API_BASE_URL` is read as
`import.meta.env.VITE_API_BASE_URL ?? ""`. The production build sets it
**empty**, so the client uses relative `/api/v1/...` URLs on the same
origin and no development URL can leak into the artifact. A committed
regression test (`test_committed_dist_is_production_safe`) fails the
suite if any future `dist/` contains `localhost`/`127.0.0.1`.

## 6. Database strategy

VERIFIED FROM REPOSITORY (`backend/app/db/session.py`,
`backend/app/db/migration.py`, `backend/.env.example`):

* Schema is managed by idempotent `ensure_schema` (currently
  `SCHEMA_VERSION = 11`); fresh databases boot to v11, older databases
  upgrade with data preserved; newer-than-code databases refuse to boot.
* Models use only portable SQLAlchemy column types (a future
  PostgreSQL move stays config + `DATABASE_URL`).
* The local dev database (`backend/microchess.db`) is gitignored and is
  NEVER copied by `.cpanel.yml`.

The deploy replaces only `backend/app`, `backend/static`,
`backend/__pycache__`, and `docs` — never the backend directory
itself and never any `*.db` file (enforced by test). First boot creates
and stamps the schema automatically via `run_startup()`; no manual
migration step, no destructive operations, ever.

## 7. Frontend build (local only)

> Frontend build currently happens locally because the current hosting
> environment imposes a process/thread limitation that makes esbuild
> unreliable. This is a hosting-specific operational constraint, not a
> MicroChess architecture limitation.

VERIFIED FROM REPOSITORY (`frontend/package.json`,
`frontend/vite.config.ts`): `npm run build` = `tsc --noEmit && vite
build`; no custom `base` (output assumes domain-root serving, which the
section-8 design satisfies); the dev server proxy (`/api →
localhost:8000`) never affects production output.

Procedure (developer machine, per release that touches the frontend):

```text
cd frontend
npm ci                        # lockfile-exact, deterministic (lockfileVersion 3, tracked)
VITE_API_BASE_URL= npm run build   # empty => same-origin relative /api/v1/...
```

The ~1 MB `frontend/dist/` output (content-hashed filenames, absolute
`/assets/...` references) is COMMITTED to Git — deliberately (see
`.gitignore` header note). Rationale, all verified: the bundle is
small, reproducible from the tracked lockfile (identical content yields
identical hashes), and committing it is what makes `git push` alone
sufficient with no server-side build and no manual copy. `node_modules/`
and `frontend/.env` stay ignored and are never deployed.

If a future host allows reliable server-side builds, only `.cpanel.yml`
(regain `npm ci` + `npm run build`, stop deploying committed `dist/`)
and the dist-in-git decision change — no frontend/backend rewrite is
needed, by design (no Node runtime exists in production code).

## 8. Frontend serving (FastAPI + SPA fallback)

Decision record (evidence-based): the repository contains no `/` route
and no static serving, and whether Passenger on this account can share
the domain root between the document root (static) and the Python app
(API) cannot be determined from the repository. The robust choice that
depends on nothing unverified is therefore:

```text
FastAPI
 ├── /api/v1/*        → API routers (unchanged)
 ├── /health          → unchanged
 ├── existing static  → served from backend/static (/assets/*, fonts, SVGs)
 └── everything else  → index.html (React Router owns the route)
```

Implementation (VERIFIED FROM REPOSITORY): `backend/app/core/frontend.py`
(`mount_spa`, mounted LAST in `backend/app/main.py` — API routers,
`/health`, and FastAPI's own `/docs`/`/openapi.json` always take
precedence). The directory resolves relative to the package
(`backend/static` in production; absent locally, where mounting is a
no-op and API-only behavior is byte-identical). No production paths
exist in application code.

Contract (proven by `backend/tests/test_spa_frontend.py`, 13 tests):

```text
/api/* → backend API (unknown API paths keep the JSON 404 envelope)
/assets/app.<hash>.js (existing file) → 200 with deterministic Content-Type
/ , /login , /exercises/... , /admin/... → 200 index.html (direct refresh works)
traversal attempts → can never escape the bundle directory
```

## 9. What .cpanel.yml does (per deploy)

1. Sets `DEPLOYPATH` + `VENV` (operator-confirmed, no guessing).
2. Replaces code paths only: `backend/app`, `backend/static`,
   `backend/__pycache__`, `docs` (backend dir itself is never wiped).
3. Copies `passenger_wsgi.py`, `pyproject.toml`, `requirements.txt`,
   `.env.example` (reference only) into `backend/`.
4. Copies committed `frontend/dist/` → `backend/static/` (whole-dir
   replace + hashed filenames ⇒ no stale assets).
5. Copies `docs`, `README.md`, `AGENTS.md`.
6. Removes the legacy Phase-13 `$DEPLOYPATH/frontend` source copy.
7. Runs venv `pip install -r requirements.txt` (idempotent).
8. Touches `backend/tmp/restart.txt` (Passenger reload, once per deploy).

Contains no `npm`/`node`, no `frontend/src`, no secrets handling.

## 10. Deploy workflow (operator)

```text
1. npm ci
2. npm run build          (only when the frontend changed; VITE_API_BASE_URL empty)
3. tests                  (backend pytest + frontend tests/typecheck)
4. git commit              (includes rebuilt frontend/dist/ when changed)
5. git push
6. cPanel automatic deployment (post-receive hook runs .cpanel.yml)
```

Pull fallback (`Update from Remote` + `Deploy HEAD Commit`) runs the
same script with the identical result.

## 11. Rollback

The deploy is code-only (DB/env untouched; migrations additive), so
rollback is a revert + push (+ pull fallback if auto-deploy is off):

1. Identify the known-good commit (`git log --oneline` locally).
2. `git revert <sha>` (preferred — linear, auditable) + push; the
   matching `frontend/dist/` rebuilds into the same commit, so no
   separate frontend rollback step exists.
3. Passenger reloads via `restart.txt`; run the smoke test (section 12).
   Database needs no action.

## 12. Post-deployment smoke test

```text
curl -I https://microchess.ir/                  → 200, text/html
curl -I https://microchess.ir/login             → 200, text/html (SPA fallback)
curl -I https://microchess.ir/api/v1/exercises  → 200, application/json
```

Content checks: `/` serves the Persian bundle (`میکروچس` in body);
`/api/v1/exercises` returns a JSON list (after content seeds), never
HTML. Then: register → login → `/users/me` (200 with `active_role`) →
player on `/admin/dashboard` (403).

The full 34-check fresh-DB matrix (register → roles → relationships →
attempt → rating → gamification → support → notifications) is automated
locally; see IMPLEMENTATION_STATE.md Phase 13 evidence.

## 13. Live failures and their fixes (evidence)

### 500 → `200 0` hang → fork-safety fix

Observed 2026-09-12 (fetched live): `/`, `/health`, and
`/api/v1/exercises` ALL return HTTP 500.

VERIFIED FROM REPOSITORY: `/health` is a static dict with no DB, env,
or auth dependency — a booted app cannot 500 on it, and `/` (no route)
would be a JSON 404, not a 500. A blanket 500 therefore means the
Passenger application fails at boot/request-entry level, not in any
route. Ordered suspects (cannot be distinguished without the real log):

1. Deployed code predates `passenger_wsgi.py` (the on-host clone was
   reported possibly behind GitHub) → startup file missing → every
   request 500s.
2. `run_startup()` raises at import: `ENVIRONMENT=production` with the
   default `JWT_SECRET` (fail-fast RuntimeError), `init_db()` failure
   (unwritable/misconfigured `DATABASE_URL`), or a missing venv package
   (e.g. `a2wsgi` never installed after Phase 13 added it).
3. venv/Python mismatch or file permissions on the host.

RESOLVED 2026-09-14. The boot-level symptoms were real but the final
hang had a different root cause, diagnosed live via WSGI probes:

* Requests DID reach the WSGI layer (`passenger_wsgi.application` ran;
  a `PRE-WSGI` probe logged per request), yet no HTTP response was ever
  written — LiteSpeed logged `200 0` and the client timed out. The
  worker accepted the connection and then a forked child stalled in
  `a2wsgi`'s first `next()` on the WSGI generator.
* Root cause: `a2wsgi.ASGIMiddleware` constructs an asyncio event-loop
  **thread** in its `__init__`. LiteSpeed mod_lsapi on this host uses
  pre-forked workers (`LSAPI_CHILDREN`, `LSAPI_KEEP_LISTEN=2`); the
  master imports the module at startup, then each request is served by
  a process **forked** from the master. Threads do not exist in the
  child after `fork()`, so `a2wsgi`'s
  `run_coroutine_threadsafe(...).result()` deadlocked forever on the
  first generator `next()`.
* Fix (committed): `backend/passenger_wsgi.py` builds the middleware
  lazily, keyed by `os.getpid()`. Each forked worker constructs its own
  live loop thread on first request. Also added explicit vitualenv
  `site-packages` (incl. `lib64` for binary wheels) to `sys.path`.
  After the fix `/health` → `200 {"status":"ok"}`, `/` → the SPA
  index.html, over HTTPS and HTTP/2.
* The deployed `.cpanel.yml` pip path was still `/home/kevitir/...`;
  the operator account is `microche` (fixed in the same commit).

MUST BE VERIFIED ON THIS CPANEL ACCOUNT — retrieve the real error:

```text
a. cPanel → Setup Python App → the app → its stderr log file path;
   read the newest traceback (or Metrics → Errors).
b. git -C ~/repositories/micro-chess log --oneline -3   (is passenger_wsgi.py deployed?)
c. ls ~/microchess/backend                               (is the new layout live?)
d. ~/virtualenv/microchess/backend/3.12/bin/pip list | grep -i -E "a2wsgi|fastapi"
e. Confirm ENVIRONMENT / DATABASE_URL / JWT_SECRET are set (values stay secret).
```

The new deployment removes whole suspect classes (deps install on every
deploy; committed bundle; backend-served frontend), but the first
deploy must still be followed by the section-12 smoke test.

## 14. Security review

* `.env`, `*.db`, `.venv`, `.git`, `tests/`, `qa/`, `*.test.*`,
  `node_modules/`, `frontend/src` are never copied (explicit allowlist
  + regression test `test_cpanel_yml_deploys_adapter_safely`, extended
  for the pip + prebuilt-bundle rules).
* The committed `dist/` contains no secrets, no dev URLs (enforced by
  `test_committed_dist_is_production_safe`), no source maps beyond
  Vite defaults, and no server paths.
* No secrets, credentials, or tokens exist in `.cpanel.yml`,
  `passenger_wsgi.py`, or docs.
* Production refuses to boot with the dev JWT secret
  (`ensure_ready`, tested).
* Auth/authz/active-role/capability code is untouched by the deployment
  work; the full backend suite passes unchanged.
```
