# Deployment (overview)

Production runs on cPanel shared hosting (CloudLinux + LiteSpeed)
for the `microche` account. The full operator runbook is
`docs/platform/CPANEL_DEPLOYMENT.md` — this page is only the shape
of the system.

## Model: push, prebuilt frontend, Passenger backend

```text
local:  npm ci && npm run build (+ tests) → git commit → git push
  ↓  cPanel-managed repository receives via post-receive hook
  ↓  .cpanel.yml tasks run with the clone as working directory
  ↓  production application under $DEPLOYPATH
```

- The frontend arrives prebuilt as the committed `frontend/dist/`
  (content-hashed, ~1 MB). No Node/npm runs on the server: the
  current host imposes a process/thread limitation that makes
  esbuild unreliable (a hosting constraint, not an architecture
  limitation).
- FastAPI serves the bundle itself from `backend/static/` with SPA
  fallback (`backend/app/core/frontend.py`): `/api/*` keeps the JSON
  404 contract, `/` and all frontend routes return `index.html`.
- The ASGI app is exposed to Passenger through
  `backend/passenger_wsgi.py` (`a2wsgi` bridge, WSGI callable
  `application`). The middleware is constructed lazily per process
  (`os.getpid()`) because LiteSpeed mod_lsapi pre-forks workers —
  see `CHANGELOG.md` (2026-09-14) for the hang this fixed.

## Production layout (`microche` account)

```text
Git clone (cPanel-managed, never deployed into):
  /home/microche/repositories/micro-chess
Deployment root (DEPLOYPATH):
  /home/microche/microchess
Python Application Root:  /home/microche/microchess/backend
Startup File:             passenger_wsgi.py  (entry point: application)
Virtualenv:               /home/microche/virtualenv/microchess/backend/3.12
```

## Per-deploy steps (`.cpanel.yml`)

1. Replace code paths only: `backend/app`, `backend/static`,
   `backend/__pycache__`, `docs`. The backend directory itself is
   never wiped, so a `.env` or database file living beside the code
   survives every deploy.
2. Copy `passenger_wsgi.py`, `pyproject.toml`,
   `requirements.txt`, `.env.example` (reference only) into `backend/`.
3. Copy committed `frontend/dist/` → `backend/static/`
   (whole-dir replace ⇒ no stale hashed assets).
4. Idempotent venv `pip install -r requirements.txt`
   (cheap no-op unless dependencies changed; a wrong venv path fails
   loudly instead of booting half-installed).
5. Touch `backend/tmp/restart.txt` (Passenger reload, once per deploy).

Never deployed or copied: `.git`, databases, `.env` files,
`node_modules`, `frontend/src`, backend `tests/`. Rollback is
`git revert` + push; the database needs no action (migrations are
additive). Post-deploy smoke test and troubleshooting: runbook
sections 12–13.

## SSH-based GitHub access

Day-to-day deployment needs no SSH: `git push` (or cPanel's
`Update from Remote` + `Deploy HEAD Commit` fallback) is the whole
workflow. SSH is only a diagnostic tool (log retrieval, `pip list`
checks) — the exact commands are in the runbook section 13.
No secrets or private keys are stored in the repository, and none
may be added (see `SECURITY.md`).
