# AGENTS.md — Rules for AI coding agents working on MicroChess

Read this before changing code. Keep it simple and explicit.

## 1. Language

- User-facing UI text: Persian (fa). No English strings in UI.
- Code, comments, commit messages, docs: English.

## 2. Architecture boundaries

- `frontend/` NEVER decides correctness. It only renders and transports answers.
- `backend/app/main.py` and `*/router.py` are thin wiring only. No business logic there.
- Business logic lives in `*/service.py` or pure functions.
- Standard chess logic: `modules/chess_engine/` (python-chess wrapper) ONLY.
- Exercise-specific/custom rules: that exercise's validator registered in `modules/exercises/registry.py`. NEVER add `if/elif exercise_slug` chains in core flow.
- Keep separate: Exercise (type) / Puzzle (one question) / Position (FEN/data) / Attempt (one try).
- Keep separate: validation vs scoring vs rating vs feedback.
- `rating_engine/` implements the current Elo-style update (Glicko-2
  deferred). `practice` attempts MUST NOT set `rating_delta`.
- `audio/ports.py` is the TTS boundary. Do not import vendor SDKs into domain code.

## 3. Data rules

- Puzzle `answer_json` is immutable once `is_published=True` (`puzzles/service.py` enforces; test covers it).
- Never hard-delete puzzles with history. Use `archive()` (sets `is_archived`).
- `attempts` rows store raw `answer_json`; results in correct/partial/wrong/timeout/skipped/abandoned; mode in rated/practice.
- Only portable SQLAlchemy column types. No SQLite-only DDL (PostgreSQL migration must be config-only + Alembic later).
- Schema source of truth: `backend/app/db/migration.py`
  (`SCHEMA_VERSION`) + `docs/platform/DATA_MODEL.md`. Add new tables only when a feature needs them.

## 4. Frontend rules

- Mobile-first, touch-usable (min 44px targets, `touch-action: manipulation` on board).
- Page `dir` is RTL; chessboard islands are `dir="ltr"` with a-file left in White orientation.
- Chess pieces: SVG components only. NEVER Unicode chess glyphs in UI.
- Small design system in `components/ui/` (Button, Card, PageHeader, Badge, AppShell). Reuse, don't restyle per page.
- i18n via `src/i18n/`: call `t("key")`. Add Persian strings to `fa.ts`; English later.
- Anonymous progress in `src/lib/localProgress.ts` (localStorage). Server is source of truth for accounts.

## 5. Simplicity

- Do NOT add abstractions, factories, event buses, microservices, or generic frameworks.
- Prefer small explicit modules. If a change needs a new pattern, document it in `docs/ARCHITECTURE.md`.
- Do not invent product behavior. Missing exercise specs come from the user.

## 6. Verification

- Backend: `pytest` must pass. Add focused tests for chess rules, validators, scoring, rating.
- Frontend: `npm run typecheck` and `npm run build` must pass.
- Run the relevant gate before finishing any task.
