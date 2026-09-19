# MicroChess — Product Blueprint

> Source of truth for product vision, concepts, and architecture.
> Status: documentation phase. Concepts marked **Accepted** are product decisions;
> **Proposed** needs approval; **Open** is undecided. Nothing in this file is an
> implementation order — see `docs/ROADMAP.md`. Nothing here authorizes code
> changes — see `docs/DECISIONS.md`.
>
> Code reality (verified 2026-09-14, `SCHEMA_VERSION=11`, 19 registered
> exercises, 51 backend test files): `docs/EXERCISES.md` (exercise truth),
> `docs/platform/IMPLEMENTATION_STATE.md` (platform truth),
> `docs/platform/DATA_MODEL.md` (target data model, `Documented != Implemented`).
> Where this blueprint conflicts with code, **code wins** and the conflict is
> listed in §22.

---

## 1. Product vision

**MicroChess is a Chess Skill Assessment + Training Platform.** (Accepted)

- Usable from the very first day of learning chess up to advanced/professional level.
- Primary audience: children and teenagers — but not limited to them (adult
  learners, parents, coaches, academies are first-class users).
- Usable independently by a player (self-training), and as a complement to
  academy classes and coaching systems.
- It does **not** replace the coach. It gives coaches and students structured
  practice, skill measurement, weakness discovery, and suitable next exercises.
- Focus: specialized exercises, skill measurement, weakness detection, and
  (future) personalization — **not** "the largest puzzle database".
- Competitive advantage must come from MicroChess-specific structured exercises,
  skill evidence, and recommendation — never from raw puzzle counts.

### 1.1 Who it serves

| Audience | Need MicroChess answers |
|---|---|
| Student (child/teen/adult) | What am I weak at? What should I practice next? Am I improving? |
| Parent | Is my child progressing? What does the coach say? |
| Coach | How is each student doing? How do I test a group with the same 10 questions? |
| Academy | Own content/curriculum? Per-student view across coaches? |
| Admin/content team | How do I author, validate, and publish safe puzzles? |

### 1.2 Product principles (Accepted)

1. **Exercise → Skill.** Skills are extracted from MicroChess exercises (§3).
2. **Backend is authoritative.** Frontend never decides correctness (enforced,
   `AGENTS.md` §2).
3. **Evidence over claims.** Mastery, level, and recommendation require
   sufficient behavioral evidence — never one attempt or one score.
4. **Suitability, not difficulty.** Recommend the most *suitable* exercise for
   the user's current state, not the hardest or easiest (§8, §11).
5. **Document future architecture, don't implement it.** (§21 in mission terms —
   concepts + requirements + data to preserve, no future DB/API design.)
6. **Documentation → Approved Plan → Implementation → Tests → Review.**
   No implementation without an approved plan; no future feature ahead of its phase.

---

## 2. Repository audit snapshot (evidence, 2026-09-14)

Verdict scale: **Implemented** / **Partial** (exists but incomplete) /
**Documented-only** / **Planned** / **Missing**.

