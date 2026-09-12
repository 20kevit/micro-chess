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
verified. Phase 04 (Ratings) completed and verified. Phase 05
(Gamification foundation) completed and verified. Phase 06
(Administration foundation) completed and verified. Phase 07
(Content & Generators) completed and verified. Phase 08
(Analytics) completed and verified. Phase 09 (Relationships)
completed and verified. Phase 10 (Adaptive Training Foundation)
completed and verified. Phase 11 (Support & Notifications)
completed and verified. Phase 12 (Beta Readiness: active roles,
admin bootstrap, cPanel deployment) completed and verified.
No later phase started.

| Area                         | Status      |
| ---------------------------- | ----------- |
| Foundation                   | VERIFIED    |
| Accounts & Identity          | VERIFIED    |
| Player Platform              | VERIFIED    |
| Ratings                      | VERIFIED    |
| Gamification                 | VERIFIED    |
| Administration               | VERIFIED    |
| Content & Generators         | VERIFIED    |
| Analytics                    | VERIFIED    |
| Relationships                | VERIFIED    |
| Adaptive Training Foundation | VERIFIED    |
| Support & Notifications      | VERIFIED    |
| Beta Readiness (Phase 12)    | VERIFIED    |

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

Phase 12 beta readiness — active roles, admin bootstrap, cPanel
deployment (all verified by tests + live runtime checks):

* Active-role model (`auth_sessions.active_role`, schema v11):
  assigned roles stay in `user_roles`; each session carries exactly one
  active role, always a member of the assigned set (`service.py`
  `assigned_role_codes/validate_session_role/active_role_for`;
  `create_user_session` requires a validated role; JWTs still carry no
  role). Single-role accounts log in directly (backward compatible);
  multi-role logins without a role get 409 `ROLE_SELECTION_REQUIRED`
  with the account's own assigned roles in `error.details` (only after
  successful authentication, so no cross-user role enumeration); an
  unassigned/unknown role is 422 `invalid_role`. `POST
  /api/v1/auth/active-role` switches the current session only (nothing
  else changes). A session whose active role is no longer assigned
  authorizes as nothing (401 `active_role_revoked`, fail closed, no
  silent fallback); fresh login recovers deterministically.
* Authorization (`core/capabilities.py`): the capability set resolves
  from the session's active role (`active_role_for_session`,
  `capabilities_for_session`), not the assigned union — a PLAYER-active
  session of an ADMIN user gets 403 on admin endpoints while an
  ADMIN-active session passes. Object-level checks (relationships,
  ownership, 404 scope) are untouched and remain authoritative:
  coach/parent reads still require an ACTIVE edge of the matching kind.
  `require_capability` keeps its direct-call unit-test seam (unresolved
  `Depends` markers fall back to the assigned union; real requests stay
  strict). `/users/me` now also returns server-resolved `active_role`.
* Admin bootstrap (`backend/app/cli.py`, no HTTP/frontend path):
  `python -m app.cli create-admin <username>` promotes an existing
  account to ADMIN only (never creates accounts, no password handling,
  idempotent `already_admin` no-op, username canonicalized) and
  refuses production without `--confirm-production`.
  `tests/test_admin_bootstrap.py` (8 tests).
* cPanel deployment (`/.cpanel.yml`, valid YAML, root-level): explicit
  tracked source paths only (backend `app/`, packaging, env template;
  frontend `src/`, `public/`, build config; docs); never `.git`,
  databases, `.env`, `node_modules`, `dist/`, backend `tests/`,
  frontend `qa/`, or colocated `*.test.*` (pruned). No secrets, no
  wildcard copies, no on-server builds (tooling unverified): the
  frontend bundle is built locally (`npm run build`) and the Python app
  is wired in cPanel's UI. Verified assumptions: file layout above,
  code-only deploy dirs (DB/env live outside). Unresolved (operator):
  exact `DEPLOYPATH`, Python-App root/startup/venv, env values, DB
  location, static hosting of `dist/`. Live cPanel deploy untested.
* Schema v11: fresh boots to v11; v1–v10 DBs upgrade with data
  preserved (v11 step adds `active_role` + backfills NULL rows to the
  owner's first canonical role, PLAYER fallback; re-run safe, never
  overwrites chosen roles). Legacy upgrade-contract tests bumped
  `== 10` → `== 11`. Only portable column types.
* Frontend: 409-driven Persian RTL role-selection step on the login
  page (server list only), `نقش فعلی` + `تغییر نقش` switcher on the
  account page (multi-role only, server-authoritative via
  `switchActiveRole` + reload), active-role-aware `RequireAdmin` and
  nav tabs (coach/parent/admin follow the session role), `apiRoles`/
  `apiDetails` transport, `active_role` on `AuthUser`, 6 new Persian
  strings in `fa.ts`. Backend remains the sole authorizer. 12 new
  frontend tests (transport + selection + switcher + guard/nav +
  context).
* Runtime verified live on a fresh DB (26 checks): register → single
  login → multi 409 + roles → invalid role 422 → coach login →
  invite/accept → coach read 200 / foreign 404 → switch → scope
  unchanged → bootstrap → admin dashboard → anon 401 / wrong-role 403
  → logout/revoke → re-login → support + notifications + exercise
  attempt → schema v11 with the v2→v11 migration chain.
