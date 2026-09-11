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

Phase 01 (Foundation) completed and verified. Phase 02 (Accounts)
completed and verified. Phase 03 (Player Platform) completed and
verified. No later phase started.

| Area                         | Status      |
| ---------------------------- | ----------- |
| Foundation                   | VERIFIED    |
| Accounts & Identity          | VERIFIED    |
| Player Platform              | VERIFIED    |
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
helper) exist and Phase 2 persists accounts, roles, server sessions,
and guest identity on top of them.

---

## 4. Exercise Compatibility

Existing exercises verified preserved after Phase 03:

* exercise behavior, exercise-specific validation, scoring
* puzzle delivery (answers still never leave the server)
* responsive exercise UX (no exercise UI touched)
* existing tests: all pass unchanged (`/` anonymous menu unchanged)

---

## 5. Evidence

Phase 03 player platform (all verified by tests + live runtime checks):

* Player profile: `player_profiles(user_id UNIQUE, display_name,
  bio, avatar_reference)` (`backend/app/modules/player/models.py`);
  `GET/PATCH /api/v1/me/profile` (`modules/player/router.py`,
  thin; logic in `modules/player/service.py`). Lazy creation on
  first read (no data backfill); editable fields only, mass
  assignment rejected, no secrets in responses.
  `tests/test_player_platform.py` (15 tests).
* External chess identities: `player_external_identities` with
  CHECK(provider) + UNIQUE(user_id, provider) +
  UNIQUE(provider, external_username) (normalized strip+lower);
  `GET/POST/PATCH/DELETE /api/v1/me/chess-identities`. Providers
  strictly fide/lichess/chess_com; ratings self-reported and
  separate from MicroChess ratings; `is_verified` server-controlled
  (always False, never client-settable). Duplicates → 409,
  foreign ids → 404 (no existence leak).
* Training history: `GET /api/v1/me/training/attempts` (filters
  exercise/mode/correct + `page`/`page_size` bounds, newest first)
  and `GET /api/v1/me/training/attempts/{id}` read authoritative
  `attempts` rows; no duplication, no recalculation, no
  answer-solution exposure. Ownership is `/me`-scoping (no client
  user ids); cross-user → 404, anonymous → 401. Migrated guest
  attempts surface automatically after `/guest/migrate`.
* Progress: `GET /api/v1/me/progress` (all-time totals +
  per-exercise attempts/correct/accuracy/last) and
  `GET /api/v1/me/progress/{slug}` (404 for unknown slugs) via
  straightforward attempt queries — no analytics warehouse, no
  time ranges (Phase 8 owns those). No rating/XP/streak fields
  anywhere (Phases 4/5 own those; `rating_delta` is never
  surfaced).
* Dashboard: `GET /api/v1/me/dashboard` read model
  (profile + progress + 5 most recent attempts).
* Exercise discovery: `GET /api/v1/exercises/{slug}` detail
  (metadata only; 404 unknown); list endpoint unchanged
  (active-only). Frontend catalog remains the playable-source.
* Schema v3: `ensure_schema` upgrades Phase 02 DBs (new tables via
  `create_all`, no data touch; dev DB booted live at v3);
  fresh boot + idempotency covered by tests.
* Frontend: `HomePage` (`/` dashboard when logged in, unchanged
  exercise menu when anonymous), `DashboardPage`, `ProgressPage`
  (summary + filters + paging), `ProfilePage` (edit + identities
  CRUD), 4-tab player nav (Home/Exercises/Progress/Profile;
  player tabs only when logged in), `/account` links to
  `/profile`; Persian RTL, 44px targets, loading/empty/error
  states; 14 new frontend tests.
* Runtime verified live: register → profile → identities
  (409/422/404 boundaries) → attempts → history/progress/
  dashboard (cross-user 404, anon 401, pagination 422);
  production bundle contains the new screens; exercises untouched.

Phase 02 accounts (all verified by tests + live runtime checks):

* Username identity: `users.username` normalized (strip + lower),
  unique (`ix_users_username`), policy 3–30 `[a-z0-9_]`
  (`backend/app/modules/auth/service.py`); login/registration use
  username only. Legacy `users.email` kept nullable for upgrades, never
  required/returned. `tests/test_accounts.py` (28 tests).
