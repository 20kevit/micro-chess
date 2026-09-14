# MicroChess — Decision Log

> Every binding product decision + open/proposed items from the documentation phase.
> Format: `DEC-XXX / Title / Decision / Reason / Status / Date / Impact`.
> Status: **Accepted** = binding · **Proposed** = needs approval ·
> **Open** = undecided, must never be assumed decided.
> Code evidence date: 2026-09-14 (`SCHEMA_VERSION=11`).

---

## Accepted

### DEC-001 — Product identity
- Decision: MicroChess is a Chess Skill Assessment + Training Platform (self-training
  + academy complement, never a coach replacement; advantage = specific exercises,
  measurement, future personalization — not puzzle counts).
- Reason: Mission product vision; consistent with exercise-registry architecture.
- Status: Accepted | Date: 2026-09-14 | Impact: All phases; gates new-exercise review.

### DEC-002 — Exercise → Skill taxonomy direction
- Decision: Skill taxonomy is extracted from MicroChess exercises. Generic
  buckets (Tactics/Strategy/Opening/Endgame) are rejected as the taxonomy base.
- Reason: Only exercise-measured abilities are assessable; generic buckets hide gaps.
- Status: Accepted | Date: 2026-09-14 | Impact: Phase 0 taxonomy; Mode B assignment.

### DEC-003 — Opening scope
- Decision: Opening exists only as specific problem-oriented exercises
  (Reverse Opening, Opening Traps). No general opening curriculum/theory.
- Reason: Matches implemented seeded-only modules; avoids duplicating theory sites.
- Status: Accepted | Date: 2026-09-14 | Impact: Content; anything more is Future/Undecided.

### DEC-004 — Backend authoritative
- Decision: Frontend never decides correctness; validation/scoring/rating live in
  backend (`chess_engine` for standard rules, per-exercise validators for custom rules).
- Reason: Already enforced in code + `AGENTS.md`; anti-cheat and consistency.
- Status: Accepted | Date: 2026-09-14 | Impact: Every exercise and API change.

### DEC-005 — External ratings are signals, not the rating
- Decision: FIDE/Lichess/Chess.com = initial level signals only; MicroChess
  behavioral evidence outweighs them once accumulated.
- Reason: External pools are not comparable to MicroChess skills; prevents mis-leveling.
- Status: Accepted | Date: 2026-09-14 | Impact: User level design (Phase 3), imports (Phase 7).

### DEC-006 — User Level vs Puzzle Level separated; suitability rule
- Decision: User level and item level are distinct; future suitability =
  level distance + required skill + history + recent performance + goal.
  External rating is never an absolute gate (evidence of weakness re-opens items).
- Reason: Prevents both boredom and false mastery gating.
- Status: Accepted | Date: 2026-09-14 | Impact: Phases 3–4, Mode B assignment.

### DEC-007 — Mistake taxonomy shape
- Decision: `exercise-independent core + exercise-specific types`; reserved in the
  future data model, not implemented now.
- Reason: Enables weakness analysis and AI explanations later without re-collecting data.
- Status: Accepted | Date: 2026-09-14 | Impact: Attempt data contract; Phase 3.

### DEC-008 — Evidence-gated mastery
- Decision: Mastery requires sufficient evidence — never one attempt or one score.
- Reason: Prevents false mastery claims, especially for children.
- Status: Accepted | Date: 2026-09-14 | Impact: Phase 3 mastery rules, parent/coach trust.

### DEC-009 — Recommendation objective
- Decision: Recommend the most *suitable* exercise (inputs: level, evidence, item
  level, history, mistakes, recency, retention, goals, assignments, time, external
  signals) — not hardest/easiest. Speed = assessment/fun/benchmark, not the backbone.
- Reason: Keeps training in the zone of proximal development; preserves Speed's role.
- Status: Accepted | Date: 2026-09-14 | Impact: Phase 4; personalized packs over daily challenge.

### DEC-010 — Coach modes A/B/C + assessment use case
- Decision: Mode A specific assignment (incl. 10-question group test + compare
  dashboard); Mode B skill/goal assignment (future, needs Phases 3–4); Mode C academy
  custom content separate from public exercises (future).
