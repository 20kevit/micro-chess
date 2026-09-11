# MicroChess Platform — Master Plan

## 1. Document Status

**Status:** Accepted
**Document Type:** Master Product & Implementation Plan
**Scope:** Target platform, implementation roadmap, and execution contract

This document defines the target MicroChess platform, its implementation order, global constraints, and execution rules.

It is both:

1. a product/architecture roadmap, and
2. an implementation contract for AI coding agents and human developers.

This document describes the **target state**.

It does not describe the repository's current implementation state.

Detailed behavior belongs in the relevant domain and phase specifications.

---

# 2. Purpose

The implementation agent must use this document to:

1. understand the target platform
2. identify the active implementation phase
3. inspect the repository before making changes
4. reconcile the current implementation with the target
5. implement the required capabilities for the active phase
6. verify the implementation
7. update affected documentation and implementation state
8. stop at the phase boundary unless explicitly instructed to continue

The phases form one coherent product roadmap.

They are **not** permission to implement the entire roadmap in one autonomous run.

---

# 3. Target State

The target MicroChess platform consists of:

```text
MicroChess
│
├── Identity
│   ├── Accounts
│   ├── Authentication
│   ├── Sessions
│   ├── Guest identity
│   ├── Roles
│   └── Capabilities
│
├── Player
│   ├── Profile
│   ├── External chess identities
│   ├── Dashboard
│   └── Progress
│
├── Training
│   ├── Exercises
│   ├── Practice
│   ├── Speed
│   ├── Sessions
│   └── Attempts/history
│
├── Ratings
│   ├── Per-exercise ratings
│   └── Rating history
│
├── Gamification
│   ├── XP
│   ├── Levels
│   ├── Streaks
│   ├── Goals
│   ├── Achievements
│   ├── Mastery
│   └── Leaderboards
│
├── Administration
│   ├── Users
│   ├── Roles
│   ├── Exercises
│   ├── Puzzles
│   ├── Generators
│   ├── Analytics
│   ├── Audit
│   └── Support
│
├── Analytics
│   ├── Player
│   ├── Exercise
│   ├── Puzzle
│   └── Platform
│
├── Relationships
│   ├── Coach → Student
│   └── Parent → Student
│
└── Future Adaptive Training
    ├── Recommendations
    ├── Adaptive difficulty
    └── Personalized training
```

This is the target product direction.

It does **not** require all capabilities to be implemented immediately.

A capability becomes implementation work only when its phase is active or an accepted specification explicitly brings it forward.

---

# 4. Current-State Rule

The repository is the source of truth for what currently exists.

Before implementing a phase, the agent MUST inspect the relevant current implementation, including where applicable:

* backend structure
* frontend structure
* models and database schema
* migrations
* API routes
* application/domain services
* exercise architecture
* existing tests
* configuration
* relevant documentation
* current runtime assumptions

The documentation defines the intended target.

The repository defines the current state.

The agent must reconcile the two before making changes.

Existing working functionality must be preserved unless an accepted requirement intentionally changes it.

---

# 5. Documentation Authority

When documents disagree, use this authority order:

```text
Accepted ADR
    ↓
MASTER_PLAN.md
    ↓
Most specific domain specification
    ↓
Cross-cutting architecture/security/API/UX documents
    ↓
Active phase specification
    ↓
IMPLEMENTATION_STATE.md
    ↓
Repository implementation
    ↓
Historical documentation
```

This hierarchy applies to **target requirements**.

For current implementation facts, the repository remains authoritative.

If an actual conflict exists between accepted specifications, the agent must stop and identify the conflict rather than silently choosing one.

---

# 6. Documentation Loading Strategy

The documentation package is intentionally modular.

The agent MUST NOT load the entire documentation tree by default.

For normal implementation work, load only:

```text
1. platform/README.md
2. platform/MASTER_PLAN.md
3. platform/IMPLEMENTATION_STATE.md
4. the active phase specification
5. directly relevant domain specifications
6. relevant cross-cutting specifications only when required
```

Examples:

### Accounts work

Read:

```text
accounts/AUTHENTICATION.md
accounts/USER_PROFILES.md
accounts/ROLES_AND_PERMISSIONS.md
accounts/SESSIONS_AND_GUESTS.md
SECURITY.md
```

Do not load unrelated analytics, generator, or relationship specifications unless required.

### Ratings work

Read:

```text
training/RATINGS.md
training/ATTEMPTS_AND_HISTORY.md
SECURITY.md
API_CONTRACTS.md
```

