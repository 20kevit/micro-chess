# MicroChess Platform Documentation

## 1. Purpose

This directory contains the canonical documentation for the MicroChess platform expansion.

It defines:

* product scope
* architecture
* data model
* API contracts
* security
* UX rules
* domain behavior
* implementation phases
* important architectural decisions

The documents are intentionally separated by responsibility. A document should define only what belongs to its scope and should link to other canonical documents instead of duplicating their rules.

---

# 2. Documentation Authority

When documents conflict, use this order:

1. Accepted ADRs in `decisions/`
2. `MASTER_PLAN.md`
3. The most specific applicable domain specification
4. Cross-cutting specifications:

   * `ARCHITECTURE.md`
   * `DATA_MODEL.md`
   * `API_CONTRACTS.md`
   * `SECURITY.md`
   * `UX_AND_DESIGN.md`
5. Phase specifications
6. `IMPLEMENTATION_STATE.md`
7. Existing implementation
8. Historical documentation
9. Agent assumptions

An accepted ADR is both a historical decision record and a current architectural constraint until superseded.

The most specific applicable specification wins over a more general specification when there is no higher-level conflict.

---

# 3. Current Implementation vs Target State

The documentation describes the intended target state.

The repository describes the current implementation.

Existing code is therefore **evidence of current state**, not automatically the desired state.

However, documented target state does not justify unnecessary rewrites.

Before changing existing code, the implementation agent must:

1. inspect the relevant repository code
2. understand existing behavior and architecture
3. identify the gap between current and target state
4. choose the smallest safe change
5. preserve unrelated working behavior
6. add or update meaningful tests
7. verify the result

Existing exercise implementations are especially important and must not be rewritten merely to fit a new platform abstraction.

---

# 4. Documentation Structure

## Core

```text
MASTER_PLAN.md
IMPLEMENTATION_STATE.md
PRODUCT_SCOPE.md
ARCHITECTURE.md
DATA_MODEL.md
API_CONTRACTS.md
SECURITY.md
UX_AND_DESIGN.md
```

### `MASTER_PLAN.md`

Defines the complete platform target, major capabilities, dependencies, implementation phases, global invariants, and overall Definition of Done.

### `IMPLEMENTATION_STATE.md`

Records repository reality:

* implemented areas
* verification state
* known gaps
* blockers
* important technical debt

It does not redefine requirements or act as a task queue.

### `PRODUCT_SCOPE.md`

Defines product goals, users, capabilities, current/future scope, and explicit non-goals.

### `ARCHITECTURE.md`

Defines system structure, module boundaries, dependencies, application/domain responsibilities, persistence, integrations, and architectural invariants.

### `DATA_MODEL.md`

Defines entities, relationships, ownership, lifecycle, constraints, indexes, historical records, and deletion/anonymization behavior.

### `API_CONTRACTS.md`

Defines API conventions, contracts, validation, errors, authorization boundaries, pagination, filtering, idempotency, and versioning.

### `SECURITY.md`

Defines authentication, authorization, privacy, abuse prevention, sensitive operations, audit, and security invariants.

### `UX_AND_DESIGN.md`

Defines global UX rules including Persian RTL, responsive behavior, accessibility, navigation, feedback, and exercise-screen constraints.

---

# 5. Domain Documentation

```text
accounts/
training/
admin/
relationships/
```

Domain documents define detailed behavior for their respective subsystem.

### Accounts

```text
accounts/
├── AUTHENTICATION.md
├── USER_PROFILES.md
├── ROLES_AND_PERMISSIONS.md
└── SESSIONS_AND_GUESTS.md
```

Covers authentication, profiles, external chess identities, roles/capabilities, sessions, guests, and guest migration.

### Training

```text
training/
├── RATINGS.md
├── ATTEMPTS_AND_HISTORY.md
├── GAMIFICATION.md
└── ANALYTICS.md
```

Covers exercise-specific ratings, authoritative training history, gamification, and analytics.

### Administration

```text
admin/
├── ADMIN_OVERVIEW.md
├── USER_MANAGEMENT.md
├── EXERCISE_MANAGEMENT.md
├── PUZZLE_MANAGEMENT.md
├── GENERATORS.md
└── ADMIN_ANALYTICS.md
```

Covers administrative operations, users, roles, exercises, puzzles, generators, and administrative analytics.

### Relationships

```text
relationships/
├── COACH_STUDENT.md
└── PARENT_STUDENT.md
```

Covers relationship lifecycle, scoped access, assignments, groups/classes, and future parent/coach functionality.