* Passwords: Phase 01 pbkdf2_sha256 policy preserved; hashes never in
  responses (`/users/me` returns id/username/display_name/roles/
  created_at only); generic `401 INVALID_CREDENTIALS` for unknown
  user/wrong password/suspended.
* Persisted roles: `user_roles(user_id, role)` with CHECK to
  PLAYER/COACH/PARENT/ADMIN; registration assigns PLAYER; GUEST is not
  a role (`Role("GUEST")` raises). Capabilities resolve server-side
  from DB rows in canonical order; JWT carries no role (re-signed
  tokens rejected by the session hash binding). ADMIN carries
  platform-operation capabilities (no admin endpoints exist yet);
  COACH/PARENT map to the player set until Phase 9 relationships.
* Server sessions: `auth_sessions` rows bound to tokens via
  `sid` claim + SHA-256 hash; logout revokes (idempotent 204);
  multi-session supported; expiry, suspension, tampering, cross-user
  sid reuse, and sid-less legacy tokens all resolve to anonymous.
* Guests: `guest_sessions` (ACTIVE/MIGRATED/REVOKED + expiry) via
  `POST /api/v1/guest/session`, `GET /api/v1/guest/session`,
  `POST /api/v1/guest/migrate` (`accounts.migrate_guest`
  capability). Guest practice attempts carry `guest_session_id`;
  rated mode still requires an account. Migration is atomic,
  idempotent, replay-safe, ownership-checked (409 on foreign replay).
* Schema v2: `ensure_schema` upgrades Phase 01 DBs (username backfill
  from email, email nullability relaxation incl. SQLite rebuild,
  PLAYER backfill, attempts column); fresh boot + idempotency +
  downgrade refusal covered by tests; dev DB boots at v2.
* Frontend: username transport + guest helpers (`api/client.ts`),
  `AuthProvider`/`useAuth`, `/login`, `/register`, guarded
  `/account` (identity + Persian roles + logout), `RequireAuth`,
  header auth state, Persian error mapping; 10 new frontend tests.
* Runtime verified live: register → login → `/users/me` → duplicate
  400 → generic 401s → logout → revoked 401 → second session alive →
  guest create/get/migrate/replay (15/15 checks); production bundle
  contains the account screens; exercises untouched.

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
Area: Coach/Parent scoped capabilities
Current limitation: COACH/PARENT map to the player capability set; no
student-scoped object access exists (no relationship model yet).
Impact: None; student data access arrives with Phase 9 relationships.
Required follow-up: Phase 9 relationship + object authorization.
```

```text
Area: Anonymous local progress
Current limitation: frontend localStorage practice log is client-side
convenience only and is never imported as server attempts (client
scores are untrusted by design).
Impact: None; server-side guest attempts migrate via /guest/migrate.
Required follow-up: none (intended; revisit only with explicit product
requirement and server re-validation).
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

```text
Area: Player privacy settings / avatar uploads / public profiles
Current limitation: Phase 03 stores display_name/bio/avatar_reference
only; no privacy-settings table, no media uploads, no public profile
or leaderboard endpoints (no product requirement defines their fields).
Impact: None; profile visibility defaults to private (server never
serves one player's data to another).
Required follow-up: Explicit product spec + later phase.
```

```text
Area: Guest migration presentation
Current limitation: No dedicated migration UI; migrated guest attempts
surface automatically in history/progress/dashboard after /guest/migrate.
Impact: None for data; players are not shown a migration confirmation screen.
Required follow-up: Small UI notice when a product flow requires it.
```

---

## 7. Testing State

* backend tests: 935 passed (`pytest`; includes 28 account tests in
  `tests/test_accounts.py`, 15 player-platform tests in
  `tests/test_player_platform.py`, plus the Phase 03
  migration-table and v3-upgrade contract updates)
* frontend tests: 253 passed (`npm test`, 25 files; includes 10
  auth-context/login/protected-account tests and 14 new player
  transport/page/nav tests)
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