Do not load the complete administration documentation unless required.

### Analytics work

Read:

```text
training/ANALYTICS.md
training/ATTEMPTS_AND_HISTORY.md
training/RATINGS.md
GAMIFICATION.md
API_CONTRACTS.md
```

and only the directly relevant administration specification when needed.

The agent may load additional documents when:

* a dependency requires them,
* a specification conflict is suspected,
* an architectural decision is involved,
* or repository evidence requires broader inspection.

The goal is **progressive context loading**, not maximum context consumption.

---

# 7. Global Principles

## 7.1 Preserve Existing Exercises

The platform expansion must integrate with the existing exercise system.

Do not create a second exercise architecture.

Reuse existing shared infrastructure where appropriate, including:

* exercise lifecycle
* play shell
* board
* catalog
* API client
* i18n
* design-system components
* existing exercise-specific mechanisms

Exercise-specific rules remain inside their exercise domain.

---

## 7.2 Smallest Safe Change

Prefer the smallest coherent implementation that fully satisfies the active requirement.

Avoid:

* speculative rewrites
* unrelated refactors
* duplicate frameworks
* unnecessary dependencies
* premature abstractions
* replacing working architecture without evidence
* broad cleanup unrelated to the active phase

A large change is acceptable when repository evidence and the target architecture genuinely require it.

---

## 7.3 Complete Means Complete

The goal is not to implement a partial feature merely to advance the roadmap.

When a capability is included in the active phase, implementation must cover all required layers:

```text
Domain behavior
    ↓
Application behavior
    ↓
Persistence
    ↓
API
    ↓
Frontend
    ↓
Authorization/security
    ↓
Tests
    ↓
Runtime verification
    ↓
Documentation
```

Do not mark a capability complete merely because its database model or API endpoint exists.

---

## 7.4 Server Authority

The server is authoritative for:

* identity
* authorization
* correctness
* scores
* ratings
* XP
* achievements
* streaks
* training history
* administrative actions
* other security-sensitive or result-sensitive state

The client must not determine authoritative results.

---

## 7.5 Historical Data

Historical training data must remain useful for:

* player progress
* analytics
* rating history
* difficulty analysis
* future recommendations
* debugging
* auditing where applicable

Do not destroy historical meaning merely because the current UI no longer displays a field.

---

## 7.6 No Premature Infrastructure

Extensibility must come from clean boundaries and appropriate data models.

Do not introduce infrastructure merely for hypothetical future scale.

Do not introduce:

* microservices
* message brokers
* distributed event infrastructure
* data warehouses
* Kubernetes
* ML infrastructure

unless an accepted specification explicitly requires them.

The initial platform remains a modular application using the existing technology direction.

---

## 7.7 No Speculative Future Implementation

Documenting a future capability does not authorize implementing it early.

The following rule is mandatory:

> **Documented does not mean implemented. Architecture-ready does not mean schema-required.**

Do not create future database tables, APIs, services, abstractions, or UI merely because a later phase will eventually need them.

Only create the minimum extension points required by the active phase.

---

# 8. Dependency Graph

The default roadmap is:

```text
Phase 1
Foundation
    │
    ▼
Phase 2
Accounts & Identity
    │
    ▼
Phase 3
Player Platform
    │
    ▼
Phase 4
Exercise Ratings
    │
    ▼
Phase 5
Gamification
    │
    ▼
Phase 6
Administration Foundation
    │
    ▼
Phase 7
Content & Generators
    │
    ▼
Phase 8
Analytics
    │
    ▼
Phase 9
Relationships
    │
    ▼
Phase 10
Adaptive Training Foundation
```

This is the recommended dependency order.

It does not require every internal task to be sequential when its real dependencies are already satisfied.

However, an implementation run should normally work on **one phase at a time**.

---

# 9. Phase Execution Model

## 9.1 One Phase per Run

The default autonomous execution boundary is:

> **One implementation run = one phase.**

The agent must not automatically continue into the next phase after completing the active phase.

After phase completion:

```text
Implement
    ↓
Test
    ↓
Verify
    ↓
Update documentation
    ↓
Update implementation state
    ↓
Commit
    ↓
STOP
```

A later phase requires a new explicit implementation run.

This rule exists to:

* limit context growth
* reduce accidental cross-phase changes
* simplify debugging
* preserve clean Git history
* make failures easier to isolate
* reduce speculative implementation
* make human review practical

A human may explicitly authorize multiple phases in one run when the phases are small and tightly coupled.

---

## 9.2 Phase Gate

