# MicroChess — Development Roadmap

> Phase-by-phase build order after the documentation phase.
> Each phase needs an **approved plan** before implementation, and tests + review
> before merge: `Documentation → Approved Plan → Implementation → Tests → Review`.
> Status labels: `DONE (verified)` = in code with tests · `PARTIAL` = exists but
> incomplete · `TODO` = not started. Evidence: `SCHEMA_VERSION=11`, 19 registered
> exercises (14 full practice+speed, 5 seeded-only), 51 backend test files.

Ordering note vs the mission baseline: the mission proposed Phase 0 (concepts)
first, then content → student → skill → recommendation → coach → academy. The
audit shows **platform, accounts, attempts, ratings-interim, gamification,
admin, and relationships already exist**, so this roadmap keeps the mission's
phase *content* but reorders execution to (a) lock decisions first, (b) close
content/authoring gaps that block 4 modules, (c) fix data-capture gaps before
they compound, then (d) build skill → recommendation → coach depth → academy →
external → AI → monetization. Reason for every deviation is recorded inline.

---

## Phase 0 — Product Foundation (TODO; documentation + decisions only, no code)

Goal: make every later phase decidable. Closes mission §2–§10 concept work.

- [ ] Approve skill taxonomy derived from the 19 exercises (blueprint §3 Proposed → Accepted)
- [ ] Approve user-level vs puzzle-level + suitability rule (blueprint §8)
- [ ] Approve mistake taxonomy core + per-exercise types (blueprint §9)
- [ ] Approve mastery/evidence rules + learning-loop stages (blueprint §10)
- [ ] Approve full puzzle lifecycle incl. Flagged/Rejected + blacklist fingerprint (blueprint §16–§17)
- [ ] Approve coach assignment model: multi-puzzle pack vs single-exercise (blueprint §13 gap)
- [ ] Resolve guest-play conflict: teaser scope vs hard login gate (blueprint §22.1)
- [ ] Confirm final rating formula stays **undecided**; label current Elo-style **interim**
- Exit criteria: `DECISIONS.md` has no blocking Open item for Phase 1; `REQUIREMENTS.md` Phase-0 reqs Accepted.

## Phase 1 — Content & Puzzle Engine (PARTIAL → complete)

Existing: puzzle lifecycle `draft→validated→reviewed→approved→published→retired`,
`answer_json` immutability, archive, `content_hash` dedup, 14 generators, graceful
failure paths. Missing (the documented content blocker):

- [ ] Admin position-entry workflow (unblocks `is-checkmate`, `opening-traps`,
  `reverse-opening`, `castling-rights` expansion)
- [ ] Authoring flow: search-existing → generate → Draft → suggested answer →
  edit → validate → preview → approve/publish (blueprint §14)
- [ ] Explicit reject + rejected/blacklisted fingerprint (never re-recommend,
  never blindly regenerate)
- [ ] Safe-generation-failure UX (`No valid puzzle available`)
- Exit criteria: all 19 exercises generatable or explicitly seeded-only by
  decision; 4 content-blocked modules resolved.

## Phase 2 — Student Core (PARTIAL → complete)

Existing: register/login/JWT, guest sessions + migrate, active-role switching,
19 exercise routes, practice + 60s speed, attempt history, progress/profile/
account pages, `localProgress.ts`. Missing:

- [ ] Mount the real Student Dashboard as logged-in home; separate Public Home
  (marketing, samples, pricing, FAQ) from dashboard per blueprint §18
- [ ] Enforce the approved guest policy (Phase 0 decision)
- [ ] Exercise catalog + assignment consumption (student sees coach work, submits,
  sees results)
- [ ] Close attempt data-capture gaps **before** skill work: mistake codes
  (reserved), assignment/assessment context, difficulty snapshot, retries,
  abandonment/timeout flags — see `REQUIREMENTS.md` data requirements
- Exit criteria: a logged-in student can train, be assigned work, and review
  history from the dashboard; attempts carry all Phase-3-needed context.

