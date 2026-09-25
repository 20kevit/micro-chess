# Testing

## Backend

```bash
cd backend
pytest
```

Configuration: `testpaths = ["tests"]`, `pythonpath = ["."]`
(`backend/pyproject.toml`). Tests use an isolated in-memory SQLite
database with a `TestClient(app)` override
(`backend/tests/conftest.py`) — the dev `microchess.db` is never
touched.

Coverage includes chess rules and validators, scoring edge cases,
the puzzle publish/archive lifecycle, auth/roles/relationships,
ratings, gamification, support/notifications, the Passenger WSGI
adapter (`test_passenger_wsgi.py`), the SPA fallback
(`test_spa_frontend.py`, 13 tests), and the deploy-path safety
invariants. New exercise or rule changes need focused tests for
validation, scoring, and custom rules.

## Frontend

```bash
cd frontend
npm run typecheck   # tsc --noEmit
npm run build       # tsc --noEmit && vite build
npm test            # vitest run (jsdom, src/**/*.test.{ts,tsx})
```

`npm run build` must pass before committing whenever the frontend
changed: `frontend/dist/` is the committed production artifact
(see `docs/DEPLOYMENT.md`), and a regression test fails the backend
suite if a committed bundle ever contains dev URLs.

## Manual viewport QA

`frontend/qa/` holds headless Puppeteer checks (board geometry,
viewport matrix, place/replace/erase flows) for selected exercises.
They are not part of the app bundle and need both servers running:

```bash
# terminal 1: backend on :8000 (uvicorn, seeded DB)
# terminal 2: cd frontend && npm run dev   # :5173
node frontend/qa/<script>.cjs
```

The scripts expect a local Chrome/Chromium binary — adjust the
executable path at the top of the script to your machine.

## Before every commit

Run the gate for the side you touched; run both for full changes.
`AGENTS.md` section 6 states the same rule for AI agents.
