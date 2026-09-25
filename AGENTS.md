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

## 7. Where things live (VPS)

Open with the workspace at `/opt/projects/micro-chess` so all three
directories below are inside the workspace boundary.

```text
repo/        ONLY Git working tree. Source of truth. Edit here.
beta/        Runtime deployment (beta.microchess.ir).  NOT a Git repo.
production/  Runtime deployment (microchess.ir).      NOT a Git repo.
```

- `main` is the only permanent branch. Push to `main`; no other branch
  becomes permanent.
- **Never hand-edit `beta/` or `production/`.** They are deploy outputs;
  an edit there is lost on the next deploy. Change `repo/`, then deploy.
- Deploy with `repo/ops/deploy.sh` (`beta` | `prod <commit>` | `status` |
  `rollback`). Production takes an explicit, already-betatested commit.
- `DATABASE_URL` is relative to each unit's working directory, which is
  what keeps the two databases apart. **Never** point beta at
  `production/backend/microchess.db`, and never run tests against the
  production database. Use a disposable database.
- `.env` files, databases, backups, certificates, and keys are never
  committed and never printed. Only `*.example` templates are tracked.
- Telegram verification stays disabled. The production Bale bot stays in
  production; do not copy its credentials into beta.
- Infrastructure change is not done until it is verified: run the
  service, check the health endpoint, and confirm the real domain
  answers. Do not touch unrelated projects, services, or sites on this
  host (`/opt/projects/fide-service`, `xray`, `cups`, `xrdp`, and the
  default Nginx site are out of scope).

## Repository Map

For a current high-level map of the repository, major domains, entry points,
and common change locations, read:

`docs/REPOSITORY_MAP.md`

Use it as a navigation aid, then inspect the actual source files before making changes.
The map is a guide, not a substitute for repository evidence.
