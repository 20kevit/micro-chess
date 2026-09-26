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

## 7. Repository and deployment workflow

This repository is PUBLIC. Keep server-specific operational detail
(host addresses, filesystem paths, service accounts, unit names, ports,
backup locations, certificate paths) OUT of the tracked files. Use the
neutral placeholders already in `docs/DEPLOYMENT.md` (`<PROJECT_ROOT>`,
`<PRODUCTION_SERVICE>`, `<BETA_SERVICE>`, `<INTERNAL_PORT>`,
`<APP_USER>`, `<BACKUP_ROOT>`).

On the deployment host the project lives in a workspace holding three
directories:

```text
repo/        ONLY Git working tree. Source of truth. Edit here.
beta/        Runtime deployment (beta environment).  NOT a Git repo.
production/  Runtime deployment (production env.).  NOT a Git repo.
```

- `main` is the only permanent branch. Push to `main`; no other branch
  becomes permanent.
- **Never hand-edit `beta/` or `production/`.** They are deploy outputs;
  an edit there is lost on the next deploy. Change `repo/`, then deploy.
- Deploy with `repo/ops/deploy.sh` (`beta` | `prod <commit>` | `status` |
  `rollback`). Production takes an explicit, already-betatested commit
  and is never deployed automatically.
- The helper holds no host values: they come from a private, uncommitted
  env file (`MICROCHESS_*` variables, see `docs/DEPLOYMENT.md`). It fails
  closed if one is missing. Do not hardcode host values into it.
- `DATABASE_URL` is relative to each service's working directory, which is
  what keeps the two databases apart. **Never** point beta at the
  production database file, and never run tests against a production
  database. Use a disposable database.
- `.env` files, databases, backups, certificates, and keys are never
  committed and never printed. Only `*.example` templates are tracked.
- Telegram verification stays disabled. The production messaging-bot
  credentials stay in production; do not copy them into beta.
- Change the code, not the environment: no DNS, TLS, firewall, SSH, or
  reverse-proxy architecture changes as part of application work.
- Infrastructure change is not done until it is verified: run the
  service, check the health endpoint, and confirm the real domain
  answers. Do not touch unrelated projects, services, or sites on the
  deployment host; they are out of scope.
- Operator-only detail (real paths, units, ports, backups, host access)
  belongs in a private, uncommitted runbook kept outside the repository
  next to the deployment host. Never symlink it into a tracked file, and
  never add a second public copy.

## Repository Map

For a current high-level map of the repository, major domains, entry points,
and common change locations, read:

`docs/REPOSITORY_MAP.md`

Use it as a navigation aid, then inspect the actual source files before making changes.
The map is a guide, not a substitute for repository evidence.