* `tests/test_active_roles.py` (19 tests): backward-compat login,
  selection matrix, switching (incl. other-session isolation),
  revoked-role fail-closed, active-role authorization, coach/parent
  scope under both roles, exact 409 envelope, v10→v11 backfill.
* Phase-mandated updates to existing tests (behavior change, not
  weakening): admin/staff helpers re-login with an ADMIN-active
  session after promotion (sessions fix their role at creation);
  `test_promoted_admin_gains_access` now asserts the old session stays
  403 while a fresh ADMIN session passes; demoted-admin session is 401
  `ACTIVE_ROLE_REVOKED` (was 403); `/me` shape test covers
  `active_role`; `test_piece_attempts_api` passes the required role.
* Intentional deferrals: live cPanel deploy test (no account access),
  `passenger_wsgi.py` (startup wiring stays in cPanel's UI, no invented
  entrypoint), frontend build on the server, PostgreSQL migration,
  leaderboards, Glicko-2, ML/adaptive models, mastery, gamification
  additions, analytics additions, messaging, notifications providers,
  attachments, public profiles, new exercises/generators, MFA, password
  reset, passkeys (all out of scope per the phase boundary).

Phase 11 support & notifications (all verified by tests + live runtime checks):

* Support (`backend/app/modules/support/`, schema v10): tickets owned
  by exactly one account (guest support not enabled — no product
  requirement); lifecycle exactly `open -> answered -> closed`
  (owner replies move `answered` back to `open`; `closed` is terminal
  and idempotent; first staff response/close records
  `assigned_admin_id`). Creation carries the initial owner message
  (subject ≤200, message ≤2000, category free-form ≤50 — no invented
  taxonomy); messages are append-only with a server-derived staff/user
  flag (owner views never expose admin identities). Capabilities are
  new `support.create/read_own` (every account) plus
  `support.read/respond/close` (ADMIN-held; `support.manage` already
  existed). Creation + owner replies are rate-limited
  (`support_rate_limit_per_minute`, centralized setting + shared
  limiter); every state change is audited (`support.create/reply/
  respond/close`, secret-free).
* Notifications (`backend/app/modules/notifications/`, the module's
  only tables): strict `event -> notification -> delivery` separation —
  domain code emits an event, the service applies the preference
  decision, persists the notification, then delivers through a channel
  provider. Categories are exactly `support` (default-on,
  disableable) and `account` (mandatory, never disableable; missing
  preference rows default to enabled; evaluation is server-side).
  Event types are exactly `support.response`, `support.closed`,
  `account.suspended`, `account.reactivated` (only triggers: staff
  support actions + suspend/reactivate hooks in the admin service;
  emission is best-effort and can never fail the business operation).
  Deduplication is a UNIQUE `dedup_key` (IntegrityError collapses to
  the existing row). Deliveries are one row per (notification,
  channel) with provider-independent `pending/sent/delivered/failed`
  status, attempt counts, and payload-free error summaries; retries
  update the same row. Provider abstraction (`providers.py`) keeps
  vendor SDKs out of the domain — only `in_app` is registered
  (external channels remain future per the Phase 11 spec).
* API (thin routers, `/api/v1`, error envelope, bounded pagination):
  `POST /support/tickets`, `GET /me/support/tickets[/{id}]`,
  `POST /me/support/tickets/{id}/messages` (owner-only; foreign ids
  404, anon 401), `GET /admin/support/tickets[/{id}]`,
  `POST /admin/support/tickets/{id}/messages|/close` (staff caps),
  `GET /me/notifications[?unread_only]`,
  `GET /me/notifications/unread-count`,
  `POST /me/notifications/{id}/read` (owner-only, idempotent),
  `GET|PATCH /me/notification-preferences` (mandatory rejection is
  422). No client notification-write endpoint exists.
* Schema v10: fresh boots to v10 (`support_tickets`,
  `support_messages`, `notifications`, `notification_deliveries`,
  `notification_preferences` via `create_all`); v1–v9 DBs upgrade
  with data preserved (no backfill, no fabricated history); legacy
  upgrade-contract tests bumped `== 9` → `== 10`; idempotency +
  downgrade refusal covered. Only portable column types (compiled on
  SQLite + PostgreSQL dialects in tests).
* Frontend: `/support` (create form + status list with Persian
  labels), `/support/:id` (conversation + reply box hidden when
  closed), `/notifications` (unread filter, mark-read, preference
  switches with mandatory locking), `/admin/support` (queue with
  status filter + conversation + respond/close with confirmation),
  header bell with server-owned unread badge (refreshed on
  navigation, no polling) + support link, admin dashboard link,
  `supportApi`/`notificationsApi`/`adminApi.support` transport, ~40
  Persian strings in `fa.ts`; RTL preserved, 44px targets,
  loading/empty/error states. Backend remains the sole authorizer.
  14 new frontend tests (4 transport + 10 page).
* Runtime verified live on a fresh DB (23 checks): register ×3 →
  create/list (owner + admin views) → staff respond → owner
  `support.response` notice + unread 1 → owner reply reopens →
  close → `support.closed` notice → mark read → prefs matrix +
  opt-out + mandatory 422 → cross-user 404 / player-admin 403 /
  anon 401 → suspend/reactivate notices covered by tests →
  dashboard/catalog/admin-overview regressions green → schema v10
  with the v8→v10 migration chain.