| Area | Verdict | Evidence |
|---|---|---|
| Backend structure (42 modules under `backend/app/modules/`) | Implemented | `exercises/registry.py` plug-in model; `progress/service.submit_attempt()` single-commit flow; `rating_engine` Elo-style; `gamification_engine`; `puzzles` lifecycle; `auth/users/player/admin/relationships/adaptive/support/notifications` |
| Frontend structure (React 18 + Vite 6 + TS, RTL Persian) | Implemented | 19 exercise routes + admin/support/relationships pages; `main.tsx` router (real), `App.tsx` placeholder; SVG pieces; `i18n/fa.ts` ~572 keys; `DashboardPage.tsx` exists but **not mounted** |
| DB models (`SCHEMA_VERSION=11`, portable types) | Implemented | users/roles, sessions+guests, player profiles + external identities, exercises, puzzles+history/validations/reviews, attempts, per-exercise ratings + rating events, gamification, generator_runs, relationships+assignments, adaptive_recommendations, support, notifications, audit_logs, 14 speed-session tables |
| APIs (per-exercise practice + 60s speed prepare/clock) | Implemented / Partial | 14 exercises have `POST /<slug>/next` + speed sessions; 5 seeded-only (`pin`, `is-checkmate`, `opening-traps`, `reverse-opening`, `castling-rights`) use generic `GET /puzzles` + `POST /attempts`, no speed clock |
| Exercise registry | Implemented | 19 slugs registered via per-module `__init__.py`; `validate_answer` / `score_for_answer`; unknown slug → wrong (no crash) |
| Validators | Implemented | All 19 have validators; custom scorers on 13, default 1.0/0.5/0.0 on 6 |
| Generators | Partial | 14 full exercises have generators; 5 seeded-only have **no** generator (`pin`, `is-checkmate`, `opening-traps`, `reverse-opening`, `castling-rights`) |
| Puzzle repository (seeded content) | Implemented / Partial | 15 seeds for most modules (8 for blindfold-square-vision, ~30 pools for trapped-pieces); 4 modules **content-blocked** (checkmate, opening-traps, reverse-opening, castling-rights — no expansion without admin position-entry workflow) |
| Attempt/scoring logic | Implemented | `submit_attempt()` validates → scores (never trusts client) → rates → XP → feedback atomically; terminal results (timeout/skipped/abandoned) bypass validator |
| Rating-related code | Implemented (interim) | Elo-style per-exercise rating, K=32 provisional/16 established, clamp [100,3000]; practice **never** sets `rating_delta` (NULL); Glicko-2 **deferred** (not decided) |
| Authentication/users | Implemented | register/login/JWT (`sid`), guest sessions + migrate, active-role switching (player/coach/parent/admin), suspend/reactivate |
| Coach/parent (relationships + assignments) | Partial | Relationships `pending→active→revoked`; coach assignment = **single exercise_slug + note + optional due_at** (no multi-puzzle ordered pack, no per-puzzle timing, no instructions field, no target-group field); student/parent read views present |
| Admin | Implemented | Dashboard, users/roles, exercise enable/disable, puzzle CRUD + lifecycle transitions + history, generator runs, analytics, support, audit log; `answer_json` immutable once published; archive (no hard delete) |
| Tests | Implemented | 51 backend `test_*.py`; frontend `typecheck` + `build` + vitest gates |
| Docs | Implemented | `EXERCISES.md`, `platform/` (scope, architecture, data model, phases 01–11, decisions), `ARCHITECTURE.md`, `API.md`, setup/testing/config/deployment |
| README | Implemented | Accurate: claims 19 registered / 14 full + 5 seeded — matches code |
| Migrations | Implemented | `migration.py` idempotent ensure_schema, v2–v11, downgrade protection; Alembic deferred to Postgres move |
| Public home vs student dashboard | Partial | Public `/` + exercises playable **without login** (guest/anonymous allowed — conflicts with §16 decision below, see §22); logged-in account/progress/profile exist; `DashboardPage` unmounted; no personalized training pack |

---

## 3. Skill taxonomy principle (Accepted — binding)

**Do NOT build the skill taxonomy from generic chess categories**
(Tactics / Strategy / Opening / Endgame). That categorization is wrong for MicroChess.

**Binding rule: Exercise → Skill.** First observe what MicroChess exercises
actually measure/train, then extract skills from them. Never
`Generic Chess Categories → Exercise`.

### 3.1 Initial taxonomy extracted from the current 19 exercises (Proposed, not final)

Derived only from what validators/scorers actually measure today:

| Skill cluster (proposed) | Extracted from exercises | Status |
|---|---|---|
| Board literacy (piece identity, square identity/color) | piece-recognition, blindfold-square-vision, chinese-board | Proposed |
| Legal-move computation | legal-destinations, give-check, get-out-of-check | Proposed |
| Capture evaluation (SEE-style: what is attacked/defended, trapped) | captures, undefended-pieces, trapped-pieces, heavier-side | Proposed |
| Check dynamics (give / escape / mate recognition) | give-check, get-out-of-check, is-checkmate, pin | Proposed |
| Path & visualization (shortest path, obstacles, blindfold calc) | pathfinding, pathfinding-obstacles, blindfold-calculation | Proposed |
| Material weighing (comparison, balance) | heavier-side, balance-scale | Proposed |
| Special-rule knowledge (castling rights) | castling-rights | Proposed |
| Opening-pattern memory (trap lines, move reconstruction) | opening-traps, reverse-opening | Proposed |

**Open questions:** final cluster names, skill granularity (one skill per
exercise vs shared skills), whether non-chess skills (memory, balance-scale)
belong in the chess skill profile or a separate cognitive profile, cross-exercise
skill mapping weights, and who approves the final taxonomy (Phase 0 deliverable).