A phase cannot be considered complete until:

1. required capabilities are implemented
2. backend behavior works
3. frontend behavior works
4. required persistence changes are safe
5. security/authorization requirements are enforced
6. meaningful tests pass
7. existing functionality remains operational
8. relevant UX is verified
9. documentation is synchronized
10. implementation state contains evidence

Only after these conditions are satisfied may the run stop as a successful phase completion.

The next phase must not begin automatically.

---

# 10. Phase 1 — Foundation

## Objective

Prepare the existing application for accounts, persistent training data, authorization, and future platform features without breaking existing exercises.

## Scope

* repository and architecture audit
* database/migration strategy
* configuration review
* API conventions
* error handling
* authentication/session primitives where required by the foundation
* authorization/capability foundation
* testing foundation
* shared platform boundaries
* documentation synchronization

The phase must establish only the foundations required by later phases.

It must not implement speculative platform features.

## Completion

The application has safe foundations for platform expansion, existing exercises continue to work, and the resulting architecture is documented.

---

# 11. Phase 2 — Accounts & Identity

## Objective

Introduce secure registered accounts and guest identity.

## Scope

* username/password registration
* secure login/logout
* sessions and expiration
* account status
* password hashing
* canonical role foundation
* capability system
* guest sessions
* guest training identity
* guest-to-account migration
* authentication tests
* authorization tests

Registration initially requires only:

* username
* password

Profile information and external chess identities are added in Phase 3.

Guest is not a persisted role.

Guest migration must be:

* atomic
* idempotent
* replay-resistant
* safe against accidental data overwrite
* auditable where required

Detailed requirements belong in:

```text
accounts/
```

---

# 12. Phase 3 — Player Platform

## Objective

Build the complete registered-player experience around the existing exercises.

## Scope

* player profile
* external chess identities
* privacy settings
* player dashboard
* exercise discovery
* exercise progress
* training history views
* basic personal progress summaries
* player navigation
* guest migration presentation

Phase 3 may expose basic personal statistics needed for the player experience.

It does **not** implement the full analytics system defined in Phase 8.

Full analytics, comparisons, advanced time ranges, exercise/puzzle/platform analytics, and analytical aggregation belong to Phase 8.

External FIDE, Lichess, and Chess.com identities remain separate from MicroChess exercise ratings.

The existing exercise experience remains the foundation of the player platform.

Detailed requirements belong in:

```text
PRODUCT_SCOPE.md
accounts/
training/ATTEMPTS_AND_HISTORY.md
UX_AND_DESIGN.md
```

---

# 13. Phase 4 — Exercise Ratings

## Objective

Introduce independent skill ratings for applicable exercises.

## Scope

* one rating per applicable exercise
* initial/provisional rating
* current rating
* rating events
* rating history
* deterministic rating update
* rated/unrated attempt handling
* replay protection
* atomic attempt/rating updates
* player-facing rating display

The initial algorithm must be:

* simple
* deterministic
* testable
* documented

The architecture should allow future rating improvements without destructive redesign.

Advanced rating algorithms and sophisticated calibration systems are future extensions unless explicitly required.

Detailed requirements belong in:

```text
training/RATINGS.md
```

---

# 14. Phase 5 — Gamification

## Objective

Make meaningful training engaging without encouraging low-quality activity.

## Scope

* XP
* levels
* streaks
* daily/weekly goals
* achievements
* badges
* personal records
* exercise mastery
* leaderboard foundation

Gamification must use shared application/domain mechanisms rather than arbitrary exercise-specific logic.

It must remain:

* server-authoritative
* idempotent
* resistant to duplicate/replayed activity

Do not introduce a generic event bus merely to implement gamification.

Detailed requirements belong in:

```text
training/GAMIFICATION.md
```

---

# 15. Phase 6 — Administration Foundation

## Objective

Provide the operational tools required to manage users and operate the platform safely.

## Scope

* admin dashboard
* user management
* role management
* account status management
* basic exercise visibility/availability management
* basic platform operational metrics
* audit visibility
* support management

Phase 6 establishes administrative foundations.

It does **not** implement the complete puzzle/content lifecycle or generator system.

Those belong to Phase 7.

Administrative operations must use the canonical capability system and object-level authorization.

Admin tools must not bypass domain validation or directly corrupt historical training data.

Detailed requirements belong in:

```text
admin/ADMIN_OVERVIEW.md
admin/USER_MANAGEMENT.md
admin/EXERCISE_MANAGEMENT.md
admin/ADMIN_ANALYTICS.md
admin/
SECURITY.md
```

