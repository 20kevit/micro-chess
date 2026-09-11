# MicroChess Platform Implementation State

## 1. Purpose

This document records the actual implementation state of the platform.

It describes **repository reality**, not planned functionality.

---

## 2. Status Vocabulary

Use only:

```text
NOT_STARTED
IN_PROGRESS
PARTIAL
IMPLEMENTED
VERIFIED
BLOCKED
```

`IMPLEMENTED` means code exists.

`VERIFIED` means the implementation has also been meaningfully tested.

---

## 3. Platform Areas

Phase 01 (Foundation) completed and verified. No later phase started.

| Area                         | Status      |
| ---------------------------- | ----------- |
| Foundation                   | VERIFIED    |
| Accounts & Identity          | NOT_STARTED |
| Player Platform              | NOT_STARTED |
| Ratings                      | NOT_STARTED |
| Gamification                 | NOT_STARTED |
| Administration               | NOT_STARTED |
| Content & Generators         | NOT_STARTED |
| Analytics                    | NOT_STARTED |
| Relationships                | NOT_STARTED |
| Adaptive Training Foundation | NOT_STARTED |
| Support & Notifications      | NOT_STARTED |

Foundation primitives that later phases build on (password hashing +
policy, JWT sessions, capability registry, token transport, audit
helper) exist, but no Phase 2+ product behavior was implemented.

---

## 4. Exercise Compatibility

Existing exercises verified preserved after Phase 01:

* exercise behavior, exercise-specific validation, scoring
* puzzle delivery (answers still never leave the server)
* responsive exercise UX (no exercise UI touched)
* existing tests: all pass unchanged

---

## 5. Evidence

Phase 01 foundation (all verified by tests + live runtime checks):

* API versioning: `backend/app/core/api.py` (`API_V1_PREFIX`), all
  routers mounted under `/api/v1` from `backend/app/main.py`.
* Error contract: `backend/app/core/errors.py` returns
  `{"error": {"code", "message", "details"}}` plus legacy `detail`
  for existing clients; `tests/test_foundation_errors.py` (5 tests).
* Configuration: env-driven `backend/app/core/config.py`
  (production refuses the default JWT secret; CORS/rate-limit knobs
  centralized); `tests/test_foundation_config.py` (7 tests).
* Authorization: canonical registry `backend/app/core/capabilities.py`
  (roles PLAYER/COACH/PARENT/ADMIN, deny by default; every account acts
  as PLAYER until Phase 2 persists roles); enforced on `/users/me`
  and `/attempts`.
* Auth hardening: centralized password policy, pbkdf2_sha256 default
  hash (bcrypt backend broken in this env — verified), normalized
  emails, generic login failures, `POST /auth/logout` (204, server
  revocation lands in Phase 2), in-memory rate limits on auth routes
  (`backend/app/core/rate_limit.py`); `tests/test_foundation_auth.py`
  (12 tests).
* Migrations: `backend/app/db/migration.py` (`ensure_schema` is
  idempotent, stamps `schema_version`, refuses newer-than-code DBs,
  imports all module models — this fixed 7 exercise session tables
  missing from fresh boots); dev DB verified stamped v1 with 19
  tables; `tests/test_foundation_migrations.py` (6 tests).
* Pagination bounds: `backend/app/core/pagination.py`
  (`page`/`page_size`, max 200) applied to `GET /puzzles` with
  unchanged response shape.
* Observability: `configure_logging` + `RequestIdMiddleware`
  (`X-Request-ID` on every response); audit primitive
  `backend/app/core/audit.py` (log-only until Phase 6 persists rows).
* Frontend: token transport + `error.code` parsing + auth endpoints
  in `frontend/src/api/client.ts`, `AuthProvider`/`useAuth` in
  `frontend/src/lib/auth-context.tsx` (no login UI — Phase 2);
  `frontend/src/api/client.test.ts` (7 tests).
* Runtime verified: uvicorn boots, `/health`, `/api/v1/exercises`,
  404 envelope, 422 bounds, 204 logout checked live.

---

## 6. Known Gaps

```text
Area: Architecture docs
Current limitation: docs/platform/ARCHITECTURE.md and DATA_MODEL.md are byte-identical (both hold the data-model text).
Impact: No implementation impact; architecture boundaries live in code + AGENTS.md.
Required follow-up: Docs fix outside any implementation phase.
```

```text
Area: Roles
Current limitation: No persisted roles; administrative capabilities deny everyone (fail closed).
Impact: None for Phase 1; admin endpoints do not exist yet.
Required follow-up: Phase 2 role model.
```

```text
Area: Sessions
Current limitation: Stateless JWT only; logout is client-side token discard.
Impact: No server-side revocation yet.
Required follow-up: Phase 2 persisted sessions.
```

```text
Area: List responses
Current limitation: Paginated endpoints keep plain-list shape (no {items, pagination} envelope).
Impact: None; bounds are enforced.
Required follow-up: Versioned envelope change when a consumer needs it.
```

```text
Area: Migrations
Current limitation: Version-row + idempotent steps; Alembic not adopted.
Impact: None for SQLite dev; sufficient for current scale.
Required follow-up: Adopt Alembic with the PostgreSQL move.
```

---

## 7. Testing State

* backend tests: 891 passed (`pytest`; 861 pre-existing + 30 foundation)
* frontend tests: 229 passed (`npm test`, 18 files; 222 pre-existing + 7 foundation)
* typecheck: `npm run typecheck` clean
* build: `npm run build` succeeds (pre-existing chunk-size warning only)
* migration verification: fresh-boot, idempotency, data preservation,
  legacy-DB stamping, downgrade refusal (tests) + live dev-DB stamp
* integration/e2e: live uvicorn checks (health, catalog, error
  envelope, pagination bound, logout); no browser e2e added

---

## 8. Update Rules

Update this document when:

* a platform phase changes state
* a major implementation milestone is completed
* a blocker is discovered
* verification changes
* an important architectural gap is resolved

Keep entries concise.

Do not turn this file into a development diary.

---

## 9. Agent Rule

Before implementing any phase, the agent MUST:

1. inspect the repository
2. compare actual state with this document
3. treat code as current-state evidence
4. implement only missing work
5. run meaningful verification
6. update this document with evidence

The agent must never assume that a phase is incomplete merely because its documentation exists, or complete merely because its documentation describes the desired state.