---

## 4. Official exercises (baseline + extended)

Baseline = the 8 exercises named in the product mission. Extended = the other
11 registered exercises (verified in code + `docs/EXERCISES.md`).

Common fields per exercise (see `docs/REQUIREMENTS.md` for the per-exercise
data contract; per-exercise specs live in `docs/exercises/` + `docs/EXERCISES.md`):

`ID · FA name · EN name · goal · measured skills · suitable level ·
modes (Practice/Speed/Assessment) · answer type · scoring · generator ·
validator · data source · implementation status · production readiness ·
dependencies · coach-assignable? · recommendation-usable? · attempt data to
store · extractable mistake types`

### 4.1 Baseline exercises (mission §4)

| # | ID (slug) | FA / EN | Goal | Status (code-verified) |
|---|---|---|---|---|
| 1 | `piece-recognition` | تشخیص مهره / Piece Recognition | Find all squares containing the target piece | Implemented: practice `next` + 60s speed, generator + 15 seeds, custom square scorer |
| 2 | `legal-destinations` | حرکت‌های قانونی / Legal Destinations | All legal destinations of a piece from a square | Implemented: practice + speed, generator + 15 seeds, custom scorer |
| 3 | `captures` | گرفتن مهره / Captures | Hunter-piece captures (SEE-flavored) | Implemented: practice + speed, generator + 15 seeds, custom scorer |
| 4 | `undefended-pieces` | مهره‌های بی‌دفاع / Undefended Pieces | List undefended squares | Implemented: practice + speed, generator + 15 seeds (Lichess `puzzles.db` + fallback), custom scorer |
| 5 | `give-check` | کیش دادن / Giving Check | Find checking moves | Implemented: practice + speed, generator, **no** `seed.py` (shared DB + fallback FENs), custom move scorer |
| 6 | `get-out-of-check` | رفع کیش / Get Out of Check | Escape check legally | Implemented: practice + speed, generator + 15 hand-designed, custom scorer (+5/−2/−3) |
| 7 | `pathfinding` | مسیریابی / Pathfinding | Shortest path (+ `/step` oracle) | Implemented: practice + speed, generator + 15 seeds, custom path scorer |
| 8 | `pathfinding-obstacles` | مسیریابی با مانع / Obstacle Pathfinding | Shortest path with obstacles/enemy pieces | Implemented: practice + speed, generator + 15 seeds (BFS `transitions.py`), custom scorer |

All 8: answer = squares/moves/paths submitted to `POST /api/v1/attempts`;
scoring partial-credit; modes today = Practice + Speed; Assessment mode =
**Proposed** (coach 10-question pack, §13); coach-assignable today only as
single-exercise assignment (multi-puzzle pack = future); recommendation-usable
once skill mapping + user level exist (Phase 3–4).

### 4.2 Extended registered exercises (code-verified)

| # | ID | FA (UI) / EN | Modes | Generator | Production note |
|---|---|---|---|---|---|
| 9 | `balance-scale` | ترازو / Balance Scale | practice + speed | Yes (DP solver) + 15 seeds | Implemented, non-chess weighing skill |
| 10 | `heavier-side` | سمت سنگین‌تر / Heavier Side | practice + speed | Yes + 15 seeds | Implemented, material-only |
| 11 | `pin` | آچمز / Pin | practice/attempt only, **no speed** | **No** (15 ordered-triplet seeds) | Implemented, seeded-only |
| 12 | `chinese-board` | صفحه‌ی حفظی / Memorization Board (slug `chinese-board` kept for routes/API/DB) | practice + speed | Yes + 15 seeds | Implemented |
| 13 | `is-checkmate` | مات؟ / Is it Checkmate? | attempt only, no speed | **No** | Implemented but **content-blocked** |
| 14 | `blindfold-square-vision` | دید نابینا / Blindfold Square Vision | practice + speed (button-only) | Yes + 8 seeds | Implemented |
| 15 | `blindfold-calculation` | محاسبه نابینا / Blindfold Calculation | practice + speed, SAN input | Yes + 15 Lichess rows | Implemented (`fen=NULL`, server-side answer) |
| 16 | `opening-traps` | گشایش ذهنی / Mental Opening (Opening Traps) | attempt only, no speed | **No** | Implemented but **content-blocked** |
| 17 | `reverse-opening` | گشایش معکوس / Reverse Opening | attempt + `/step`, no `/next`, no speed | **No** | Implemented but **content-blocked** |
| 18 | `trapped-pieces` | مهره‌ی محبوس / Trapped Pieces (MicroChess SEE def.) | practice + speed (`exactly_one`) | Yes (`detector.py`) + ~30 pools | Implemented |
| 21 | `castling-rights` | حق قلعه / Castling Rights | attempt only, no speed | **No** | Implemented but **content-blocked** |