---

# 16. Phase 7 — Content & Generators

## Objective

Provide controlled management of exercises and puzzle content.

## Scope

* puzzle browsing
* puzzle search/filtering
* manual puzzle creation
* puzzle validation
* puzzle review
* puzzle approval
* publishing
* retirement
* content metadata
* difficulty/target-rating metadata
* generator registry
* generator configuration
* generation jobs
* batch generation
* validation
* deduplication
* preview
* generation history

Generated content is never automatically production content.

The conceptual lifecycle is:

```text
Draft
  ↓
Created / Generated
  ↓
Validated
  ↓
Reviewed
  ↓
Approved
  ↓
Published
  ↓
Active
  ↓
Retired
```

Not every lifecycle state requires a separate UI screen initially, but the data model must preserve the necessary lifecycle boundaries.

Detailed requirements belong in:

```text
admin/EXERCISE_MANAGEMENT.md
admin/PUZZLE_MANAGEMENT.md
admin/GENERATORS.md
```

---

# 17. Phase 8 — Analytics

## Objective

Provide trustworthy analytics based on authoritative training data.

Phase 8 is the canonical home of the platform's full analytics system.

## Scope

### Player Analytics

* attempts
* accuracy
* training time
* active days
* exercise performance
* rating/change
* streaks
* progression
* period comparisons where meaningful

### Exercise Analytics

* attempts
* unique players
* accuracy
* completion
* response time
* rating distribution
* performance trends

### Puzzle Analytics

* attempts
* accuracy
* response time
* repeated failures
* observed performance/difficulty

### Platform Analytics

* users
* activity
* sessions
* attempts
* exercise usage
* retention/activity indicators

### Time Ranges

* 7 days
* 30 days
* 90 days
* all time
* custom

Analytics should initially use relational data, indexes, and appropriate aggregation.

Do not introduce a separate analytics platform without demonstrated need.

Detailed requirements belong in:

```text
training/ANALYTICS.md
admin/ADMIN_ANALYTICS.md
```

---

# 18. Phase 9 — Relationships

## Objective

Introduce controlled multi-user training relationships.

## Scope

### Coach → Student

* relationship lifecycle
* invitations/acceptance
* scoped progress access
* assignments foundation
* groups/classes foundation where justified

### Parent → Student

* relationship lifecycle
* multiple children
* scoped progress access
* privacy boundaries

All related-user access requires:

```text
capability
+
active relationship
+
object authorization
+
privacy rules
```

Do not build unnecessary organization-management or classroom infrastructure beyond current requirements.

Detailed requirements belong in:

```text
relationships/
```

---

# 19. Phase 10 — Adaptive Training Foundation

## Objective

Prepare the platform for personalized training without premature ML.

## Scope

Prepare reliable data and boundaries for:

* skill detection
* weakness identification
* difficulty adjustment
* exercise recommendations
* personalized exercise selection
* training plans

Initial recommendation behavior, if implemented, should be:

* deterministic
* explainable
* based on available training signals

Do not introduce machine-learning infrastructure merely to satisfy this phase.

Detailed requirements belong in:

```text
phases/PHASE_10_ADAPTIVE_TRAINING.md
training/ANALYTICS.md
```

---

# 20. Cross-Phase Requirements

Every phase must respect the following.

## Security

* server-side authorization
* secure password storage
* secure sessions
* input validation
* appropriate rate limiting
* object-level access control
* privacy boundaries
* audit of sensitive administrative actions

Detailed security requirements belong in:

```text
SECURITY.md
```

## Data Integrity

* appropriate database constraints
* transactional updates where state must change together
* historical preservation
* safe migrations
* replay/duplicate protection where required

## Testing

Prioritize meaningful tests for:

* business rules
* security
* authorization
* data integrity
* API contracts
* migrations
* regressions
* non-trivial algorithms
* important user flows

Test quantity is not the goal.

---

# 21. Frontend and UX Requirements

All platform interfaces must follow the existing MicroChess design system.

The platform must remain:

* Persian-first
* RTL where appropriate
* child-friendly
* responsive
* accessible
* visually consistent

Chess-specific UI must preserve appropriate LTR behavior.

The global exercise rule remains mandatory:

> Every exercise/play screen must fit within the visible viewport without normal vertical page scrolling on supported desktop, tablet, and mobile orientations.

Dashboards, administration pages, and other content-heavy screens may scroll normally.

Detailed UX requirements belong in:

