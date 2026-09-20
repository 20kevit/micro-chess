# MicroChess — Pricing, Subscriptions, Entitlements, Coupons, Attribution, Payments

Status: accepted. Current product state: **free beta** (`payment_provider = none`).
No payment gateway is integrated and none is required for registration or use.

## 1. Model chain

```text
Product (MicroChess)
  → Plan (free / premium, data rows in billing_plans)
    → Price versions (immutable rows in billing_plan_prices)
      → Subscription (one user's grant + frozen snapshot)
        → Entitlements (resolved server-side from plan + status)
          → Feature access (can_access / require_entitlement)
```

Separately:

```text
Campaign (where users came from)
  → Coupon (code bound to a campaign)
    → Attribution (first-touch permanent + last-touch informational)
      → User
```

And separately (future):

```text
Subscription → Payment (snapshot + provider ref) → PaymentProvider
```

## 2. Plans and prices (data-driven)

- Plans are rows, not code. `GET /api/v1/billing/plans` lists active
  plans with active price versions. Business logic never hard-codes amounts.
- Price versions are append-only: `POST /api/v1/admin/billing/plans/{code}/prices`
  creates version N+1. Old subscriptions keep the snapshot they were
  created under (`plan_code`, `price_amount_minor`, `currency`, `coupon`).
- **No commercial price is decided.** The `premium` plan seeds with NO
  price row, so paid checkout is structurally disabled until an operator
  configures a price. Never present a seed value as the real price.
- Enabling paid checkout later = configure a premium price version AND
  plug in a provider. No logic rewrite: `paid_checkout_enabled()` checks
  both (`app/modules/billing/service.py`).

## 3. Entitlement matrix (beta-safe)

Free accounts keep everything the beta ships today:

| Feature | Free | Trial / Paid |
|---|---|---|
| basic_training, practice_access, progress_tracking | ✓ | ✓ |
| recommendations (basic), basic_xp_streak | ✓ | ✓ |
| coach_features, parent_features | ✓ | ✓ |
| advanced_analytics | — | ✓ |
| advanced_personalization | — | ✓ |
| personalized_training_package (future; external FIDE/Lichess/Chess.com NOT integrated) | — | ✓ |
| speed_training, premium_training_content | — | ✓ |

Rules: single resolver `subscription_access()`; routes use
`require_entitlement(feature)`; frontend is never authoritative (403
`premium_required` for free sessions on premium surfaces). Unknown
features deny by default. No existing endpoint was paywalled.

## 4. Subscription lifecycle

`pending → trialing/active → expired/cancelled` (`past_due` reserved for
the future provider). Details:

- Registration ensures an `active` free subscription (`source=free_beta`).
- Free/trial/paid are distinct (`plan_code` + `status` + `source`).
- Expiry is lazy on read (no cron at this scale); every transition
  appends a `billing_subscription_events` row + audit log.
- Cancellation keeps already-granted time until `current_period_end`.
- Paid activation happens ONLY in `activate_paid_subscription()` from a
  `BillingPayment` with status `verified` (set exclusively by provider
  webhook verification). No browser-triggered activation path exists.

## 5. Coupons

Types: `percent` (1–100), `fixed` (minor units), `free_trial` (days).
Fields: code (normalized UPPER), campaign, active flag, validity window,
`max_redemptions`, `max_per_user` (default 1), applicable plans (empty =
all), `min_amount_minor`, `first_time_only`, `trial_days`.

Server-side validation order: exists → active → dates → per-user limit →
global cap → plan eligibility → first-time/trial rules → price math from
the live price table (never client math). Rejections are audited
(`billing.coupon_rejected`); only applied uses get rows.

- `free_trial` coupons grant a `trialing` premium subscription
  immediately — no gateway needed. **One promotional trial per user
  across all trial coupons** (`trial_already_used`).
- `percent`/`fixed` coupons record a `pending` subscription + `pending`
  payment intent; they activate only after provider verification.
- Redemption is idempotent via `idempotency_key` (replays return the
  existing row; no duplicate trials, subs, or payments).

## 6. Group codes and attribution

Admin creates a campaign (`abadeh-chess-group`, source/medium/content)
then codes bound to it (`ABADEH1405`, `SHIRAZ1405`, `COACHALI`, …).
A coupon code alone implies its campaign at registration.

URL scheme: `/?campaign=<slug>` / `/?ref=<slug-or-code>` /
`/?coupon=<CODE>`. Touches persist in localStorage
(`microchess.attribution.v1`, first-touch + last-touch) so they survive
landing → register → login, then the server stores one
`billing_attributions` row per user: **first-touch write-once**,
last-touch refreshed. No personal data is stored.

Reporting (`GET /api/v1/admin/billing/report`): per campaign —
registrations, redemptions, trials, paid. Queryable raw tables back it.

## 7. Payments (future boundary)

`BillingPayment` stores: user, subscription, frozen commercial snapshot,
currency, coupon, provider code (today always `none`), provider ref,
status (`pending/requires_action/verified/failed/cancelled`),
idempotency key, verification metadata. Never card data or secrets.

Vendor code lives only behind `PaymentProvider`
(`app/modules/billing/providers.py`; same isolation rule as
`audio/ports.py`). `NullProvider` fails closed on create and verify.
Integration checklist (when the gateway is chosen):

1. Implement `PaymentProvider` (create intent + `verify_callback` with
   server-to-server signature check); register in `get_provider()`.
2. Add webhook route that calls `verify_callback()` then flips the
   payment to `verified` — never trust `POST /payment/success`.
3. Call `activate_paid_subscription()` from the verified payment.
4. Configure the commercial premium price version via admin API.
5. Never store card data; keep snapshots frozen.

## 8. Security rules

Backend is authoritative for price, discount, trial length, plan, and
status. Frontend/API never accept those from the client. Covered by
`backend/tests/test_billing.py`: expired/inactive/future/unknown codes,
caps, per-user limits, wrong-plan, invalid discounts, duplicate and
replay redemption, client price/discount injection (ignored), direct
premium calls (403), anonymous billing access (401), unverified
activation refusal, idempotent retries.

## 9. Admin

`GET/POST /api/v1/admin/billing/campaigns`, `GET/POST/PATCH
/api/v1/admin/billing/coupons`, `GET .../report|redemptions|
subscriptions|payments`, `POST .../plans|plans/{code}/prices`
(capabilities `billing.read` / `billing.manage`, ADMIN-held).

## 10. Schema

v15 tables (`billing_plans`, `billing_plan_prices`,
`billing_subscriptions`, `billing_subscription_events`,
`billing_campaigns`, `billing_coupons`, `billing_coupon_plans`,
`billing_coupon_redemptions`, `billing_attributions`,
`billing_payments`). Migration is a `create_all` no-op step like prior
phases; existing accounts gain free access lazily. Portable types only.