Removed with no placeholders (not planned): `hanging-pieces`,
`equal-attackers-defenders`, `memory-board` (superseded by `chinese-board`),
`opening-move-reconstruction` (renamed to `reverse-opening`), `avoid-stalemate`,
`rule-of-the-square`. Planned-but-unregistered: **none** — every roadmap item is
registered; anything beyond the 19 is **Open/Future**.

---

## 5. Opening — correct definition (Accepted)

> Opening in MicroChess is **not** a general curriculum for memorizing and
> teaching opening theory. It enters the product **only** as specific,
> problem-oriented MicroChess exercises (e.g. Reverse Opening / Opening Move
> Reconstruction, Opening Traps).

Anything beyond that (full opening repertoire, theory lessons) is
**Future / Undecided**. Code status: `opening-traps` + `reverse-opening` exist
as seeded-only validators — consistent with this definition.

---

## 6. Skill profile (conceptual — no implementation)

In the future every user has a picture of their abilities (e.g. ability A/B/C).
The rating formula is **not decided**: do **not** lock Glicko-2, Elo, or any
final skill-rating formula in this phase. (Current Elo-style per-exercise rating
is explicitly an **interim** implementation.)

The future system must be able to store/compute (data to preserve — Accepted as
requirements, not as built features):

- performance per skill · per exercise · per difficulty
- response time · repeated mistakes · mistake type
- retention · improvement trend · attempt history · assessment results
- external rating signals (FIDE / Lichess / Chess.com, unverified `is_verified=False` today)

---

## 7. External rating (Accepted)

FIDE / Lichess / Chess.com ratings are **not** MicroChess's main rating. They are
**External Signals / Initial Level Signals**: usable at signup for a rough
initial level estimate. After real MicroChess data accumulates,
**MicroChess behavioral/performance evidence must outweigh them**.

- Today: `player_external_identities(provider, external_username, rating,
  is_verified=False)` stores the signal. No import, no verification pipeline.
- Future architecture must allow Lichess/Chess.com game import and the pipeline
  `Game → Position → Pattern → Skill Evidence → Recommendation` (Future, §19).

---

## 8. User Level vs Puzzle/Exercise Level (Accepted)

Two separate concepts:

- **User Level** — estimated ability of the user.
- **Puzzle/Exercise Level** — suitability level of a practice item
  (today: `puzzles.difficulty`, `target_rating`, `initial_rating=1200`).

Future decision rule (Proposed): *suitability = f(distance between user level
and item level + required skill + user history + recent performance + current
goal).* External rating is **never** an absolute gate: e.g. a 1400+ user does
not get Piece Recognition by default — but if real evidence shows weakness in
that skill, the system must be able to recommend it again.

---

## 9. Mistake taxonomy (conceptual — no implementation)

MicroChess must eventually know more than `correct / wrong` — it must know
*what kind* of mistake was made. Per-exercise examples (Proposed):

wrong piece · wrong square · illegal move · wrong target · missed capture ·
missed check · wrong escape · extra path step · illegal attempt · timeout ·
repeated error · plus exercise-specific types.

Design rule (Accepted): taxonomy = **exercise-independent core** +
**exercise-specific mistake types**. The future data model must reserve room
for it. Code gap (verified): attempts store raw `answer_json` + result + score
but **no mistake codes** — validators return messages, not classified mistake
types. Preserve raw answers (done) so future classifiers can backfill.

---

## 10. Learning loop (Proposed model, not implementation)

Proposed product principle: `Learn → Practice → Assessment → (Review) → Mastery`.

- Each skill/exercise can eventually have Learn / Practice / Assessment / Review
  / Mastery stages.