* `tests/test_support_notifications.py` (21 tests): creation,
  ownership, pagination, conversation, staff lifecycle, capability
  matrix, read/unread, preferences (incl. mandatory + suppression),
  dedup, delivery failure/retry, provider isolation, account
  triggers, migration, portability.
* Intentional deferrals: guest support (no product requirement),
  email/push/Telegram/external providers (provider seam is ready),
  ticket reopening (closed is terminal per the capability list —
  no reopen capability exists), admin assignment endpoint
  (first responder auto-records), support attachments, coach/parent
  notification surfaces, adaptive/gamification notification triggers
  (only the specified support + account events emit).

Phase 10 adaptive training foundation (all verified by tests + live runtime checks):

* Policy (`backend/app/modules/adaptive/service.py`, pure + documented):
  deterministic, explainable selection over authoritative state —
  per-exercise ability is the current rating (else the documented 1200
  default); signals derive read-only from attempts (accuracy, recent
  accuracy/failures, repeated mistakes, response time, recency),
  rating events (trend), and ratings (provisional/games). One
  machine-readable reason per scope (`WEAK_EXERCISE`,
  `RECENT_FAILURES`, `READY_FOR_HARDER`, `LOW_RECENT_ACTIVITY`,
  `MASTERY_REVIEW` with a documented stale+strong definition,
  `APPROPRIATE_DIFFICULTY`, `COLD_START` baseline), classified by a
  pure function with a documented priority (struggling first).
  Difficulty targets are ability-relative (remediation −200,
  challenge +150, else ability; clamped to [100, 3000]); candidates
  rank by distance to target with id tie-breaks. An explicit caller
  `seed` picks reproducibly among the top-5 via `random.Random(seed)`
  (injectable; global random never touched). All knobs are centralized
  constants in the service module (same precedent as Phase 04/05).
* Eligibility (database-side): published + not archived only (Phase 07
  projection); disabled exercises yield nothing; unknown exercises 404;
  scope is strictly per-exercise for `next` (cross-exercise choice
  lives only in `overview`). Recent content (last 20 own attempts) is
  avoided; when everything was seen, recency relaxes (flagged
  `fallback: true`) rather than stranding the learner — lifecycle rules
  never relax; empty sets return 404 `no_eligible_content`.
* Observed difficulty reuses the Phase 08 derived label (≥5-attempt
  gate, never persisted, never rewritten by selection).