---

# 6. Phase Documentation

```text
phases/
```

Phase documents define **implementation order and execution scope**.

They are not independent product specifications.

A phase should reference the relevant domain documents instead of copying their rules.

Each phase should define, where applicable:

1. Objective
2. Prerequisites
3. Included capabilities
4. Required data changes
5. Backend changes
6. Frontend changes
7. API changes
8. Security requirements
9. Migration requirements
10. Tests
11. Documentation updates
12. Acceptance criteria
13. Definition of Done

The implementation agent should follow the dependency order defined by `MASTER_PLAN.md`.

A phase must not redefine a domain rule differently from its canonical domain specification.

---

# 7. Architecture Decisions

```text
decisions/
```

ADRs record decisions that materially affect architecture, security, data ownership, major behavior, or long-term evolution.

Each significant decision should have its own ADR.

Typical structure:

```text
0001-...
0002-...
0003-...
```

An ADR should contain:

* Status
* Context
* Decision
* Alternatives
* Consequences

Accepted decisions must not be silently rewritten.

When a decision changes:

1. create a new ADR
2. mark the previous ADR `SUPERSEDED`
3. reference the new decision
4. update affected specifications

Do not create ADRs for ordinary implementation details.

---

# 8. Documentation Maintenance

Documentation must remain consistent with implementation and with itself.

When a meaningful implementation change affects documented behavior:

1. update the relevant specification
2. update `IMPLEMENTATION_STATE.md`
3. create or update an ADR when the change is architecturally significant

Do not create duplicate sources of truth.

Prefer references to canonical documents over repeating the same requirements.

A document explicitly marked `DRAFT` must not be treated as an accepted implementation requirement.

---

# 9. Rules for Autonomous Implementation Agents

An implementation agent working on the platform must:

1. Read `MASTER_PLAN.md` before making platform-wide decisions.
2. Read the relevant domain specification before changing that domain.
3. Inspect the repository before implementing or restructuring anything.
4. Treat existing code as current-state evidence.
5. Never invent requirements.
6. Never silently weaken documented requirements.
7. Preserve unrelated working functionality.
8. Prefer the smallest safe implementation that satisfies the target.
9. Reuse existing architecture when it is sound.
10. Keep routes/controllers thin and business rules in the appropriate application/domain layer.
11. Keep server-side validation authoritative for security-sensitive, scoring-sensitive, rating-sensitive, and gamification-sensitive operations.
12. Preserve historical data required for analytics and product integrity.
13. Add meaningful tests for business rules, contracts, security boundaries, regressions, and non-trivial algorithms.
14. Avoid tests that merely reproduce implementation details.
15. Verify affected backend and frontend behavior.
16. Verify responsive behavior for affected UI.
17. Keep migrations safe and avoid destructive changes without explicit justification.
18. Do not modify large read-only source datasets such as the puzzle database unless the relevant specification explicitly requires it.
19. Do not treat generated content as production content without the defined validation/review/publishing process.
20. Update implementation state after meaningful milestones.

---

# 10. Conflict Resolution

When a conflict is discovered:

1. Check applicable ADRs.
2. Check `MASTER_PLAN.md`.
3. Check the most specific domain specification.
4. Check whether one document is outdated.
5. Inspect the repository for relevant current-state evidence.
6. Resolve only when the documentation and evidence provide a clear answer.
7. Otherwise report the unresolved conflict instead of guessing.

Do not resolve significant architectural conflicts simply by choosing the easiest implementation.

---

# 11. Preservation of Existing Exercises

The platform expansion must remain compatible with the existing MicroChess exercise system.

Platform work must not unnecessarily change:

* exercise behavior
* puzzle validation
* scoring semantics
* exercise-specific algorithms
* existing responsive exercise UX
* existing exercise routes/API behavior

When a platform capability requires an integration with an existing exercise, prefer an adapter or minimal integration boundary over rewriting the exercise.

Every affected exercise must retain meaningful regression coverage.

---

# 12. Final Objective

The platform should evolve MicroChess into a complete chess-skill training product while preserving its existing exercise foundation.

The target includes:

* secure player accounts
* profiles and external chess identities
* guest training
* exercise-specific ratings
* detailed training history
* analytics
* gamification
* player dashboards
* administration
* exercise and puzzle management
* puzzle generation and quality control
* coach/student infrastructure
* parent/student infrastructure
* future adaptive training
* strong privacy and security

Future capabilities must be added through the architecture defined by the documentation without prematurely implementing infrastructure that current product requirements do not justify.
