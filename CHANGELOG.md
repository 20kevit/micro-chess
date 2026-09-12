# MicroChess Changelog

All notable deployment and platform changes. Product behavior changes
are documented per phase in `docs/platform/IMPLEMENTATION_STATE.md`.

## Unreleased (deployment architecture)

### Added

* FastAPI now serves the prebuilt frontend from `backend/static/` with
  SPA fallback (`backend/app/core/frontend.py`): `/api/*` keeps the
  JSON 404 contract, existing static assets serve with deterministic
  Content-Types, `/` and all frontend routes return `index.html`.
* `frontend/dist/` (~1 MB, content-hashed) is committed to Git as the
  production artifact enabling `git push`-only deployment.
* `backend/tests/test_spa_frontend.py` (13 tests): fallback, asset
  serving, API precedence, traversal isolation, committed-artifact
  production safety (no dev URLs).
* Push-deployment `.cpanel.yml`: committed bundle → `backend/static/`,
  idempotent venv `pip install` on every deploy, code-path-only
  replacement (beside-the-code `.env`/database files survive),
  `restart.txt` reload, no Node/npm on the server.

### Notes

* Frontend build happens locally because the current hosting
  environment imposes a process/thread limitation that makes esbuild
  unreliable. This is a hosting-specific operational constraint, not a
  MicroChess architecture limitation; a future host can regain
  server-side builds via `.cpanel.yml` alone.
* Production returned HTTP 500 on `/`, `/health`, and
  `/api/v1/exercises` at implementation time (boot-level failure;
  diagnosis + log retrieval steps in
  `docs/platform/CPANEL_DEPLOYMENT.md` section 13).

## Phase 13 — cPanel deployment readiness

* Passenger WSGI adapter (`backend/passenger_wsgi.py`, `a2wsgi`
  bridge) with lifespan-preserving startup; deterministic
  `backend/requirements.txt` mirror of `backend/pyproject.toml`;
  finalized `.cpanel.yml` with `DEPLOYPATH=/home/kevitir/microchess`
  and `restart.txt` reload.

## Phase 12 — Beta readiness

* Active-role sessions with login role selection and switching;
  admin bootstrap CLI (`python -m app.cli create-admin`); initial
  cPanel deployment configuration.
