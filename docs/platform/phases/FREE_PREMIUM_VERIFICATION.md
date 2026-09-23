# Free/Premium Accounts & Phone Verification (schema v17)

Implemented. This document records repository reality.

## 1. Product rules

- Authentication is username + password only. No Google, no SMS OTP,
  no email auth, no passwordless login.
- Anonymous: landing/product info only; training endpoints stay
  authentication-protected.
- Free: username + password, no verified phone required, **10**
  completed exercise attempts per user-local calendar day.
- Premium: username + password, phone verified via Telegram **or**
  Bale, active subscription, **100** attempts per user-local day
  (a maximum entitlement, not a goal).
- All activation coupons currently issued are 100% discount: no
  payment gateway is involved. The Product → Plan → Subscription →
  Entitlements → Invoice/Payment/Coupon architecture is preserved so
  real payments can be enabled later without redesign.

## 2. Daily quota (server-authoritative)

- Module `app/modules/quota/`: `daily_usage` rows keyed
  `(user_id, local_date)` with the UTC window of that local day.
- Enforced inside `progress.service.submit_attempt` after validation
  and after every other rejection gate: only validated
  correct/partial/wrong attempts consume quota (terminal states and
  rejected submissions never count; one request consumes at most one
  unit). Speed sessions flow through the same function, so they are
  covered automatically.
- Limit resolution reuses billing entitlements
  (`subscription_access` → paid access ⇒ 100, else 10). No second
  entitlement system.
- Timezone: `users.timezone` (onboarding) with `Asia/Tehran`
  fallback; deterministic UTC windows. A mid-day timezone change
  lands inside the already-open window, so it cannot mint quota
  (enforced by the overlapping-window check).
- Over-quota submits are rejected with stable `403
  daily_quota_exceeded`. `GET /me/quota` exposes
  `{used, limit, remaining, plan, local_date, can_practice,
  upgrade_available}` (no hidden ratings, no billing internals).
- The Daily Journey stays 3 quests; quota appears only as a subtle
  «۷ از ۱۰» / «۱۷ از ۱۰۰» line plus the limit card with a single
  «دریافت حساب ویژه» CTA at the genuine upgrade moment.

## 3. Phone verification (Telegram/Bale contact sharing)

- Module `app/modules/verification/` (+ `bots.py` adapters).
- Verification is NOT authentication: Telegram/Bale never become a
  login identity.
- Flow: `POST /me/verification/sessions {channel}` → 6-digit pairing
  code + public bot address (no secret in any URL) → user sends the
  code to the bot → bot binds the chat and shows the official Share
  Contact button → provider delivers
  `contact{phone_number, user_id}` with the sender id → the backend
  requires `contact.user_id == sender id`, normalizes the phone
  server-side, rejects phones verified on another account (generic
  message, no leak), stores the stable platform id in
  `player_external_identities` (verified, unique per provider),
  writes the channel address, and sets
  `user.phone/phone_verified`. Sessions are single-use, 15-minute,
  attempt-capped, user-bound. Logout/login/device changes preserve
  verification.
- One phone belongs to one account (`phone_taken` is generic).
- Webhook `POST /verification/webhook/{channel}` (+ optional
  `/verification/webhook/{channel}/{secret}` path variant for Bale,
  which cannot send custom headers; the URL is operator-configured
  only, never user-facing, and excluded from access logs): shared
  secret (`X-Bot-Secret`) and/or Telegram per-bot secret token;
  idempotent;
  unknown/malformed updates answer 200 with no body; reply failures
  never block verification; no tokens/phones/secrets in logs.
- Bale uses the same Telegram-compatible wire (`tapi.bale.ai`)
  including `request_contact` keyboards and Contact updates (per
  docs.bale.ai); verified here with fixtures, pending live
  credentials for end-to-end confirmation.

## 4. Premium activation (invoice + 100% coupon, no gateway)

- Reuses billing: `ensure_premium_price` (operator-configurable via
  `PREMIUM_PRICE_MINOR`, admin-price-versionable), standard
  `validate_coupon`/`redeem_coupon` (all coupon rules apply:
  expiry, status, per-user/global limits, plan allowlist,
  first-time, min amount, transactional idempotent redemption),
  then `activate_zero_payment` for zero-final payments: payment
  marked `verified` with explicit zero-settlement metadata
  (final amount stays 0 — no fake charge is recorded) and a
  premium/active `coupon`-source subscription is created.
  Non-zero payables are honestly refused (`payment_required`):
  paid checkout does not exist in this phase.
- Endpoints: `GET /billing/me/premium/quote?coupon_code=` (invoice
  preview: price/discount/payable), `POST
  /billing/me/premium/activate {coupon_code}` (requires verified
  phone; idempotent replays). Rate-limited with the shared
  in-memory limiter family (no Redis).
- Frontend `/premium`: benefits, verification gate, invoice with
  coupon input, zero-amount activation, success state
  («حساب ویژه فعال شد»). Account page shows plan, daily usage,
  phone state, channel, and upgrade CTA. Pricing page premium CTA
  routes to `/premium`.

## 5. Admin, analytics, notifications

- `GET /admin/journey/overview` adds free/premium counts,
  per-channel verifications, activations, redemptions,
  users-at-limit, and event funnels (no phones, tokens, or secrets).
- New allow-listed analytics events: `registration_completed`,
  `daily_journey_started`, `daily_limit_reached`,
  `premium_upgrade_started`, `verification_channel_selected`,
  `verification_started/completed/failed`, `coupon_entered`,
  `coupon_redeemed`, `premium_activated`.
- Verification is transactional, not marketing: verifying never
  opts anyone into notifications; existing preferences respected.
  SMS is not a verification or reminder channel.

## 6. Security properties (reviewed)

- Username/password hashing, sessions, capabilities unchanged.
- Quota: owner-scoped rows, unique day keys, race-collapse on
  IntegrityError, timezone-hop guard, server-counted only.
- Verification: secret webhook, pairing-code attempt caps,
  single-use sessions, stable-id uniqueness (takeover protection),
  generic duplicate-phone responses, masked phone display.
- Coupons: server-side only, transactional, idempotent,
  replay-safe activation.
- No secrets in Git/tests/docs/logs/frontend; bot tokens env-only.

## 7. Bot setup (owner steps)

1. Create the Telegram bot via @BotFather → `TELEGRAM_BOT_USERNAME`,
   `TELEGRAM_BOT_TOKEN`; create the Bale bot → `BALE_BOT_USERNAME`,
   `BALE_BOT_TOKEN`.
2. Set `BOT_WEBHOOK_SECRET` (and optionally
   `TELEGRAM_WEBHOOK_SECRET`) in production env.
3. Point each provider webhook at
   `https://microchess.ir/api/v1/verification/webhook/{telegram|bale}`
   with the secret.
4. Check `GET /admin/system/provider-health` (configured flags
   only), send a real code → contact flow, confirm
   `verification_completed`.

## 8. Troubleshooting

- `daily_quota_exceeded` (403): quota consumed; check `/me/quota`.
- `phone_not_verified` (403 on activate): verify first via `/verify`.
- `payment_required` (422 on activate): coupon leaves a payable;
  paid checkout unavailable — issue/use a 100% coupon.
- `phone_taken`: number verified on another account (generic).
- Webhook 403: secret mismatch. Webhook 200 with no verification:
  expired/replayed/unknown code — take a fresh code in the app.
- Bot silent but verification completes: token missing or
  provider unreachable; verification itself is unaffected.
