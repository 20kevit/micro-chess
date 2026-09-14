# MicroChess — Requirements Matrix

> ID / description / priority (P0 must · P1 should · P2 nice) / status
> (`Implemented` in code+tests · `Partial` exists but incomplete ·
> `Planned` approved future · `Open` undecided) / phase / dependency.
> Evidence date 2026-09-14 (`SCHEMA_VERSION=11`, 19 exercises, 51 test files).
> Decisions: `docs/DECISIONS.md`. Order: `docs/ROADMAP.md`.

## Product

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-PROD-001 | Platform identity: skill assessment + training, self-use + academy complement, never coach replacement | P0 | Implemented (docs+arch) | 0 | DEC-001 |
| REQ-PROD-002 | Advantage via specific exercises, not puzzle counts; 6-question new-exercise gate | P0 | Planned (gate undecided as process) | 0–1 | DEC-013 |
| REQ-PROD-003 | Public Home (marketing, no real guest exercises) vs Student Dashboard split | P0 | Partial (guest play exists; DashboardPage unmounted) | 2 | DEC-012, DEC-O03 |
| REQ-PROD-004 | Persian-first RTL UX; backend-authoritative correctness | P0 | Implemented | — | DEC-004 |

## Student

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-STU-001 | Register/login, JWT sessions, role switching, guest migrate | P0 | Implemented | — | — |
| REQ-STU-002 | Student dashboard: training, progress, skills, assignments, history, packs | P0 | Partial (pages exist, dashboard unmounted, no packs) | 2–4 | Phase 3–4 |
| REQ-STU-003 | Exercise catalog + practice + 60s speed for full modules | P0 | Implemented (14 full; 5 seeded attempt-only) | 1 | Phase 1 |
| REQ-STU-004 | Attempt history + progress views (own + coach/parent views) | P0 | Implemented | — | — |
| REQ-STU-005 | Personalized training pack (level, weaknesses, goal, time, recency, mistakes, review) | P1 | Planned | 4 | Phase 3 |

## Exercise

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-EX-001 | 19 registered validators, no per-exercise branches in core flow | P0 | Implemented | — | — |
| REQ-EX-002 | Generators for all generatable modules; seeded-only set explicitly decided | P0 | Partial (14 gen; 5 seeded-only; 4 content-blocked) | 1 | Phase 0 |
| REQ-EX-003 | Per-exercise specs for all 19 (today only 10 files in `docs/exercises/`) | P1 | Partial | 1 | — |
| REQ-EX-004 | Opening only as problem-oriented exercises (reverse/traps) | P0 | Implemented | — | DEC-003 |
| REQ-EX-005 | Speed mode only where pedagogically valid (assessment/fun/benchmark) | P1 | Implemented (14 have, 5 excluded) | — | DEC-009 |

## Puzzle

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-PUZ-001 | Lifecycle with history (draft→…→published→retired), answer immutability, archive-not-delete | P0 | Implemented (6-state) | — | DEC-011 |
| REQ-PUZ-002 | Full 8-state model incl. Generated/Active/Flagged/Rejected + transitions | P1 | Planned | 1 | DEC-P02 |
| REQ-PUZ-003 | Rejected/blacklisted fingerprint: never re-recommend, never blindly regenerate | P0 | Open (missing) | 1 | DEC-011 |
| REQ-PUZ-004 | Admin authoring flow: search→generate→draft→suggested answer→edit→validate→preview→approve/publish | P0 | Partial (CRUD+transitions exist; no entry workflow/preview) | 1 | — |
| REQ-PUZ-005 | Duplicate prevention via content hash | P0 | Implemented | — | — |
| REQ-PUZ-006 | Graceful generation failure (`No valid puzzle available`, no crash) | P0 | Implemented (pattern) | 1 | DEC-011 |

## Skill

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-SKL-001 | Taxonomy extracted from exercises (generic buckets rejected) | P0 | Planned (8 clusters proposed) | 0 | DEC-002, DEC-P01 |
| REQ-SKL-002 | Skill evidence pipeline (attempt→mistake→evidence) + skill profile + user/item levels | P0 | Planned | 3 | Phase 2 data |
| REQ-SKL-003 | Final rating formula (Glicko-2/Elo/custom undecided; current Elo-style = interim) | P0 | Open | 3 | DEC-O01 |
| REQ-SKL-004 | Mastery requires sufficient evidence, never single attempt/score | P0 | Planned | 3 | DEC-008 |
| REQ-SKL-005 | Mistake taxonomy: core + exercise-specific; reserved, then implemented | P0 | Open (codes missing; raw answers preserved) | 3 | DEC-007 |

