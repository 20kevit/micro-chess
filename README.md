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
- Exercise 1: practice (untimed, `POST .../next`, client prefetch buffer) +
  speed (prepare ≥20, then authoritative 60s clock, ~450ms auto-advance,
  server-rebuilt report); zero-target questions valid; per-square scoring
  (+5/−1/−2 with +5 zero-target bonus, negatives kept); self-hosted
  Vazirmatn font; answers never leave the server.
- Exercise 2 (Legal Destinations): same practice+speed architecture with a
  dynamic white-only generator (uniform target piece, deliberate blockers,
  `ignore-enemy-attacks` profile), sky-ring target highlight, identical
  per-square scoring; full spec in `docs/exercises/02-legal-destinations.md`.
- Exercise 3 (Captures): same practice+speed architecture with a dynamic
  hunter-vs-black generator (one white hunter, 3–8 black pieces, deliberate
  capturable/shielded/decoy patterns, defense explicitly irrelevant via the
  `ignore-enemy-attacks` profile), hunter highlight, identical per-square
  scoring; full spec in `docs/exercises/03-captures.md`.
- Exercise 4 (Undefended Pieces «مهره‌های بی‌دفاع»): same practice+speed
  architecture with a shared-`puzzles.db` position source (FEN only, like
  Exercise 1, bounded sampling preferring non-empty answers), no
  pre-highlight, absolute-pin-aware rule (pinned-to-King pieces never
  count, pin-to-Queen still counts, Kings never answers), identical
  per-square scoring; full spec in
  `docs/exercises/04-undefended-pieces.md`.
- Exercise 5 (Giving Check «کیش دادن»): same practice+speed architecture
  with a shared-`puzzles.db` position source (FEN only, bounded sampling
  that rejects positions with either King already in check), answer as a
  SET of arrows (every legal non-King checking move as from→to UCI:
  direct/capture/discovered/double/promotion/en-passant, Kings and
  castling never answers), reusable multi-arrow board layer
  (press-drag-release for mouse + touch, per-arrow remove/promotion,
  green/amber/red feedback), identical per-move scoring; full spec in
  `docs/exercises/05-giving-check.md`.
- Former Exercises 5 (Hanging Pieces) and 6 (Attacker/Defender Equality)
  were removed from the project; later exercises renumbered accordingly
  and Castling Rights moved to the end of the roadmap
  (see `docs/EXERCISES.md`).
- Tables now: `users`, `exercises`, `puzzles`, `attempts`, `piece_speed_sessions`,
  `legal_speed_sessions`, `capture_speed_sessions`,
  `undefended_speed_sessions`, `giving_check_speed_sessions`. Rating tables postponed.
- Puzzle answers immutable once published; archive instead of delete.
- Attempts distinguish correct/partial/wrong/timeout/skipped/abandoned + rated/practice.
- Audio is a `AudioPort` boundary only; no TTS vendor yet.
- Anonymous progress: browser localStorage now; `attempts.user_id` nullable for future transfer.
- Visual language: MicroChess Design System (`docs/DESIGN_SYSTEM.md`, tokens in `frontend/src/index.css`).

## Intentionally NOT implemented

All 20+ exercises (Piece Recognition comes as the first vertical slice later),
Glicko-2 rating, admin panel, TTS provider, analytics system.
