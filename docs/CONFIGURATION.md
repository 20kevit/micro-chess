# Configuration & Environment

Secrets come only from the environment — never committed, never
bundled into the frontend. All settings are defined in
`backend/app/core/config.py` (pydantic-settings, `env_file=".env"`).

## Backend (`backend/.env`, gitignored)

Template: `backend/.env.example`. Copy it with `cp .env.example .env`.

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./microchess.db` | SQLite file, **relative to the process working directory**, so each runtime resolves its own database. Local dev, beta, and production each have their own gitignored file. |
| `ENVIRONMENT` | `development` | Set `production` on the host. With `production` + the default `JWT_SECRET`, the app fails fast at startup (`ensure_ready()`). |
| `JWT_SECRET` | `change-me-in-production` | REQUIRED in production — must be a long random secret. |
| `JWT_ALGORITHM` | `HS256` | — |
| `JWT_EXPIRE_MINUTES` | `60` | — |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list. Production sets the site origin. |
| `LOG_LEVEL` | `INFO` | — |
| `RATE_LIMIT_ENABLED` | `true` | — |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `30` | Auth endpoints abuse protection. |
| `VERIFICATION_TELEGRAM_ENABLED` | `false` | **Telegram verification is disabled by project decision** (no usable server connectivity). Leave it `false`. The Bale channel stays available; its bot credentials live only in the production `.env`. |
| `SUPPORT_RATE_LIMIT_PER_MINUTE` | `20` | Support ticket/message spam protection (code default; not in `.env.example`). |
| `GUEST_SESSION_EXPIRE_DAYS` | `30` | Server-side guest session lifetime (code default; not in `.env.example`). |
| `PUZZLES_DB_PATH` | unset | Optional shared Lichess position source (read-only). When unset, the backend looks for `./puzzles.db` then `./backend/puzzles.db`, else uses curated fallback positions. Never committed (gitignored). |
| `LICHESS_PUZZLE_URL` | `https://database.lichess.org/lichess_db_puzzle.csv.zst` | Offline ingestion pipeline source (`python -m app.tools.lichess_puzzles.cli`). Not required for the FastAPI runtime. |
| `LICHESS_PUZZLE_DATA_DIR` | `data/lichess_puzzles` | Ingestion data root (raw dump + processed outputs, gitignored). |
| `LICHESS_PUZZLE_PROGRESS_EVERY` | `200000` | Ingestion progress log interval (rows). |

Offline ingestion details (download/process/validate, output format,
schema-reuse notes): `docs/LICHESS_PUZZLES.md`.

There is no debug mode in the codebase. CORS and rate limits are
env-driven only.

## Per-runtime files on the deployment host

Each runtime owns its own `backend/.env` and its own SQLite database.
Neither is committed. Beta and production MUST NOT share either one; see
`docs/DEPLOYMENT.md`. Where each runtime actually lives on the host is
operator-side configuration and is intentionally not in this public
repository.

| Runtime | `.env` | Database |
|---|---|---|
| beta | `beta/backend/.env` | `beta/backend/<beta-db>.db` |
| production | `production/backend/.env` | `production/backend/<production-db>.db` |

Both files are mode `0600` and are not reachable over HTTP.

## Frontend (build-time)

Single variable (`frontend/.env.example`), read in
`frontend/src/api/client.ts` as `import.meta.env.VITE_API_BASE_URL ?? ""`:

| Variable | Dev | Production build |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | empty (same-origin relative `/api/v1/...` URLs) |

Build production with the variable empty:

```bash
cd frontend
VITE_API_BASE_URL= npm run build
```

A committed regression test
(`test_committed_dist_is_production_safe`) fails if any future
`frontend/dist/` contains `localhost`/`127.0.0.1`.

## Database

Schema is managed by idempotent `ensure_schema`
(`backend/app/db/migration.py`, `SCHEMA_VERSION = 17`): fresh
databases boot to v17, older ones upgrade with data preserved,
newer-than-code databases refuse to boot. Back up a production
database before any deploy that could migrate it. Models use only portable
SQLAlchemy column types. The full logical model is documented in
`docs/platform/DATA_MODEL.md`.
