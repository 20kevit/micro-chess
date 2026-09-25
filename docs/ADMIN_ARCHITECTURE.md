# Admin Architecture

Admin is a business-domain operations console over the existing
MicroChess platform. It introduces no parallel domain systems: every
metric, transition, and price is derived from or enforced by the
authoritative backend modules documented in `docs/REPOSITORY_MAP.md`.

## 1. Information architecture

Business-domain navigation (never raw table names):

```text
Admin
|-- Dashboard (/admin)
|-- Exercises (/admin/exercises, /admin/exercises/:slug)
|-- Puzzles (/admin/puzzles)
|-- Generators (/admin/generators)
|-- Review Queue (/admin/review-queue)
|-- Users (/admin/users, /admin/users/:id)
|-- Analytics (/admin/analytics: platform, retention, learning, recommendations)
|-- Sales (/admin/sales: revenue, subscriptions, payments, plans, coupons, campaigns)
|-- Support (/admin/support)
|-- Product Insights (/admin/insights)
|-- System Health (/admin/system)
`-- Audit Log (/admin/audit)
```

Shared shell: `frontend/src/components/admin/AdminLayout.tsx`
(Persian labels, RTL, `t()` keys in `frontend/src/i18n/fa.ts`).

## 2. Authorization

Server-side only, via `backend/app/core/capabilities.py`.
Frontend `RequireAdmin` is a UX guard. New endpoints reuse existing
capabilities (no new capability was needed):

| Endpoint group | Capability |
|---|---|
| `/admin/review-queue` | `puzzles.manage` |
| `/admin/dashboard-extended`, `/admin/insights`, `/admin/system/health` | `admin.overview` |
| `/admin/analytics/retention` | `analytics.read_platform` |
| `/admin/analytics/learning`, `/admin/analytics/recommendations` | `analytics.read_exercise` |
| `/admin/sales/overview` | `billing.read` |
| `/admin/support/stats` | `support.read` |
| `/admin/users/{id}/profile` | `users.read_private` |
| `PATCH /admin/billing/campaigns/{slug}` | `billing.manage` |
| `PATCH /admin/billing/plans/{code}` | `billing.manage` |
| `PATCH /admin/billing/prices/{id}` | `billing.manage` |

Tests (`backend/tests/test_admin_ops.py`) assert 401 anonymous and
403 authenticated-non-admin on every new endpoint.

## 3. API architecture

Thin routers (`admin/router.py`, `billing/router.py`) over domain
services. New read-only derivations live in
`backend/app/modules/admin/ops.py` (pure aggregations, never writes):

- `review_queue` — puzzles in validated/reviewed/approved/quarantined
  with severity (`quarantined` > high failure > awaiting review) and
  reasons; deterministic severity-then-age ordering.
- `retention` — real registration cohorts (UTC calendar days, last
  14 days) with D1/D7/D14/D30 activity (authenticated attempts only);
  cohorts under 5 users report null (insufficient data, never 0%).
- `learning_overview` — exercise usage plus `evidence` mistake,
  direction, and skill distributions.
- `recommendation_overview` — `adaptive_recommendations` funnel by
  status/reason/exercise (read-only; selection behavior untouched).
- `sales_overview` — subscriptions/payments by status, verified-payment
  revenue sum, redemption count (all from `billing_*` tables).
- `product_insights` — deterministic rules (low supply, review depth,
  high failure, payment failures, open support). Signals only, no AI
  certainty.
- `system_health` — `SELECT 1` connectivity, `SCHEMA_VERSION` match,
  puzzle counts. Degrades to `ok: false`, never leaks secrets.
- `dashboard_extended` — today/week/month registrations, active users,
  attempt comparisons incl. previous week, sales rollup, 14-day series.

Billing admin lists gained `status`/`page`/`page_size` filters
(subscriptions, payments, redemptions) plus `GET /admin/billing/plans`.
Support staff list gained a `category` filter. Audit list gained an
`actor_id` filter.

No migration: everything derives from existing tables
(`SCHEMA_VERSION` stays 15).

Hardening additions (no new tables, no new capabilities):

- `GET /admin/users/{id}/profile` — 360° view: overview
  (registration, last active, roles, attempts), learning (per-exercise
  attempts, seen skills via `skill_state_for_user`, mastery via
  `mastery_for_user`, XP level, streak), commercial (current + recent
  subscriptions, first-touch attribution, redemptions, payments),
  timeline (registration, first attempt, subscription events,
  payments, redemptions, recommendations, support — every timestamp
  from a durable row, newest first, capped at 50). Strictly read-only:
  it calls no `ensure_*`/`get_or_create_*`, so viewing creates no
  subscription/XP/streak rows (covered by test).
- `GET /admin/exercises` — enriched rows (`published_count`,
  `needs_review_count`, `success_rate`, `low_supply`) from 3 grouped
  queries; filters `active`, `low_supply`, `needs_review`.
- `GET /admin/analytics/exercises/{slug}` — added `supply_by_status`,
  `difficulty_distribution`, windowed `mistake_distribution` (top 10),
  `recommendation_outcomes`.
- `GET /admin/dashboard-extended` — added per-day `revenue_minor`,
  `redemptions`, `new_subscriptions` (14-day series), `attribution`
  (reused `campaign_report`), `exercise_success` (top 8).
- Billing toggles (`campaigns/{slug}`, `plans/{code}`,
  `prices/{id}` `PATCH {is_active}`) — flag-only, history immutable,
  audited; coupon admin view gained `applicable_plan_codes`;
  redemptions gained `coupon_code` filter; payments expose
  `failure_reason`/`provider_ref`; subscriptions expose `user_id`.
- Campaign date fields were NOT added: the current product has no
  scheduling requirement, so no migration was justified.
- Subscriptions stay read-only in Admin: `cancel_subscription`
  enforces owner identity and `activate_paid_subscription` requires a
  verified payment, so no safe manual-override primitive exists;
  Admin surfaces status instead of inventing a "set active" shortcut.
- Generators UI derives supported vs unsupported exercises from the
  registry + exercise catalog at render time (no second list).

## 4. Analytics definitions

- Active user: >= 1 authenticated attempt in the window (guest attempts
  excluded until migration, same as Phase 8 analytics).
- Successful attempt: `result == "correct"`; accuracy denominator is
  ALL attempts (matches `progress_summary` contract).
- Revenue: sum of `final_amount_minor` over `status == "verified"`
  payments only (currency IRR).
- Registration source: persisted `billing_attributions` first-touch
  (reported per campaign via `billing.service.campaign_report`).
- Coupon usage: durable `billing_coupon_redemptions` rows.
- Observed difficulty: accuracy-derived per puzzle, minimum 5 attempts
  (`insufficient_data` below threshold), never written to `Puzzle`.
- Time windows: server-side naive UTC, matching the repo convention.

## 5. Puzzle lifecycle and generation pipeline

Lifecycle (unchanged, server-enforced in `admin/service.py`):

```text
draft -> validated -> reviewed -> approved -> published ⇄ quarantined
```

Generation (`generators/` registry, 3 codes) enters candidates as
`validated` and follows the same gates. The UI never publishes
directly: Review Queue exposes only valid next actions with
confirmation dialogs; invalid transitions return 409.

## 6. Audit log

Append-only `audit_logs`. All puzzle lifecycle, role, exercise,
coupon/campaign/plan, support, and generator actions record actor,
action, entity, and secret-free metadata. New: filter by `actor_id`.

## 7. Commercial administration

Plans/prices are operator-configured with immutable price versions;
historical snapshots stay on subscriptions/payments. Paid checkout
remains disabled (`payment_provider = none`); Admin shows provider
state honestly instead of faking payments. No card data is stored or
displayed. Coupon validation/redemption is server-side and
idempotent; Admin can only toggle `is_active`.

## 8. Support

Tickets are the single conversation system (`open -> answered ->
closed`); "messages / issues / feedback" are views over ticket
status + free-form `category`, not a second system. User context on
tickets reuses existing admin user detail; no secrets exposed.

## 9. Exercise & Content Management (Phase 12)

Admin is the professional content-management surface for MicroChess:
an authorized admin operates the full content lifecycle without
database access, SQL, or code changes for normal operations.

Information architecture additions:

```text
Admin
|-- Exercises (/admin/exercises) + Workspace (/admin/exercises/:slug)
|   `-- tabs: overview | puzzles | generate | review | quality |
|       difficulty | learning | analytics | settings
|-- Puzzles (/admin/puzzles: server-side library, filters, bulk)
|-- Puzzle detail (/admin/puzzles/:id: preview, answer, difficulty,
|   rating, validation, lifecycle, usage, history)
|-- Puzzle editor (/admin/puzzles/new, /admin/puzzles/:id/edit:
|   Board Editor + typed Answer Editor + validate + save-as-draft)
|-- Content health (/admin/content-health: global supply view)
`-- Review Queue (/admin/review-queue: now links into puzzle detail)
```

Backend (`admin/content.py` over `admin/service.py`; no new tables,
no migration, no new capabilities):

- Answer contracts (`exercises/answer_contracts.py`): one typed
  contract per exercise validator (squares, moves, single_move,
  move_sequence, ordered_squares, single_square, square_or_color,
  choice, options, path, pieces, structured fallback). Served via
  `GET /admin/exercises/{slug}/answer-contract` with validator and
  generator availability flags.
- `POST /admin/puzzles/preview-validate`: authoritative validation
  of unsaved content (structural gates + FEN-derived answer replay
  through the registered validator). Never writes.
- Meaning edits of validated/reviewed/approved content via
  `PATCH /admin/puzzles/{id}` now apply the change and demote the
  puzzle to draft (`content_edited`, audited, history row) so gates
  are re-passed. Published/retired/rejected/quarantined stay
  immutable; exercise reassignment stays forbidden.
- `POST /admin/puzzles/bulk` (max 50): validate, approve_review,
  approve, publish, quarantine, release, reject, retire, restore.
  Per-item lifecycle gates, per-item failures, destructive actions
  require a reason; per-action capability (same as single-item
  routes); one summary audit row (`puzzles.bulk_<action>`).
- `POST /admin/exercises`: creation gated on a registered
  server-side validator (`exercise_not_implemented` otherwise);
  capability `exercises.create`.
- `GET /admin/exercises/{slug}/quality`: supply by status, review
  backlog, quarantined, difficulty coverage, validation failures,
  high-failure published puzzles (>= 5 attempts, >= 70% failure),
  success rate, avg duration, `supply_state` (healthy/attention/
  critical) with machine-readable `attention_reasons`. No composite
  quality score is invented.
- `GET /admin/exercises/{slug}/learning` (window 7/14/30/90d):
  usage, mistake distribution, canonical skills (primary/secondary
  from `evidence/taxonomy.py` plus evidence counts), adaptive
  recommendation outcomes. Read-only.
- `GET /admin/content-health`: per-exercise supply rows with
  reasons (`low_supply`, `review_backlog`, `quarantined_content`,
  `no_generator`); thresholds reuse `LOW_SUPPLY_THRESHOLD`.
- `GET /admin/puzzles/{id}/usage`: attempts, results, success rate,
  avg duration (nulls, never invented).
- `GET /admin/puzzles` gained `difficulty`, `source`, `search`
  (prompt/exercise/FEN), `rating_min/max`, `sort`/`order`.

Lifecycle map change: `reviewed -> draft` and `approved -> draft`
are now allowed, reachable only through the audited admin-edit
demotion in `update_puzzle` (no direct-transition endpoint exists,
so no step can be skipped by callers).

Frontend (`components/content/`, new pages, Persian RTL):

- `BoardEditor`: SVG pieces (never glyphs), place/remove/move,
  eraser, side to move, orientation, castling flags, en-passant,
  clear/reset, FEN text apply with parse errors. `dir="ltr"` island.
- `AnswerEditor`: one renderer per contract type; structured-JSON
  fallback only for exercise-specific shapes.
- Difficulty editor (1-5) and rating editor (100-3000, admin-only,
  never shown to players); changing difficulty never rewrites
  attempt snapshots (attempts store their own copies).
- Exercise creation is honest: unregistered slugs are refused
  server-side and explained in the UI; no fake database-only
  exercises.

Tests: `backend/tests/test_phase12_content.py` (22 cases) plus
updated `test_admin.py` lifecycle expectations; frontend
`lib/fenEditor.test.ts`, `pages/AdminContent.test.tsx`, updated
`AdminPages.test.tsx` / `AdminOps.test.tsx`.

## 10. Phase 13 Admin Control Center

Phase 13 keeps the existing domain services and adds an operator-first
workspace around them:

- `AdminLayout` is a collapsible RTL sidebar with Dashboard, Content,
  Users, Reports, and Sales groups. All Admin routes are nested under
  `/admin`; the player shell is not rendered for those routes.
- Exercise detail is the content entry point. Its tabs cover overview,
  puzzles, one-candidate generation, review, quality, difficulty,
  learning, analytics, and settings. The puzzle editor renders the
  exercise answer contract, board, position metadata, hints, source
  reference, and rating controls; unsaved validation is read-only.
- Generated candidates enter as `validated` and require review and
  approval. The generator screen never publishes or silently edits a
  candidate. Rejected candidates remain auditable.
- Safe draft deletion is intentionally narrow: it is available only for
  a manual, unpublished draft with no lifecycle history, validation,
  review, generator provenance, or attempts. Every other lifecycle
  action uses archive/quarantine/reject/retire and preserves history.
- Admin list endpoints expose `X-Total-Count`; audit supports action,
  target type/id, actor, and date-window filters. Puzzle library rows
  include a server-derived attempt count, and user rows include a
  non-secret verification channel summary.
- User detail combines account, verification, learning, commercial, and
  durable timeline data without exposing phone numbers, tokens, or
  provider secrets. Support tickets can be explicitly reopened by an
  authorized staff member; reopening is audited.
- System health distinguishes notification provider configuration from
  verification-channel availability. Telegram verification is disabled
  by default in production; the implementation remains available and can
  be re-enabled with `VERIFICATION_TELEGRAM_ENABLED=true` while Bale
  remains the safe default.

P13 focused backend coverage is in `backend/tests/test_p13_admin.py`
and `backend/tests/test_support_notifications.py`. Frontend coverage is
colocated in the `Admin*P13.test.tsx` files and the updated Phase 12
Admin tests. The normal gates remain `pytest`, `npm run typecheck`, and
`npm run build`.