## Phase 3 — Skill Engine (TODO; needs Phase 0 + Phase 2 data)

- [ ] Skill-evidence pipeline (attempt → mistake classification → skill evidence)
- [ ] Mistake taxonomy implementation (core + per-exercise)
- [ ] Skill profile + user level + exercise/puzzle level (replaces reliance on
  interim per-exercise Elo; final formula decided here)
- [ ] Mastery-evidence rules
- Exit criteria: per-user skill profile renders from real evidence; interim
  rating labeled or retired by decision.

## Phase 4 — Recommendation (TODO; needs Phase 3)

Existing: `adaptive` selection logging (`shown/accepted/completed/skipped`).
Missing: everything formulaic.

- [ ] User model + suitability calculation (blueprint §8 rule)
- [ ] Personalized recommendations + Personalized Training Pack
  (level, weaknesses, goal, time, recency, mistakes, review needs)
- [ ] Keep Speed as assessment/fun/benchmark input, not the training backbone
- Exit criteria: suitable-next-exercise served and logged; pack generation works.

## Phase 5 — Coach Depth (PARTIAL → complete; needs Phase 3–4 for Mode B)

Existing: relationships, single-`exercise_slug` assignments, student progress/
attempts/ratings views. Missing:

- [ ] Mode A complete: multi-puzzle ordered pack + timing + mode + deadline +
  instructions + group targeting; 10-question assessment + compare dashboard
- [ ] Mode B (skill/goal assignment via recommendation) — after Phase 4
- Exit criteria: coach runs a 10-question group test and compares results.

## Phase 6 — Academy (TODO; needs Phase 5)

- [ ] Academy accounts, coach management
- [ ] Custom content/curriculum, private to academy, separate from public exercises
- [ ] Academy analytics
- Exit criteria: academy authors private content and assigns it to its students.

## Phase 7 — External Games (TODO)

- [ ] Lichess/Chess.com integration, game import, position extraction,
  pattern detection → skill mapping → evidence → recommendation
- [ ] External-rating verification (`is_verified` pipeline)
- Exit criteria: imported game produces skill evidence.

## Phase 8 — AI (TODO; explicitly after data + skills exist)

- [ ] Mistake explanations, weakness analysis, personal coaching, training plans,
  game analysis, tutor interaction, generation assistance
- Constraint: architecture must stay AI-addable (raw answers + audit preserved).
- Exit criteria: at least mistake explanation + weakness analysis live.

## Phase 9 — Monetization / Scale (TODO; decision first)

- [ ] Pricing decision (still Open: Free+Premium / individual / parent / coach /
  academy per-student / fixed / hybrid)
- [ ] Subscriptions, plans, usage limits, billing, scale analytics
- Exit criteria: chosen model enforced; no model chosen → phase stays closed.

---

## Phase map to mission baseline

| Mission proposal | This roadmap | Reason if changed |
|---|---|---|
| Phase 0 concepts | Phase 0 (same) | Unchanged — decisions first |
| Phase 1 content engine | Phase 1 (same position) | Unchanged — unblocks 4 modules |
| Phase 2 student core | Phase 2, includes data-capture fixes | Audit: student exists but dashboard/guest/attempt-context gaps must close before skill work |
| Phase 3 skill engine | Phase 3 (same) | Unchanged |
| Phase 4 recommendation | Phase 4 (same) | Unchanged |
| Phase 5 coach | Phase 5, Mode B explicitly after Phase 4 | Audit: Mode A partial exists; full pack + Mode B need skill/recommendation |
| Phase 6 academy → 9 scale | Phases 6–9 (same order) | Unchanged |

## What must be approved before Phase 1 starts

1. Skill taxonomy v1; 2. user/puzzle level + suitability rule; 3. mistake
   taxonomy; 4. mastery rules; 5. full lifecycle + blacklist; 6. coach pack
   shape; 7. guest policy; 8. rating formula stays open + interim label.
