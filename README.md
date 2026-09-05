# MicroChess — Foundation (MVP scaffold)

Mobile-first educational chess exercise platform for children.
Persian-first, RTL by default. See `docs/` for product and architecture.

## Structure

- `frontend/` — React + Vite + TypeScript + Tailwind + React Router
- `backend/` — FastAPI + SQLAlchemy + Pydantic + python-chess (SQLite now, PostgreSQL-ready)
- `docs/` — PRD, architecture, API, exercises

## Quick start

Backend:

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[test]"
cp .env.example .env
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Seed Piece Recognition demo puzzles:

```bash
cd backend
python -m app.modules.piece_recognition.seed
```

Dev database note: tables are created with `create_all` (no migrations at this
stage), so after model columns change, stop the server, delete the gitignored
`backend/microchess.db`, restart, and re-run the seed above.

## Quality gates

```bash
cd backend
pytest

cd ../frontend
npm run typecheck
npm run build
```

## Decisions (short)

- Backend is authoritative for validation/scoring/rating. Frontend never decides correctness.
- Exercise validators plug into `exercises/registry.py`; no giant `if/elif`.
- Standard chess lives in `chess_engine/` (python-chess). Custom rules live in each exercise validator.
- Shared `puzzles.db` (optional, read-only, FEN only) feeds `positions/repository.py`; per-exercise generators build questions server-side.
- Exercise 1: practice (untimed, `POST .../next`) + speed (60s authoritative sessions); zero-target questions valid; answers never leave the server.
- Tables now: `users`, `exercises`, `puzzles`, `attempts`, `piece_speed_sessions`. Rating tables postponed.
- Puzzle answers immutable once published; archive instead of delete.
- Attempts distinguish correct/partial/wrong/timeout/skipped/abandoned + rated/practice.
- Audio is a `AudioPort` boundary only; no TTS vendor yet.
- Anonymous progress: browser localStorage now; `attempts.user_id` nullable for future transfer.
- Visual language: MicroChess Design System (`docs/DESIGN_SYSTEM.md`, tokens in `frontend/src/index.css`).

## Intentionally NOT implemented

All 20+ exercises (Piece Recognition comes as the first vertical slice later),
Glicko-2 rating, admin panel, TTS provider, analytics system.
