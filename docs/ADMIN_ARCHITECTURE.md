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