## Assessment

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-ASM-001 | Practice / Speed / Assessment modes per exercise (assessment = supervised pack) | P0 | Partial (practice+speed live; assessment = proposed pack) | 5 | DEC-P03 |
| REQ-ASM-002 | 10-question group test: same items, deadlines, per-student results, compare view | P0 | Planned (single-exercise assignment only today) | 5 | DEC-010 |

## Recommendation

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-REC-001 | Suitability-based recommendation (level distance + skill + history + recency + goal); external rating never absolute gate | P0 | Planned (`adaptive` logs selection only) | 4 | DEC-006 |
| REQ-REC-002 | Personalized training pack; no global daily challenge as goal | P1 | Planned | 4 | DEC-009 |

## Coach

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-COA-001 | Coach↔student relationships + student progress/attempts/ratings views | P0 | Implemented | — | — |
| REQ-COA-002 | Mode A: specific multi-puzzle ordered pack (puzzles, order, timing, mode, deadline, instructions, targets) | P0 | Partial (single exercise_slug + note + due_at) | 5 | DEC-P03 |
| REQ-COA-003 | Mode B: skill/goal assignment via recommendation | P1 | Planned | 5 | Phase 4 |
| REQ-COA-004 | Assessment results + compare + (future) weakness views | P0 | Partial (views exist; compare/weakness future) | 5 | Phase 3 |

## Academy

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-ACA-001 | Academy accounts, coach management, Academy→Coach→Students | P1 | Open (no Academy role) | 6 | DEC-O06 |
| REQ-ACA-002 | Custom content/curriculum private to academy, separate from public exercises | P1 | Open | 6 | Phase 5 |
| REQ-ACA-003 | Academy analytics | P2 | Open | 6 | — |

## Admin

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-ADM-001 | Dashboard, users/roles, exercise enable/disable, puzzle CRUD + transitions + history, generator runs, audit | P0 | Implemented | — | — |
| REQ-ADM-002 | Position-entry workflow (unblocks 4 content-blocked modules) | P0 | Open (documented blocker) | 1 | Phase 0 |
| REQ-ADM-003 | Preview + suggested-answer review + reject flow | P0 | Open | 1 | DEC-P02 |

## Authentication

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-AUTH-001 | Register/login/logout, server-revoked sessions, prod secret guard, rate limits | P0 | Implemented | — | — |
| REQ-AUTH-002 | Roles PLAYER/COACH/PARENT/ADMIN + active-role switching; Academy + Parent(future) model | P0 | Partial (4 roles live; Academy missing) | 6 | — |
| REQ-AUTH-003 | Guest sessions + migration to users | P1 | Implemented | — | DEC-O03 |

## Analytics

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-ANL-001 | Per-exercise ratings history, gamification (XP/streaks/achievements), player + admin analytics | P0 | Implemented (interim rating) | — | DEC-O01 |
| REQ-ANL-002 | Skill-profile analytics: per skill/exercise/difficulty, response time, mistakes, retention, trends | P0 | Planned | 3–4 | Phase 3 |

## Attempt data contract (collect today — P0, Phase 2)

Currently stored: exercise, puzzle, user (or guest), mode (rated/practice),
result (6 values), raw `answer_json`, score, rating before/delta/after (rated
only), XP, `started_at`→`duration_ms`, `hints_used`.
**Gaps to close (all Planned/P0 unless noted):** mistake codes (core+specific);
difficulty/target-rating snapshot at attempt time; retries count; abandonment +
timeout flags (partial: terminal results exist, no structured flags); assignment
context (`assignment_id` — attempts carry none today); assessment context
(assessment/session id); client/response payload version; UI/step trace for
path/step exercises (Open, P1); abandonment position (Open, P2).

## AI

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-AI-001 | Mistake explanations, weakness analysis, personal coaching, training plans, game analysis, tutor, generation assist | P2 | Open (future only; keep addable) | 8 | Phase 3–4, DEC-O08 |

## External integrations

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-EXT-001 | Store external identities + ratings as unverified initial signals | P0 | Implemented (`is_verified=False`, no import) | — | DEC-005 |
| REQ-EXT-002 | Lichess/Chess.com game import → positions → patterns → skill evidence → recommendation | P2 | Open | 7 | Phase 3, DEC-O07 |

## Monetization

| ID | Description | Pri | Status | Phase | Dependency |
|---|---|---|---|---|---|
| REQ-MON-001 | Pricing model selection (Free+Premium / individual / parent / coach / academy per-student / fixed / hybrid) | P2 | Open (none chosen) | 9 | DEC-O05 |
| REQ-MON-002 | Subscriptions, plans, limits, billing | P2 | Open | 9 | REQ-MON-001 |
