# Contributing to MicroChess

## Setup

Follow `docs/SETUP.md` (backend venv + `pip install -e ".[test]"`,
frontend `npm install`, `.env` copies, seeds, first admin).
Configuration reference: `docs/CONFIGURATION.md`.

## Language rule

- User-facing UI text: Persian (fa). No English strings in UI.
- Code, comments, commit messages, docs: English.

## Architecture boundaries (must-read: `AGENTS.md`)

- `frontend/` never decides correctness; it renders and transports answers.
- `backend/app/main.py` and `*/router.py` are thin wiring; business
  logic lives in `*/service.py` or pure functions.
- Standard chess: `backend/app/modules/chess_engine/` only.
  Exercise-specific rules: that exercise's validator, registered in
  `backend/app/modules/exercises/registry.py` — never add
  per-exercise branches to the core attempt flow.
- Puzzle `answer_json` is immutable once published; never
  hard-delete puzzles with history — archive instead.
- Only portable SQLAlchemy column types.

## Quality gates

```bash
cd backend && pytest
cd ../frontend && npm run typecheck && npm run build && npm test
```

Run the gate for the side you touched; run both for full changes.
Details: `docs/TESTING.md`. If the frontend changed, rebuild
`frontend/dist/` (`VITE_API_BASE_URL= npm run build`) and commit it —
it is the production artifact (see `docs/DEPLOYMENT.md`).

## Pull requests

- One focused change per PR; describe what was verified
  (which gates ran, which tests added).
- New exercise or rule changes need focused tests for validation,
  scoring edge cases, and custom rules.
- Never commit secrets, credentials, tokens, private keys,
  `.env` files, or database files.
- Docs live with the code: update the affected doc
  (`docs/API.md`, `docs/EXERCISES.md`, …) in the same PR, and keep
  internal links working.

## Issues

Include reproduction steps (commands, endpoint, request/response),
expected vs actual behavior, and the relevant module paths.