* Feedback loop (`adaptive_recommendations`, the module's only table):
  every `next` call records a `shown` row (exercise/puzzle/reason/
  ability/target/seed); the owner advances it `shown -> accepted/
  skipped`, `accepted -> completed/skipped` (terminal states never
  reopen; optional informational `result`). Selection otherwise
  mutates nothing — verified by test (attempts/ratings/XP/puzzle rows
  identical before/after).
* API (thin routers, `/api/v1`, `USERS_READ`, error envelope):
  `GET /me/adaptive/overview` (signals + recommended exercise),
  `GET /me/adaptive/next?exercise=&seed=`, `GET /me/adaptive/history`,
  `POST /me/adaptive/outcomes/{id}` (owner-only; foreign ids 404).
  Coach/parent get derived overviews only
  (`/coach/students/{id}/adaptive/overview`,
  `/coach/.../adaptive/exercises/{slug}`, same under `/parent`) under
  the Phase 09 capability + active-relationship + kind-filtered model
  (unrelated/guessed ids 404, revoked edges lose access immediately,
  issuance/outcomes stay owner-only so viewing never fabricates
  history). Answers never leave the server (`PuzzleOut`).
* Schema v9: fresh boots to v9 (`adaptive_recommendations` via
  `create_all`); v1–v8 DBs upgrade with data preserved (no backfill,
  no fabricated recommendations); legacy upgrade-contract tests bumped
  `== 8` → `== 9`; idempotency + downgrade refusal covered.
* Frontend: `AdaptiveSection` on the Progress page (recommended
  exercise + Persian reason, per-exercise signals, next-item request
  with ability/target/observed display, start-training link recording
  `accepted`, skip recording `skipped`, loading/empty/error states) +
  adaptive card in coach/parent student detail, `adaptiveApi`/
  `coachApi.adaptive`/`parentApi.adaptive` transport, ~25 Persian
  strings in `fa.ts`; RTL preserved, 44px targets. Backend remains the
  sole policy owner. 9 new frontend tests (6 section + 3 transport).
* Runtime verified live on a fresh DB (33 checks): cold-start baseline
  → nearest-ability selection → 5 failures flip the reason to
  `RECENT_FAILURES` with a below-ability target → seeded
  reproducibility → empty-exercise 404 → outcome lifecycle + history →
  no-mutation → cross-user isolation → coach invite/pending-deny/
  accept/read/unrelated-deny/revoke-block → parent read/unrelated-deny
  → anon 401 → Phase 01–09 regressions green → schema v9 with the
  2→9 migration chain.
* `tests/test_adaptive.py` (33 tests): cold start, eligibility,
  difficulty, signals, repetition/fallback, determinism (incl. global-
  RNG independence), outcomes, security matrix, invariants, migration.
* Intentional deferrals: ML/ranking models, Glicko-2, mastery tables,
  spacing/remediation scheduling beyond reason-targeted difficulty,
  coach-issued recommendations for students, exploration beyond the
  seeded top-5 pick, leaderboards, notifications (all out of scope).

Phase 09 relationships (all verified by tests + live runtime checks):

* Model (`backend/app/modules/relationships/models.py`, schema v8):
  one `relationships` table with a `kind` discriminator (`coach` /
  `parent`, CHECK-constrained) plus `assignments`; lifecycle is exactly
  `pending -> active -> revoked` (declining a pending invitation revokes
  it; no separate rejected/suspended states; history rows are never
  deleted). Duplicate pending/active edges for the same
  (kind, mentor, student) are rejected; a fresh invitation is allowed
  after revocation (new row, history preserved).
* Creation/acceptance (`service.py`, server-enforced): either party
  invites by the other account's username, creating PENDING with zero
  access (knowing a username alone proves nothing); the non-creating
  party accepts (idempotent; creator self-accept → 403). Role
  combination is explicit (coach edges need one COACH party, parent
  edges one PARENT party); self-edges, unknown users, and inactive
  accounts are rejected. Multiple coaches/parents per student allowed;
  each edge authorizes independently.
* Authorization (capability + active relationship + object scope +
  privacy, checked per request, deny by default): new
  `relationships.create/accept/revoke` capabilities (all accounts hold
  them; ADMIN holds all); reads require `users.read` plus a fresh
  ACTIVE edge of the matching kind with both accounts active. Coach
  routes (`/coach/students...`) and parent routes
  (`/parent/children...`) filter by kind, so edges never cross
  (coach ⇏ parent endpoints and vice versa); unrelated/guessed student
  ids uniformly return 404 (no existence leak); revoked edges lose
  access immediately; ADMIN gains no edge access (not a party → 404).
  Collection endpoints use database-side joins (no Python post-filter).
* Scope: related-student reads reuse the existing read-only services
  (progress, attempts incl. detail, ratings + per-exercise history,
  gamification summary, achievements, `player_overview` analytics) with
  privacy-scoped shapes (identity limited to id/username/display_name;
  never password hashes, emails, sessions, tokens, answers, or admin
  data). Student `/me/*` access is untouched by relationships.
* Assignments foundation (`assignments` + coach/parent/`/me` routes):
  coaches create exercise assignments (stable slug, note ≤500, optional
  ISO deadline) only under an ACTIVE coach edge — pending/revoked
  block creation; `assigned -> completed` (coach or owning student) /
  `assigned -> cancelled` (coach only); terminal states never reopen;
  parents see the child's assignments read-only; completing/cancelling
  never touches attempts, ratings, XP, or analytics.
* Audit (existing Phase 6 system, secret-free): `relationships.create/
  accept/revoke`, `assignments.create/update` persist actor/action/
  target/timestamp rows; ordinary related-student reads create no rows.
* Schema v8: fresh boots to v8 (`relationships`, `assignments` via
  `create_all`); v1–v7 DBs upgrade with data preserved (no backfill, no
  fabricated edges); legacy upgrade-contract tests bumped `== 7` →
  `== 8`; idempotency + downgrade refusal covered.
* Frontend: `/relationships` (invite form by username + incoming/
  outgoing pending with scope hints + active/revoked lists, accept/
  revoke with confirmation), `/coach/students` + `/parent/children`
  (role-gated nav; lists + scoped detail with progress/ratings/
  gamification/analytics/recent attempts + assignment management for
  coaches, read-only for parents), `relationshipsApi`/`coachApi`/
  `parentApi` transport, ~45 Persian strings in `fa.ts`; RTL preserved,
  44px targets, loading/empty/error states. Backend remains the sole
  authorizer. 17 new frontend tests.
* Runtime verified live on a fresh DB (38 checks): register ×4 →
  coach/parent invites (pending grants nothing) → accept →
  permitted coach/parent reads (secret-free) → assignment
  create/parent-read/student-complete → cross-student denial both kinds
  → kind separation → student self-access intact → duplicate/invalid
  transitions rejected → revocation removes reads + blocks new
  assignments (parent edge unaffected) → foreign relationship ids 404,
  anon 401 → audit rows present and secret-free → Phase 8 analytics +
  exercise catalog regressions green → schema v8.
* Drive-by fix: `positions/repository.py` `random_position_fen` dropped
  the caller's RNG on the `puzzles.db` path and drew from global
  `random`, so "seeded" generation depended on ambient test-order
  consumption (surfaced as an order-dependent trapped-pieces failure
  once Phase 09 tests were added). The RNG is now threaded through;
  seeded generation is reproducible and the full suite is
  order-independent (1068 passed twice consecutively).
* Intentional deferrals: groups/classes tables (multiple simultaneous
  edges are the foundation; no classroom hierarchy built), coach notes
  beyond assignment notes, notifications/messaging, public profiles,
  leaderboards, adaptive training (Phase 10), Glicko-2.

Phase 08 analytics (all verified by tests + live runtime checks):

* Architecture (`backend/app/modules/analytics/`, new; no new tables,
  schema stays v7): `service.py` derives every metric from
  authoritative `attempts` / `rating_events` / `xp_events` / streak
  state / content metadata; routers (`player/router.py`
  `/me/analytics*`, `admin/router.py` `/admin/analytics*`) stay thin.
  Read-only by construction (no adds/commits; immutability test
  asserts identical row counts before/after every endpoint).
* Semantics (documented in the service module): UTC rolling windows
  (`7d`/`30d`/`90d`), `all`, and `custom` UTC calendar-day ranges;
  previous-equivalent-period comparison for bounded windows only
  (`all` → 422); accuracy = correct / ALL attempts (matches Phase 3
  progress); response time over non-NULL `duration_ms`; authenticated
  attempts only (guests enter after `/guest/migrate`); observed
  difficulty = easy ≥0.7 / medium ≥0.4 / hard below, gated at ≥5
  attempts (`insufficient_data`), never persisted (Phase 10 owns
  adaptation). No cross-exercise session count exists (speed sessions
  are exercise-scoped tables with no shared model; `active_days` is
  the consistency signal); mastery/leaderboards/goals have no source
  tables yet — all intentional deferrals, no speculative framework.
* Player API (`USERS_READ`, `/me`-scoped, no client user ids):
  `GET /me/analytics` (totals + by-mode/by-exercise + daily buckets
  with XP + rating trends + XP/streak), `GET /me/analytics/comparison`
  (current vs previous + deltas), `GET
  /me/analytics/exercises/{slug}` (404 unknown), `GET
  /me/analytics/puzzles/{id}` (personal stats only, never answers;
  404 missing). `tests/test_analytics.py` (21 tests).
* Admin API (new `analytics.read_platform/read_exercise/
  read_puzzle` capabilities; ADMIN holds all; player → 403, anon →
  401): `GET /admin/analytics` (users/new/active, attempts/accuracy,
  exercise usage, daily, rating/XP, previous-period comparison),
  `GET /admin/analytics/exercises[/{slug}]`, `GET
  /admin/analytics/puzzles[?exercise,page]` + `/{id}` (attempts,
  unique players, accuracy, failure rate, repeated failures ≥2 wrong
  by one user, observed difficulty, avg response; answers never
  included). Aggregates only — no per-user rows, no secrets.
* Frontend: `AnalyticsSection` on the Progress page (period selector,
  totals, daily trend bars, comparison deltas, per-exercise; CSS bars,
  no chart dependency) + `/admin/analytics` (platform cards, exercise
  usage, puzzle performance with Persian observed-difficulty labels),
  dashboard link, `analyticsApi` transport, ~25 Persian strings in
  `fa.ts`; RTL preserved, 44px targets, loading/empty/error states.
  8 new frontend tests.
* Runtime verified live on a fresh DB (30 checks): 401/403
  boundaries → empty contract → rated-correct + practice-wrong →
  totals/accuracy/rating/XP reconcile → comparison 7d + all→422 →
  exercise filter/404 → personal puzzle answer-free → isolation →
  date filtering → admin aggregates match + secret-free → exercise/
  puzzle analytics + observed `insufficient_data` → regressions
  (progress/dashboard/ratings/gamification/exercises) → no mutation
  → schema v7 with no analytics tables.
* Drive-by fix: `core/errors.py` 500 handler referenced an unimported
  `status` (NameError on any unhandled error); now imports
  `fastapi.status`. No behavior change on handled paths.
* Intentional deferrals: coach/parent analytics (Phase 9 needs the
  relationship model), leaderboards, mastery, goals, sessions count,
  support-volume metrics (no source tables), caching/materialization
  (direct queries suffice at current scale), adaptive training
  (Phase 10).

Phase 07 content & generators (all verified by tests + live runtime checks):

* Lifecycle (`puzzles/models.py` `status`: draft → validated →
  reviewed → approved → published → retired, server-enforced;
  `is_published`/`is_archived` stay synced as the player-visibility
  projection so player queries are untouched; legacy/runtime rows
  enter via the model default; meaning locks after draft,
  retired rows are fully immutable). Publish requires approved state
  + final validation; direct draft → publish is rejected (409).
  `tests/test_content_lifecycle.py` (18 tests).
* Validation (`puzzles/validation.py`, v1): known exercise,
  non-empty answer, FEN legality via the chess-engine wrapper,
  difficulty 1–5 / rating 100–3000 bounds, answer-leakage guard,
  dedup hash over canonical (exercise, fen, answer) against gated
  content (first-to-validate wins; drafts excluded), plus
  exercise-specific solution-legality hooks registered inside the
  exercise domain (`captures`, `piece-recognition`,
  `legal-destinations` `content.py`; no slug chains in core flow).
* Review/approval: `POST validate/review/approve` under new
  `puzzles.validate/approve` capabilities (`puzzles.review` already
  existed); `request_changes`/`reject` return to draft with the
  decision preserved; every run/decision persists append-only
  (`puzzle_validations`, `puzzle_reviews`, `puzzle_status_history`)
  and is audited; `GET puzzles/{id}/history` exposes the trail.
* Generators (`modules/generators/`, code registry of 3 versioned
  entries reusing each exercise's pure builders; admin cannot invent
  executable generators): bounded synchronous jobs (1–50, no
  queues/workers), seed + version + validated-config snapshot for
  reproducibility, per-candidate validation, in-batch + DB dedup,
  accepted persist as `validated` with provenance
  (`source=generated`, `generator_run_id`), rejected stay traceable
  in the job result; never auto-published; failures are atomic (no
  partial persistence); cancel only non-terminal jobs.
  Endpoints: `GET /admin/generators`, `POST
  /admin/generators/{code}/runs`, `GET /admin/generator-runs[/{id}]`,
  `POST .../cancel` under `generators.read/run/cancel`.
* Unpublished isolation: draft/validated/reviewed/approved return
  404 on player puzzle/attempt APIs; answers never leave the server
  except in admin views.
* Schema v7: fresh boots to v7 (new `generator_runs`,
  `puzzle_status_history`, `puzzle_validations`, `puzzle_reviews`
  tables via `create_all`); v1–v6 DBs upgrade with lifecycle columns
  backfilled from legacy flags + canonical hashes (NULL-only
  backfill, re-run safe; no fabricated history); legacy
  upgrade-contract tests bumped `== 6` → `== 7`. Idempotency +
  downgrade refusal covered.
* Frontend: puzzle page lifecycle buttons + history viewer + new
  status filters, `/admin/generators` (registry + run form with
  count/seed/target/difficulty + run history + cancel),
  `adminApi` transport, ~25 Persian strings in `fa.ts`; RTL
  preserved, 44px targets, loading/empty/error states. Backend
  remains the sole authorizer. 4 new frontend tests (lifecycle
  actions, generators page, transport).
* Runtime verified live on a fresh DB (32 checks): 401/403
  boundaries → draft → invalid-FEN stays draft → invalid
  transitions rejected → validate/review/approve → unpublished
  hidden → publish (visible w/o answer) → immutability →
  registry + seeded job (provenance, hidden) → bad config 422 →
  cancel-terminal 409 → audit present and secret-free → attempt →
  retire (hidden, history kept) → dashboard intact → schema v7.
* Intentional deferrals: bulk validation/review/publish (spec
  allows but does not require), puzzle tags, observed-difficulty
  analytics (Phase 8 owns analytics), runtime on-the-fly practice
  puzzles keep `source=manual` (they predate provenance tracking;
  managed content is fully traced), generator create/update/delete
  (registry is code-defined by safety design), exercise create/
  delete, user deletion (all prior deferrals unchanged).

Phase 06 administration foundation (all verified by tests + live runtime checks):

* Capabilities (`core/capabilities.py`): granular Phase 6 additions —
  `users.read_private/suspend/reactivate`, `roles.assign/revoke`,
  `exercises.create/update/enable/disable/delete`,
  `puzzles.update/retire`, `admin.overview`. ADMIN holds all (existing
  `frozenset(Capability)` mapping); PLAYER/COACH/PARENT sets unchanged.
  Admin cross-user reads use manage-scope caps (`users.manage`,
  `exercises.manage`, `puzzles.manage`, `users.read_private`) because
  every account holds `users/exercises/puzzles.read` for its own
  `/me`/catalog endpoints — guarding admin lists with those would leak.
* Admin API (`modules/admin/`, `/api/v1/admin`, 15 endpoints, thin
  router + `service.py` business rules): `GET /dashboard` (read-only
  counts + recent registrations/audit, no secrets), user
  search/filter/pagination (`search`/`role`/`status`, whitelisted
  sort/order, bounded page size), user detail (identity + profile +
  roles + attempt count; never password hashes/emails/tokens),
  `suspend`/`reactivate` (idempotent; suspension fails closed on next
  token use, no session rewrite needed), role assign/revoke
  (canonical roles only, idempotent, final-ADMIN removal → 409),
  exercise inspect + metadata update + enable/disable (slug immutable;
  enabling requires a registered implementation; disabling hides the
  catalog entry and makes `submit_attempt` refuse new attempts with
  `exercise_not_available` while history stays readable), puzzle
  draft/create + update (answer/position/FEN/exercise immutable once
  published) + `publish` (gates: known exercise, non-empty answer) +
  `retire`/archive (idempotent; retired content hidden from players,
  attempts/ratings/analytics references preserved), audit list/detail
  (read-only; PUT/DELETE → 405). `tests/test_admin.py` (28 tests).
* Audit (`modules/admin/models.py` `audit_logs` + `record_audit`):
  every privileged transition (suspend/reactivate, role assign/revoke,
  exercise update, puzzle create/update/publish/retire) persists
  actor/action/target/timestamp/secret-free context and emits the
  Phase 1 log primitive; ordinary player requests create no rows.
* Schema v6: `ensure_schema` fresh-boots to v6 (new `audit_logs` table
  via `create_all`) and upgrades v1–v5 DBs with data preserved (legacy
  upgrade-contract tests bumped `== 5` → `== 6`; no backfill, no
  fabricated history); idempotency + downgrade refusal covered.
* Frontend: `/admin` (overview), `/admin/users` (search/filter/detail/
  suspend/reactivate/role buttons with confirmations),
  `/admin/exercises` (enable/disable + title edit),
  `/admin/puzzles` (filter + draft create + publish/retire),
  `RequireAdmin` UX guard + `مدیریت` nav tab only for ADMIN roles,
  `adminApi` transport, ~40 Persian strings in `fa.ts`; RTL preserved,
  44px targets, loading/empty/error states. Backend remains the sole
  authorizer. 15 new frontend tests (transport + guard + pages + nav).
* Runtime verified live on a fresh DB (37 checks): health → register →
  player 403 / anon 401 on admin APIs → promote → dashboard 200 →
  user search/detail (leak-free) → suspend (login 401, token dead) →
  reactivate → role assign (+422 invalid) → exercise disable (catalog
  hides) → puzzle draft/publish (visible w/o answer)/retire (404 for
  players) → player APIs intact (profile/progress/gamification/
  ratings/dashboard/achievements) → audit entries present, non-admin
  403 → schema stamped v6 with `audit_logs`.
* Intentional deferrals: user deletion (suspension is the reversible
  path; retention policy undefined), exercise create/delete, puzzle
  validate/review/approve (Phase 7 lifecycle), generators, support
  tickets, admin analytics (Phase 8), coach/parent relationships
  (Phase 9), speed-session-start gating for disabled exercises
  (submissions are refused server-side; start-gating across the 15
  exercise routers deferred to avoid touching exercise code).

Phase 05 gamification foundation (all verified by tests + live runtime checks):

* XP engine (`gamification_engine/service.py`, pure + documented):
  correct = 10 / partial = 5 / wrong = 2 per validated attempt, in
  both practice and rated modes (gamification eligibility is separate
  from Phase 4 rating eligibility); terminal states
  (timeout/skipped/abandoned) and guests never earn persistent XP.
  Numeric rules live in the service module as the single documented
  source, as GAMIFICATION.md leaves them configurable (same precedent
  as Phase 4 rating constants). `tests/test_gamification.py` (27 tests).
* Levels: `level = total_xp // 100 + 1` (centralized `LEVEL_XP_STEP`),
  derived server-side and stored on the materialized state; frontend
  only renders the bar width.
* Streaks: UTC-date based (repository-wide UTC timestamp convention),
  first activity starts at 1, consecutive days extend, same-day repeats
  are no-ops, missed days reset to 1 (longest preserved); out-of-order
  dates never corrupt state.
* Achievements (foundation catalog of 4, code-defined; unlocks in DB
  with UNIQUE(user_id, achievement_code)): `first_steps` (1 qualifying
  attempt), `steady_10` (10), `xp_100` (100 total XP), `streak_3`
  (3-day streak). Evaluation is deterministic + idempotent.
* Attempt integration (`progress/service.py`, single commit):
  XP/streak/achievements apply synchronously with the attempt (all
  speed sessions funnel through the same function); `attempt.xp_awarded`
  stamps the snapshot; idempotent re-application returns the stored
  event unchanged (UNIQUE on `xp_events.attempt_id` as the DB backstop).
* Query API (`/me` scope, `player/router.py` thin; reads in
  `gamification_engine/service.py`): `GET /me/gamification`,
  `GET /me/gamification/xp` (newest-first), `GET /me/achievements`
  (full catalog with unlock state). No client gamification-write
  endpoint exists (POST/PATCH/DELETE → 405). Cross-user reads isolated,
  anonymous → 401. Guests hold no persistent gamification rows.
* Schema v5: `ensure_schema` upgrades Phase 4 DBs (new tables via
  `create_all`, attempt `xp_awarded` column via idempotent ALTER; no
  backfill, no fabricated history); fresh boot + idempotency +
  v4→v5 data-preservation covered by tests; dev DB booted live at v5
  with users/attempts/ratings intact.
* Frontend: `GamificationSection` on the Progress page (XP total +
  level/progress bar + current/longest streak + achievements with
  Persian names + 5 most recent XP awards; loading/empty/error states),
  `getGamification/getXpHistory/getAchievements` transport
  (`api/client.ts`), 17 Persian strings in `fa.ts`; RTL preserved,
  44px targets, display-only (no XP/level/streak math in the client).
  7 new frontend tests (section states + transport); Progress page test
  mocks extended.
* Runtime verified live (20 checks + level transition): register →
  login → empty gamification → practice attempt earns XP → streak 1 →
  first_steps unlocks → history explains balance → accumulation →
  level 1→2 at 100 XP → same-day no double count → practice earns XP
  without rating → cross-user isolation → rated attempt rates + earns
  XP → Phase 3 endpoints intact (history carries `xp_awarded`).
* Intentional deferrals: leaderboards, exercise mastery, daily/weekly
  goals, badges, personal records, admin gamification management,
  notifications, guest XP migration (migrated attempts transfer
  ownership only and earn no retroactive XP), Glicko/Glicko-2, adaptive
  difficulty (all later phases or out of scope).

Phase 04 ratings (all verified by tests + live runtime checks):

* Rating state: `player_ratings(user_id, exercise_slug UNIQUE, rating,
  rating_deviation, is_provisional, games_count)` + immutable
  `rating_events(attempt_id UNIQUE, rating_before/delta/after,
  rating_deviation_before/after, reason)` (`rating_engine/models.py`).
  One row per player+exercise; guests hold no ratings (rated mode
  requires an account). `tests/test_ratings.py` (19 tests).
* Rating algorithm (`rating_engine/service.py`, pure + documented):
  Elo-style expected score vs `Puzzle.initial_rating`, actual
  1.0/0.5/0.0 for correct/partial/wrong, K=32 provisional / K=16
  established, clamp [100, 3000] with exact `after = before + delta`,
  RD `*0.97` floored at 50. Initial 1200 / RD 350 / provisional until
  10 rated attempts (configured by the implementation, as RATINGS.md
  permits; no canonical numbers exist). Glicko-2 math deferred; the
  stored deviation keeps the upgrade path open.
* Attempt integration (`progress/service.py`, single commit):
  server-decided eligibility (rated mode + account + validated
  correct/partial/wrong); practice, guest, and timeout/skipped/
  abandoned attempts never rate and keep NULL snapshots. Rated
  attempts stamp `rating_before/delta/after` on the attempt row.
  Idempotent re-application returns the stored pair unchanged
  (UNIQUE on `rating_events.attempt_id` as the DB backstop).
* Query API (`/me` scope, `player/router.py` thin; reads in
  `rating_engine/service.py`): `GET /me/ratings`,
  `GET /me/ratings/{slug}` (404 EXERCISE_NOT_FOUND vs
  RATING_NOT_FOUND), `GET /me/ratings/{slug}/history`
  (newest-first, paginated). No client rating-write endpoint exists
  (POST/PATCH/DELETE → 405). Cross-user reads miss (404/empty),
  anonymous → 401. External FIDE/Lichess/Chess.com ratings untouched
  and separate.
* Schema v4: `ensure_schema` upgrades Phase 1/2/3 DBs (new tables via
  `create_all`, attempt snapshot columns via idempotent ALTER; no
  backfill, no fabricated history); fresh boot + idempotency +
  v3→v4 data-preservation covered by tests; dev DB booted live at v4
  with users/attempts intact.
* Frontend: `RatingsSection` on the Progress page (per-exercise
  rating + موقت badge + rated-game counts; loading/empty/error
  states), `getRatings/getExerciseRating/getRatingHistory` transport
  (`api/client.ts`), 5 Persian strings in `fa.ts`; RTL preserved,
  44px targets, display-only (no rating math in the client). 6 new
  frontend tests (section states + transport); 15 existing fixtures
  extended with the new snapshot fields.
* Runtime verified live (13/13): register → login → empty ratings →
  rated attempt moves rating → detail/history match → practice
  no-op → second rated appends → cross-user isolation → Phase 3
  endpoints intact → legacy rows preserved.
* Intentional deferrals: Glicko/Glicko-2, XP/achievements/streaks/
  leaderboards, admin rating correction, adaptive difficulty,
  analytics time ranges (all later phases).

  (Phase 05 note: XP/achievements/streaks are now implemented per the
  Phase 05 scope above; leaderboards, mastery, goals, badges, and
  personal records remain deferred.)

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
Area: cPanel live deployment
Current limitation: `.cpanel.yml` is validated (YAML parses, explicit
paths resolve, no secrets/wildcards/excluded content) but a live
cPanel Git deploy was never executed (no account access); DEPLOYPATH,
Python-App wiring, env values, DB location, and static hosting of the
locally built `frontend/dist/` are operator steps.
Impact: Deployment configuration is ready but unproven end-to-end.
Required follow-up: operator deploy + checklist before Stable 1.0.0.
```

```text
Area: Architecture docs
Current limitation: docs/platform/ARCHITECTURE.md and DATA_MODEL.md are byte-identical (both hold the data-model text).
Impact: No implementation impact; architecture boundaries live in code + AGENTS.md.
Required follow-up: Docs fix outside any implementation phase.
```

```text
Area: Coach/Parent scoped capabilities
Current state (Phase 9): COACH/PARENT keep the player capability set
plus relationships.create/accept/revoke; related-student access is
granted only by an ACTIVE relationship of the matching kind, checked
per request at the object level (verified by tests + live runtime
checks). No global coach/parent data access exists.
Required follow-up: none (adaptive training arrives in Phase 10).
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

* backend tests: 1149 passed, 0 failed (`pytest`; includes 19
  new active-role tests in `tests/test_active_roles.py`, 8 new
  bootstrap tests in `tests/test_admin_bootstrap.py`, plus the Phase
  12 v11-upgrade contract updates; other suites include 28 account
  tests in `tests/test_accounts.py`, 15 player-platform tests in
  `tests/test_player_platform.py`, 19 rating tests in
  `tests/test_ratings.py`, 27 gamification tests in
  `tests/test_gamification.py`, 28 admin tests in
  `tests/test_admin.py`, 18 content/generator tests in
  `tests/test_content_lifecycle.py`, 21 analytics tests in
  `tests/test_analytics.py`, 19 relationship tests in
  `tests/test_relationships.py`, 33 adaptive tests in
  `tests/test_adaptive.py`, 21 support/notification tests in
  `tests/test_support_notifications.py` plus the Phase 12 v11-upgrade
  contract updates)
* frontend tests: 345 passed (`npm test`, 40 files; includes 10
  auth-context/login/protected-account tests, 14 player
  transport/page/nav tests, 6 rating transport/section tests, 7
  gamification transport/section tests, 15 admin
  transport/guard/page/nav tests, 4 content-lifecycle/
  generator transport/page tests, 8 analytics section/page tests,
  17 relationship transport/page tests, 9 adaptive
  transport/section tests, 14 support/notification
  transport/page tests, and 12 new active-role tests: 4 transport
  (details/roles/login-with-role/switch), 3 login selection, 3
  account switcher, 1 guard/nav active-role, 1 context switchRole)
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