- Mastery must require **sufficient evidence**, never a single attempt or score.
- Code today has Practice (+ Speed) and single-exercise coach assignment; Learn
  content, Review scheduling, and Mastery rules do **not** exist.

---

## 11. Recommendation engine (Future concept)

Future inputs (Accepted as the input list): user level, skill evidence,
exercise level, exercise history, mistakes, recent performance, retention,
goals, coach assignments, available time, external rating signals.
Objective: not the hardest, not the easiest — the **most suitable** exercise
for the user's current state.

Code reality: `adaptive` module is a **selection-recording layer only**
(`next` + `shown/accepted/completed/skipped`) — no suitability formula, no
user model, no skill evidence. All formula work is Phase 4.

---

## 12. Personalized daily training (Future concept)

A single public Daily Challenge for everyone is **not** the goal. Future:
`User Model → Personalized Training Pack` built from level, weaknesses, goal,
available time, recent exercises, mistake history, and review needs.

Speed exercises are for assessment / fun / benchmarking — the training system
must **not** be designed around Speed. (Accepted)

---

## 13. Coach system (Accepted decisions)

MicroChess is designed from the start as a coach/academy-usable product.

- **Mode A — Specific Exercise/Puzzle Assignment (partially implemented).**
  Coach assigns exactly what the student sees (e.g. a 10-question test every
  student takes). Target shape: multiple puzzles, order, timing, mode,
  deadline, instructions, target students. **Gap:** today an assignment is one
  `exercise_slug + note + optional due_at` — no puzzle list, order, mode,
  instructions, or group targeting.
- **Mode B — Skill/Goal Assignment (Future).** Coach says "practice this skill";
  MicroChess picks suitable puzzles for the student's level. Requires skill
  mapping + user level + recommendation (Phases 3–4 first).
- **Mode C — Academy Custom Curriculum/Content (Future).** Academy/coach creates
  private exercises, puzzles, and curricula, assigned to their students,
  **separate** from public MicroChess exercises.

### Coach assessment use case (Accepted)

Coach creates e.g. a 10-question test for a class/group → each student sees and
completes it → MicroChess records results → coach views and compares results
→ (future) sees weaknesses. This is a primary driver of future assignment design.

---

## 14. Admin puzzle authoring (Future workflow — Accepted as the target)

`Admin → pick Exercise → Create New Puzzle → system searches existing suitable
puzzles → if found, show for edit; if not, notify → system attempts generation
→ save as Unapproved/Draft → show suggested answer → admin edits position/puzzle
→ validate → preview → approve → publish.`

Admin must be able to: view position, view suggested answer, view validation
result, edit, preview, approve, reject, archive/delete. **Gap:** no
position-entry workflow (the documented blocker for 4 content-blocked modules),
no draft-preview UI flow, no suggested-answer review screen, no explicit reject
state (only publish/retire/archive exist).

---

## 15. Generated puzzle safety (Accepted)

If a generator cannot produce a valid puzzle, the application must **never
crash** — graceful failure (`No valid puzzle available`) and the app continues
unharmed. Verified today: unknown slug → wrong result; unpublished/archived →
rejected; duplicate detection via `content_hash`. Keep this invariant in every
future generator/authoring flow.

---

## 16. Deleted/rejected puzzle policy (Accepted as design consideration)

A puzzle an admin explicitly deletes/rejects must **never** be recommended again,
and the system must not regenerate the same puzzle merely because content is
missing. Consider a `rejected/blacklisted fingerprint` mechanism. **Gap:**
no rejected/blacklisted state or fingerprint table exists — only
`is_archived`/retired. Do not implement in this phase; record as requirement
(REQ-PUZ-…).

---

## 17. Puzzle lifecycle (Proposed full model vs implemented subset)

Proposed: `Generated → Draft/Unapproved → Validated → Published → Active →
Flagged → Rejected → Archived`, each state with meaning + allowed transitions
(to be specified in Phase 1 design).

Implemented today (verified in `puzzles/models.py`): `draft → validated →
reviewed → approved → published → retired`, mirrored on
`is_published/is_archived`, with `puzzle_status_history`, `puzzle_validations`,
`puzzle_reviews`, duplicate guard on `content_hash` against
validated/reviewed/approved/published. **Missing vs proposed:** no Generated,
Active, Flagged, or Rejected states; no rejected/blacklist fingerprint.

---

## 18. Public website vs student product (Accepted)