```text
UX_AND_DESIGN.md
DESIGN_SYSTEM.md
```

---

# 22. Database Evolution

All application database changes must use the repository's migration strategy.

Before changing the schema, inspect:

* current schema
* existing records
* existing migrations
* model conventions
* database initialization

Migrations must:

* preserve existing data
* support fresh database creation
* support upgrade from existing databases
* avoid unnecessary destructive changes
* add indexes only when justified

Large read-only source datasets, including the puzzle source database, must remain separate from normal application persistence unless an accepted specification explicitly requires otherwise.

---

# 23. API Evolution

The platform API must follow:

```text
API_CONTRACTS.md
```

New APIs must respect:

* authentication
* authorization
* validation
* consistent errors
* resource ownership
* pagination/filtering where applicable
* idempotency where required
* API versioning

Routes/controllers must remain thin.

Business rules belong in the appropriate application/domain layer.

Breaking API changes require explicit justification and review.

---

# 24. Historical Data Strategy

The platform must preserve authoritative historical facts separately from derived presentation data.

Conceptually:

```text
Authoritative history
        ↓
Derived metrics/state
        ↓
UI presentation
```

Examples include:

```text
Attempt
Rating Event
Gamification Record
Audit Record
```

Do not create one generic event model merely because several domains contain historical records.

Each domain should use the simplest structure that preserves the information it actually needs.

Derived analytics may be cached or materialized for performance, but they must remain reproducible from authoritative data where required.

---

# 25. Exercise Independence

Exercises must remain independently implementable.

Adding a new exercise should not require rewriting unrelated exercises.

Shared platform infrastructure may provide:

* common sessions
* attempt persistence
* rating hooks
* gamification integration
* analytics integration
* permissions
* content management

Exercise-specific validation, puzzle semantics, and algorithms remain exercise-specific.

---

# 26. Performance

The initial platform should use the existing application architecture and optimize measured bottlenecks.

Prefer:

* indexed relational queries
* bounded queries
* pagination
* appropriate aggregation
* background processing when genuinely necessary
* caching only where justified

Do not design around hypothetical scale requirements that have not been demonstrated.

Performance work must be evidence-driven.

---

# 27. Privacy

The platform is child-first and must follow data minimization.

Do not collect personal information merely because it could be useful later.

Access to related-player information must respect:

* capability
* relationship
* object authorization
* privacy settings

Detailed privacy and security rules belong in:

```text
SECURITY.md
```

---

# 28. Documentation Synchronization

After a meaningful implementation change, update documentation when necessary.

At minimum:

* update the affected domain specification when behavior changes
* update `IMPLEMENTATION_STATE.md`
* update phase status/evidence
* create or update an ADR for significant architectural decisions

Do not knowingly leave contradictory specifications.

Do not duplicate a rule across multiple documents when a canonical source can be referenced instead.

Documentation should describe the requirement once and reference it elsewhere whenever practical.

---

# 29. Autonomous Execution Rules

After receiving an implementation prompt, the agent must work autonomously **within the active phase boundary**.

The agent must:

1. identify the active phase
2. load only the documentation relevant to that phase
3. inspect the repository
4. determine the actual current implementation state
5. reconcile current state with the target
6. identify dependencies and constraints
7. create a concrete implementation plan
8. implement incrementally
9. run meaningful tests
10. run relevant frontend checks
11. verify migrations where applicable
12. perform targeted runtime verification
13. review the diff for unrelated changes
14. update affected documentation
15. update `IMPLEMENTATION_STATE.md`
16. verify phase completion criteria
17. commit the coherent phase change when repository workflow requires commits
18. stop

The agent must **not automatically start the next phase**.

---

# 30. Context Discipline

The implementation agent must optimize for useful reasoning rather than maximum context usage.

The agent should:

* load only relevant documentation
* inspect only relevant repository areas first
* avoid rereading unchanged documents
* avoid duplicating requirements in planning notes
* avoid generating large speculative plans
* keep implementation plans proportional to the active task
* keep test output focused
* avoid broad repository rewrites

A large context window is an available capability, not a requirement to consume it.

---

# 31. No Guessing

The agent must not guess about:

* existing architecture
* database schema
* API behavior
* exercise semantics
* business rules
* permissions
* rating behavior
* migration behavior
* security behavior

When evidence exists, inspect it.

When the specification defines the requirement, follow it.

When neither provides enough information for a safe decision, identify the uncertainty instead of inventing a requirement.

---

# 32. Change Size and Scope

Implementation should be incremental and coherent.