- Reason: Core academy value proposition; Mode A partially built, rest sequenced.
- Status: Accepted | Date: 2026-09-14 | Impact: Phase 5–6 assignment model.

### DEC-011 — Admin authoring workflow + safety + lifecycle honesty
- Decision: Target flow = search → generate → Draft → suggested answer → edit →
  validate → preview → approve/publish; generators fail gracefully
  (`No valid puzzle available`, never crash); rejected/deleted puzzles are never
  re-recommended nor blindly regenerated (blacklist fingerprint as design
  consideration); puzzle `answer_json` immutable once published; history preserved
  via archive, never hard delete.
- Reason: Content quality + child safety + auditability; partially implemented today.
- Status: Accepted | Date: 2026-09-14 | Impact: Phase 1 authoring work.

### DEC-012 — Public Home vs Student Dashboard split
- Decision: Public home markets (no real exercises for guests); logged-in home is
  the student dashboard (training, progress, skills, assignments, history).
- Reason: Clear funnel + protects assessment integrity.
- Status: Accepted | Date: 2026-09-14 | Impact: Phase 2 UX; conflicts with current
  guest play — needs resolution plan, not silent drift.

### DEC-013 — New-exercise gate (6 questions)
- Decision: Every new exercise must answer: specific skill? not a duplicate?
  educational value? measurable? skill-profile evidence? recommendation-usable?
- Reason: Protects the "specific exercises" advantage (DEC-001).
- Status: Accepted | Date: 2026-09-14 | Impact: Content review; roadmap admissions.

### DEC-014 — Deferred tracks
- Decision: Mini-games (future, non-MVP), multiplayer (future/optional), offline/PWA
  (valuable, low priority), AI + external game analysis (future phases, architecture
  must stay addable), current Elo-style rating is **interim** (final formula undecided —
  Glicko-2/Elo not locked).
- Reason: Focuses MVP; raw answers + audit trail preserve future options.
- Status: Accepted | Date: 2026-09-14 | Impact: Phases 7–9 sequencing.

### DEC-015 — Document future, don't build it
- Decision: `Documentation → Approved Plan → Implementation → Tests → Review`.
  Future concepts get concept + requirement + data-to-preserve only — no future
  DB tables or APIs ahead of phase.
- Reason: Prevents over-design and premature coupling.
- Status: Accepted | Date: 2026-09-14 | Impact: All phases.

---

## Proposed (needs approval before Phase 1)

### DEC-P01 — Initial skill clusters from 19 exercises
- Decision (proposed): 8 clusters — board literacy; legal-move computation; capture
  evaluation; check dynamics; path & visualization; material weighing; special-rule
  knowledge; opening-pattern memory (blueprint §3.1).
- Reason: Directly extracted from validators/scorers. Status: Proposed.

### DEC-P02 — Full 8-state puzzle lifecycle
- Decision (proposed): `Generated→Draft→Validated→Published→Active→Flagged→
  Rejected→Archived` with specified transitions, vs implemented 6-state chain.
- Reason: Covers flag/reject/blacklist needs. Status: Proposed.

### DEC-P03 — Multi-puzzle ordered coach pack shape
- Decision (proposed): Assignment = puzzle list + order + timing + mode + deadline +
  instructions + target students/groups (vs today's single `exercise_slug` + note).
- Reason: Required for the 10-question test use case. Status: Proposed.

### DEC-P04 — Learning loop as product principle
- Decision (proposed): `Learn→Practice→Assessment→(Review)→Mastery` per skill/exercise.
- Reason: Gives Learn/Review/Mastery a planned home. Status: Proposed.

---

## Open (undecided — do not assume)

- DEC-O01: Final skill-rating formula (Glicko-2? Elo? custom? per-skill vs per-exercise?).
- DEC-O02: Final skill cluster names + granularity + cross-exercise weights.
- DEC-O03: Guest policy resolution (teaser scope vs hard login gate).
- DEC-O04: Suitability formula weights + personalization inputs priority.
- DEC-O05: Monetization model (Free+Premium / individual / parent / coach /
  academy per-student / fixed / hybrid — none chosen).
- DEC-O06: Academy custom-content isolation + permissions model.
- DEC-O07: External game import providers order + verification rules.
- DEC-O08: AI scope order (explanations first? game analysis first?).