- **Public Home (no login):** what MicroChess is, what problem it solves, who
  it is for (students, parents, coaches, academies), features, sample exercises,
   benefits, pricing, FAQ, about, login/register. **Guest must not be able to do
   real exercises.** (Enforced 2026-09-19 per DEC-016: anonymous/guest submits
   are 401 server-side, exercise routes require login; historical guest rows
   preserved and migratable.)
- **Logged-in Home = Student Dashboard:** training, progress, skill profile,
  recommendations, assignments, history, personalized training (future).

---

## 19. Roles (conceptual model — partially implemented)

- **Student · Coach · Academy · Admin · Parent (future).**
- Future relationships: `Academy → Coach`, `Coach → Students`,
  `Coach → Assignments`, `Academy → Custom Content`, `Student → Attempts`,
  `Student → Skill Evidence`.
- Implemented: PLAYER/COACH/PARENT/ADMIN roles + active-role switching;
  coach/parent↔student relationships; single-exercise assignments; admin
  powers. **Missing:** Academy role/accounts, custom content/curriculum,
  skill evidence tables, group assignment targeting.

---

## 20. Unique exercise strategy (Accepted)

MicroChess does **not** compete on "we have 100,000 puzzles". Advantage comes
from MicroChess-specific exercises. Gate for any new exercise (all six required):

1. Does it measure a specific skill? 2. Is it a Lichess/Chess.com duplicate?
   3. Does it have clear educational value? 4. Is it measurable? 5. Can it
   produce Skill Profile evidence? 6. Can it feed recommendation?

---

## 21. Deferred tracks (Accepted)

- **Mini-games:** future (engagement, speed, visualization, memory, fun,
  assessment). Not core MVP.
- **Multiplayer:** not needed now. Future/optional.
- **Offline/PWA:** valuable but lower priority. No implementation.
- **AI roadmap (future only):** explain mistakes, personalized coaching,
  weakness analysis, game analysis, exercise generation, training plans,
  Lichess/Chess.com game analysis, tutor-style interaction. Current
  architecture must not make AI hard to add later (raw answers + audit trail
  preserved).
- **External game analysis (future):** `Lichess/Chess.com Game → Game Import →
  Position Extraction → Chess Rules/Engine → Pattern Detection → Skill Mapping →
  Skill Evidence → Recommendation.` Not implemented.
- **Monetization (Open — no decision):** options on the table: Free+Premium,
  individual subscription, parent subscription, coach subscription, academy
  per-student, academy fixed subscription, hybrid. **None accepted.**

---

## 22. Product architecture (conceptual — Accepted as the map)

```text
MicroChess
├── Exercises (Definition · Generator · Validator · Puzzle · Scoring)
├── Attempts
├── Mistake Analysis (core + exercise-specific; future)
├── Skill Evidence (future; needs mistake + level + history data)
├── User Model (External Signals [partial] · User Level [future] ·
│   Skill Profile [future] · History [partial: attempts/ratings/XP])
├── Recommendation (future; current `adaptive` = selection logging only)
├── Personalized Training (future)
├── Coach (Students [partial] · Assignments [single-exercise] · Assessments [future])
├── Academy (Custom Content · Curriculum — future)
├── Admin (Puzzle Authoring [partial] · Generator [partial] · Validation [partial] · Publishing [done])
└── Future (External Game Analysis · AI · Mini Games · Advanced Analytics)
```

---

## 23. Known doc↔code conflicts (must be resolved by approved plan, not ad hoc)

1. **Guest play vs "guest must not do real exercises" (§18).** Resolved
   2026-09-19 (DEC-016, hard login gate): anonymous/guest submits are 401
   server-side, exercise routes require login; historical guest rows are
   preserved and migratable.
2. **`DashboardPage` unmounted** while blueprint assumes a student dashboard home.
3. **Coach assignment shape** (single `exercise_slug`) vs multi-puzzle ordered
   pack with mode/instructions/groups (§13).
4. **Lifecycle states** (implemented 6-state chain) vs proposed 8-state model
   with Flagged/Rejected/Active (§17).
5. **No mistake codes, no assignment/assessment context on attempts** vs future
   skill/recommendation needs (§9, and requirements doc).
6. **Elo-style rating live** while blueprint keeps the final formula undecided
   (§6) — must stay labeled *interim* until Phase 3 decides.