Avoid:

* speculative rewrites
* unrelated cleanup
* dependency churn
* unnecessary abstractions
* duplicate systems
* replacing working components without evidence
* cross-phase implementation
* future-feature scaffolding without a current requirement

A large change is acceptable only when it is required by the active phase, target architecture, or current repository constraints.

---

# 33. Stop Conditions

The agent should normally stop at the end of the active phase.

It may stop earlier when:

* a genuine blocker prevents safe progress
* required information is unavailable
* a destructive decision requires explicit approval
* accepted specifications contain an unresolved conflict
* repository state makes safe continuation impossible

The agent must not stop early merely because:

* the phase is large
* implementation requires multiple files
* multiple tests are required
* the change touches several layers
* a reasonable implementation decision can be derived from repository evidence and accepted specifications

---

# 34. Phase Completion Gate

A phase is complete only when:

1. required capabilities are implemented
2. required backend behavior works
3. required frontend behavior works
4. required database changes are migrated safely
5. authorization/security requirements are enforced
6. meaningful tests pass
7. affected existing functionality remains operational
8. affected UX is responsive and consistent
9. documentation reflects the resulting behavior
10. `IMPLEMENTATION_STATE.md` contains sufficient evidence
11. no unrelated speculative changes remain in the diff

A green test suite alone does not prove phase completion.

---

# 35. Git and Change Safety

Follow the repository's explicit Git workflow.

The agent must:

* keep changes coherent
* avoid unrelated modifications
* avoid committing secrets
* avoid committing generated local databases
* avoid modifying ignored large source datasets
* keep the working tree understandable
* use meaningful commit messages
* avoid mixing unrelated phases in one commit

The repository's explicit Git instructions take precedence over generic assumptions in this document.

---

# 36. Phase Completion Matrix

The canonical roadmap is:

| Phase | Capability                   |
| ----- | ---------------------------- |
| 1     | Foundation                   |
| 2     | Accounts & Identity          |
| 3     | Player Platform              |
| 4     | Exercise Ratings             |
| 5     | Gamification                 |
| 6     | Administration Foundation    |
| 7     | Content & Generators         |
| 8     | Analytics                    |
| 9     | Relationships                |
| 10    | Adaptive Training Foundation |

Phase status is maintained in:

```text
IMPLEMENTATION_STATE.md
```

That file describes **repository reality**.

It must not be used as a second roadmap.

---

# 37. Explicit Non-Goals

The implementation agent must not introduce these merely because they may be useful in the future:

* microservices
* distributed event buses
* message brokers
* Kubernetes
* separate analytics warehouses
* ML infrastructure
* real-time collaboration systems
* full social networking
* full LMS functionality
* payment/subscription systems

A future capability becomes an implementation requirement only when an accepted specification explicitly brings it into scope.

---

# 38. Future Extensions

The architecture should remain reasonably extensible for future capabilities such as:

* email verification and recovery
* MFA
* passkeys
* social login
* notifications
* coach assignments
* parent dashboards
* training plans
* adaptive recommendations
* improved difficulty calibration
* personalized exercise feeds
* more advanced rating systems

These are future extension points.

They are not current implementation requirements unless explicitly included in an accepted phase or specification.

---

# 39. Target Completion

The Master Plan target is reached when the in-scope platform provides:

* secure accounts
* secure authentication and sessions
* guest training and safe guest migration
* player profiles
* external chess identities
* exercise-specific ratings
* rating history
* detailed training history
* player dashboards
* meaningful gamification
* administration
* exercise/content management
* puzzle management
* controlled puzzle generation
* player, exercise, puzzle, and platform analytics
* coach/student infrastructure
* parent/student infrastructure appropriate to the defined scope
* a clean foundation for future adaptive training
* documented security and privacy boundaries
* preserved existing exercise functionality
* responsive platform UX

Future capabilities not explicitly included in the current phases are not required for completion.

---

# 40. Final Principle

The goal is not to build the largest possible system.

The goal is to build the complete required product with:

* clear boundaries
* reliable data
* strong security
* maintainable architecture
* complete required functionality
* minimal unnecessary complexity
* predictable implementation steps
* low operational risk

The implementation agent must optimize for:

```text
Correctness
    +
Completeness
    +
Maintainability
    +
Development Speed
    +
Low Unnecessary Complexity
```

not for maximum abstraction, maximum infrastructure, or maximum code volume.

The safest implementation is the smallest implementation that completely satisfies the active requirement and preserves a clean path to the remaining roadmap.
