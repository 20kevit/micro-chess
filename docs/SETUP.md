# Development Setup

Prerequisites: Python 3.12+, Node 18+, Git.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[test]"
cp .env.example .env
uvicorn app.main:app --reload
```

The API is then at `http://localhost:8000` (`GET /health`
returns `{"status":"ok"}`). Dependencies are declared in
`backend/pyproject.toml` (`requires-python >= 3.12`); the `[test]`
extra adds `pytest` and `httpx`.

## Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The app is then at `http://localhost:5173`. The Vite dev server
proxies `/api` to `http://localhost:8000` (`frontend/vite.config.ts`),
so the default `VITE_API_BASE_URL=http://localhost:8000` also works
directly. See `docs/CONFIGURATION.md` for the variables.

## Seed puzzles

Fresh databases are playable only after seeding. From `backend/`
(with the venv active), one command per exercise module:

```bash
python -m app.modules.piece_recognition.seed
python -m app.modules.legal_destinations.seed
python -m app.modules.captures.seed
python -m app.modules.undefended_pieces.seed
python -m app.modules.give_check.seed
python -m app.modules.get_out_of_check.seed
python -m app.modules.pathfinding.seed
python -m app.modules.pathfinding_obstacles.seed
python -m app.modules.balance_scale.seed
python -m app.modules.material_comparison.seed
python -m app.modules.pin.seed
python -m app.modules.chinese_board.seed
python -m app.modules.checkmate.seed
python -m app.modules.blindfold_square_vision.seed
python -m app.modules.blindfold_calculation.seed
python -m app.modules.opening_traps.seed
python -m app.modules.reverse_opening.seed
python -m app.modules.trapped_pieces.seed
python -m app.modules.castling_rights.seed
```

Seeds insert published demo puzzles (archiving legacy rows, never
hard-deleting history). Seeded answers stay server-side; puzzle
endpoints never expose them.

## First admin account

```bash
cd backend
python -m app.cli create-admin <username>
```

The command prints a one-time password. Production bootstraps
require the additional `--confirm-production` flag
(see `backend/app/cli.py`).

## Database

The dev database is SQLite at `backend/microchess.db`
(`DATABASE_URL=sqlite:///./microchess.db`, gitignored). Schema is
managed by idempotent `ensure_schema`
(`backend/app/db/migration.py`, currently `SCHEMA_VERSION = 17`):
it runs on startup, upgrades older databases preserving data, and
refuses to boot on a newer-than-code database. No manual migration
step exists; PostgreSQL later is a `DATABASE_URL` change only.

## Clean dev reset

Stop the server, delete the gitignored `backend/microchess.db`,
restart, and re-run the seeds above. Production data is never
touched by this flow. On a deployment host each runtime keeps its own
`.env` and database, and beta must never use the production database —
see `docs/DEPLOYMENT.md`.
