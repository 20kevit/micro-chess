# P11 — Personalized Onboarding, Daily Journey, Retention & Notifications

Implemented (schema v16). This document records repository reality.

## 1. What was built

- **Phone verification**: `phone` (canonical E.164-ish) + `phone_verified`
  on `users`; `phone_otps` challenges (SHA-256 hash at rest, 5-minute
  TTL, single-use, 5 attempts, 60s resend cooldown, no OTP in logs or
  API responses). Collected at registration (optional, never blocks),
  verified via `POST /me/phone/start|resend|verify`.
- **SMS abstraction**: `app/modules/sms/ports.py` (`SmsProvider` →
  `TestSmsProvider` default, `KavenegarProvider` production adapter via
  stdlib HTTPS). Credentials only from the environment; failures are
  safe (row persists with `sent=False`, client retries via resend —
  no duplicate send inside one call).
- **Onboarding**: `onboarding_profiles` (experience, play frequency,
  optional FIDE/Lichess/Chess.com, goal, intensity, timezone,
  onboarding/placement flags). External signals mirror into the
  existing `player_external_identities` table (self-report only).
  No long questionnaire: 4 conversational steps.
- **Placement**: `GET /me/placement` returns up to 3 deterministic
  recommendations from the existing recommendation engine over real
  published puzzles; external ratings are an initial signal only
  (`ability_for` already implements this). `POST /me/placement/complete`
  marks placement done.
- **Training plan**: `GET /me/plan` — Persian headline/summary/goal text
  plus the current focus exercise. No internal scores exposed.
- **Daily quests**: `daily_quest_days` (user, local_date, timezone) +
  `daily_quests` (slot 1..3, kind core/review/challenge,
  exercise/puzzle reference, target/progress, idempotent completion).
  Selection reuses recommendation + adaptive signals (no parallel
  engine). Stable per local day (unique constraint + read-back, never
  regenerated on refresh). Completion derives progress from
  authoritative attempts; rewards reuse the existing XP/streak system
  (attempts already earn XP — no second ledger). User timezone comes
  from onboarding (`Asia/Tehran` default); server timezone is never
  used for day boundaries.
- **Daily Journey home**: authenticated PLAYER home is the journey
  (phone gate → onboarding gate → journey). Quest cards link into the
  exercise with `?quest=<id>`; a sticky banner returns to `/journey`.
  After 3/3: completion state + optional extra practice (never a trap).
- **Notifications**: existing domain extended, not duplicated. New
  categories (journey/reminder/reward/system) and channels
  (web_push/telegram/bale/sms) registered in
  `notifications/models.py` + stub providers. New `notify` module owns:
  push subscriptions, Telegram/Bale one-time expiring link tokens
  (bot webhook with shared secret, no arbitrary chat-id submission,
  unlink), extended preference matrix (conservative defaults: only
  in_app on), deduped reminders (`reminder_logs`, opt-in + incomplete
  + rate-limited), and product analytics events (`analytics_events`,
  allow-listed types only).
- **PWA/Web Push**: `manifest.webmanifest` + `sw.js` (push/click only,
  no caching yet), permission asked only in notification settings
  after value is shown, denied permissions respected. iOS limitation:
  Web Push requires the installed Home Screen web app; the UI makes
  no native-app claims.
- **Admin**: `GET /admin/journey/overview` (funnel counts, quest
  completion rate, channel links, delivery failures, event counts —
  no phone numbers, no OTP data) and
  `GET /admin/system/provider-health` (configured/not-configured only,
  never secrets).
- **Analytics**: allow-listed P11 events via `POST /me/analytics`
  (onboarding/placement/quest/journey/push/return).

## 2. Reused, not duplicated

Recommendation, Adaptive, Skill State, Mastery, Rating, Evidence,
Gamification (XP/streak/achievements), Progress/Attempts, Player
identities, Notifications (rows/deliveries/preferences). Quest rewards
are the XP/streak the underlying attempts already earned.

## 3. Environment variables (deployment prerequisites)

```text
SMS_PROVIDER=test|kavenegar        # default test (no real SMS)
SMS_KAVENEGAR_API_KEY=             # Kavenegar API key (manual account)
SMS_KAVENEGAR_SENDER=              # Kavenegar sender line/number
VAPID_PUBLIC_KEY= / VAPID_PRIVATE_KEY= / VAPID_SUBJECT=
TELEGRAM_BOT_USERNAME= / TELEGRAM_BOT_TOKEN=   # via @BotFather (manual)
BALE_BOT_USERNAME= / BALE_BOT_TOKEN=           # via Bale bot setup (manual)
BOT_WEBHOOK_SECRET=                # shared secret for /notify/bot/link
VITE_VAPID_PUBLIC_KEY=             # frontend build-time (matches VAPID_PUBLIC_KEY)
```

Manual external setup that cannot be completed from the repository:
Kavenegar account + sender line approval; Telegram bot creation via
@BotFather (username + token); Bale bot creation + token; VAPID key
generation. Until provided, the test provider serves OTP locally and
external channels report unconfigured health without breaking any flow.

## 4. Reminders

`notify.service.send_due_reminders()` is a library function for an ops
cron/job (not wired to page views, to prevent spam): only opted-in
channels, only incomplete local-today journeys, one log row per
(user, day, channel), first reminder only after onboarding exists.

## 5. Tests

Backend `tests/test_p11_journey.py` (23 tests: OTP lifecycle incl.
replay/expiry/cooldown/attempt limits, quests incl. stability/IDOR/
idempotency/timezone, prefs/push/linking/reminders/analytics/admin).
Frontend `JourneyPage.test.tsx` + `OnboardingFlow.test.tsx`, updated
`HomePage.test.tsx` + `NotificationsPage.test.tsx`.

## 6. Known pre-existing failures (not P11, untouched modules)

- `test_unknown_route_has_error_envelope` (expects `HTTP_404`, installed
  Starlette yields `NOT_FOUND`), `test_material_comparison`
  distribution seed, `test_spa_frontend::test_no_mount_without_bundle`
  (committed `backend/static` present), config/bootstrap tests under
  the production `.env` — all pre-existing/environmental.
