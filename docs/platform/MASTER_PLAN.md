# MicroChess Platform — Master Plan

## 1. Document Status

**Status:** Accepted
**Document Type:** Master Product & Implementation Plan

This document defines the target platform, implementation order, global constraints, and autonomous execution rules for evolving MicroChess from its current exercise platform into the planned training platform.

It is a roadmap and execution contract.

Detailed domain behavior belongs in the relevant domain specifications.

---

# 2. Purpose

The implementation agent must be able to use this document to:

1. understand the target state
2. inspect the repository and determine the actual current state
3. identify the earliest incomplete dependency-safe phase
4. implement the missing capabilities
5. verify the implementation
6. update implementation state and affected documentation
7. continue through the remaining phases

The phases form one continuous implementation program.

A phase is not permission to rewrite unrelated existing functionality.

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

This is the target product direction, not a requirement to implement every future capability immediately.

---

# 4. Current-State Rule

The repository is the source of truth for what currently exists.

Before implementation, the agent MUST inspect:

* backend structure
* frontend structure
* models and database schema
* migrations
* API routes
* application/domain services
* exercise architecture
* existing tests
* configuration
* documentation
* current deployment/runtime assumptions where relevant

The documentation defines the intended target state.

The repository defines the current state.

The agent must reconcile the two before making changes.

Existing working functionality must be preserved unless a documented target requirement intentionally changes it.

---

# 5. Global Principles

## 5.1 Preserve Existing Exercises

The platform expansion must integrate with the existing exercise system.

Do not create a second exercise architecture.

Reuse existing shared infrastructure where appropriate, including existing exercise lifecycle, play shell, board, catalog, API client, i18n, and design-system components.

Exercise-specific rules remain inside their exercise domain.

---

## 5.2 Smallest Safe Change

Prefer the smallest coherent implementation that satisfies the requirement.

Avoid:

* speculative rewrites
* unrelated refactors
* duplicate frameworks
* unnecessary dependencies
* premature abstractions
* replacing working architecture without evidence

A large change is acceptable when repository evidence and the target architecture genuinely require it.

---

## 5.3 Server Authority

The server is authoritative for security-sensitive and result-sensitive state, including:

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

The client must not determine authoritative results.

---

## 5.4 Historical Data

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

## 5.5 No Premature Infrastructure

Extensibility should come from clean boundaries and appropriate data models.

Do not introduce infrastructure merely for hypothetical future scale or features.

The initial platform should remain a modular application using the existing technology direction.

Do not introduce microservices, message brokers, distributed event infrastructure, data warehouses, Kubernetes, or ML infrastructure unless an accepted future specification explicitly requires them.

---

# 6. Dependency Graph

The recommended high-level dependency order is:

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
Ratings ──────────┐
    │             │
    └─────────────┤
                  ▼
Phase 5       Gamification
    │             │
    └──────┬──────┘
           ▼
Phase 6
Administration
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

This is the default dependency order, not a requirement that every internal task be strictly sequential.

Tasks may be implemented earlier when their actual dependencies are already satisfied.

Analytics depends fundamentally on reliable training history, not on the completion of all content-management functionality.

---

# 7. Phase 1 — Foundation

## Objective

Prepare the existing application for accounts, persistent training data, authorization, and platform features without breaking existing exercises.

## Scope

* repository and architecture audit
* database/migration strategy
* configuration review
* API conventions
* error handling
* authentication/session primitives
* authorization/capability foundation
* testing foundation
* shared platform boundaries
* documentation synchronization

The phase must establish the foundations required by later phases without implementing speculative platform infrastructure.

## Completion

The application has safe foundations for platform expansion, existing exercises continue to work, and the resulting architecture is documented.

---

# 8. Phase 2 — Accounts & Identity

## Objective

Introduce secure registered accounts and guest identity.

## Scope

* username/password registration
* secure login/logout
* sessions and expiration
* account status
* password hashing
* role foundation
* canonical capability system
* guest sessions
* guest training identity
* guest-to-account migration
* authentication and authorization tests

Registration initially requires only username and password.

Profile information and external chess identities are added separately.

Guest is not a persisted role.

Guest migration must be atomic, idempotent, replay-resistant, and safe against accidental data overwrite.

Detailed requirements belong in:

```text
accounts/
```

---

# 9. Phase 3 — Player Platform

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
* player-facing analytics
* guest migration presentation
* player navigation

External FIDE, Lichess, and Chess.com identities remain separate from MicroChess exercise ratings.

The existing exercise experience remains the foundation of the player platform.

Detailed requirements belong in:

```text
PRODUCT_SCOPE.md
accounts/
training/
UX_AND_DESIGN.md
```

---

# 10. Phase 4 — Exercise Ratings

## Objective

Introduce independent skill ratings for applicable exercises.

## Initial Scope

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

The initial algorithm must be simple, deterministic, testable, and documented.

The architecture should allow future rating improvements without requiring destructive redesign.

Advanced rating algorithms and sophisticated uncertainty/calibration systems are future extensions unless explicitly required by the current rating specification.

Detailed requirements belong in:

```text
training/RATINGS.md
```

---

# 11. Phase 5 — Gamification

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

It must remain server-authoritative and resistant to duplicate/replayed activity.

Do not introduce a generic event bus merely to implement gamification.

Detailed requirements belong in:

```text
training/GAMIFICATION.md
```

---

# 12. Phase 6 — Administration

## Objective

Provide the operational tools required to manage the platform safely.

## Scope

* admin dashboard
* user management
* role management
* account status management
* exercise management
* basic platform analytics
* audit visibility
* support management

Administrative operations must use the canonical capability system and object-level authorization.

Admin tools must not bypass domain validation or directly corrupt historical training data.

Detailed requirements belong in:

```text
admin/
SECURITY.md
```

---

# 13. Phase 7 — Content & Generators

## Objective

Provide controlled management of exercises and puzzle content.

## Scope

* puzzle browsing/search/filtering
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

Not every lifecycle state must require a separate UI screen initially, but the data model must preserve the necessary lifecycle boundaries.

Detailed requirements belong in:

```text
admin/PUZZLE_MANAGEMENT.md
admin/GENERATORS.md
```

---

# 14. Phase 8 — Analytics

## Objective

Provide trustworthy analytics based on authoritative training data.

## Scope

### Player

* attempts
* accuracy
* training time
* active days
* exercise performance
* rating/change
* streaks
* progression

### Exercise

* attempts
* unique players
* accuracy
* completion
* response time
* rating distribution
* performance trends

### Puzzle

* attempts
* accuracy
* response time
* repeated failures
* observed performance/difficulty

### Platform

* users
* activity
* sessions
* attempts
* exercise usage
* retention/activity indicators

### Time ranges

* 7 days
* 30 days
* 90 days
* all time
* custom

Where meaningful, support comparison with the previous equivalent period.

Analytics should initially use relational data, indexes, and appropriate aggregation.

Do not introduce a separate analytics platform without demonstrated need.

Detailed requirements belong in:

```text
training/ANALYTICS.md
admin/ADMIN_ANALYTICS.md
```

---

# 15. Phase 9 — Relationships

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

# 16. Phase 10 — Adaptive Training Foundation

## Objective

Prepare the platform for personalized training without premature ML.

## Scope

The platform should expose reliable data and boundaries for future:

* skill detection
* weakness identification
* difficulty adjustment
* exercise recommendations
* personalized exercise selection
* training plans

Initial recommendation behavior should be deterministic, explainable, and based on available training signals if recommendation functionality is actually implemented.

Do not introduce machine-learning infrastructure merely to satisfy this phase.

Detailed requirements belong in:

```text
phases/PHASE_10_ADAPTIVE_TRAINING.md
training/ANALYTICS.md
```

---

# 17. Cross-Phase Requirements

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

Detailed security requirements belong in `SECURITY.md`.

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

# 18. Frontend and UX Requirements

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

# 19. Database Evolution

All application database changes must use the repository's migration strategy.

Before changing the schema, the agent must inspect:

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

Large read-only source datasets, including the puzzle source database, must remain separate from normal application persistence unless a specification explicitly requires otherwise.

---

# 20. API Evolution

The platform API must follow the conventions defined in `API_CONTRACTS.md`.

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

# 21. Historical Data Strategy

The platform should preserve authoritative historical facts separately from derived presentation data.

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
Gamification Event
Audit Event
```

Do not create one generic event model merely because several domains contain events.

Each domain should use the simplest data structure that preserves the information it actually needs.

Derived analytics may be cached or materialized for performance, but they must remain reproducible from authoritative data where required.

---

# 22. Exercise Independence

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

# 23. Performance

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

# 24. Privacy

The platform is child-first and must follow data minimization.

Do not collect personal information merely because it could be useful later.

Access to related-player information must respect:

* capability
* relationship
* object authorization
* privacy settings

Detailed privacy and security rules belong in `SECURITY.md`.

---

# 25. Documentation Synchronization

After a meaningful implementation change, update documentation when necessary.

At minimum:

* update the affected domain specification when behavior changes
* update `IMPLEMENTATION_STATE.md`
* update phase status/evidence
* create or update an ADR for significant architectural decisions

Do not knowingly leave contradictory specifications.

Do not duplicate a rule across multiple documents when a canonical source can be referenced instead.

---

# 26. Autonomous Execution Rules

After receiving the final implementation prompt, the agent is expected to work autonomously.

The agent must:

1. read the documentation package
2. inspect the repository
3. determine the actual implementation state
4. reconcile current state with the target
5. identify the earliest incomplete dependency-safe phase
6. create a concrete implementation plan for that phase
7. implement it incrementally
8. run meaningful tests
9. run relevant frontend checks
10. verify migrations
11. perform targeted runtime verification
12. update documentation and implementation state
13. continue to the next incomplete phase

The agent must not stop merely because one phase is complete.

---

# 27. Conditions for Stopping

The agent may stop and request human input only when:

* a genuine blocker prevents safe progress
* required information is unavailable
* a destructive decision requires explicit approval
* accepted specifications contain an unresolved conflict
* repository state makes safe continuation impossible

The agent must not stop merely because:

* a phase is large
* implementation requires multiple files
* additional phases remain
* a reasonable implementation decision can be derived from existing documentation and repository evidence

---

# 28. No Guessing

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

# 29. Change Size and Scope

Implementation should be incremental and coherent.

Avoid:

* speculative rewrites
* unrelated cleanup
* dependency churn
* unnecessary abstractions
* duplicate systems
* replacing working components without evidence

A large change is acceptable only when it is required by the target architecture or current repository constraints.

---

# 30. Git and Change Safety

Follow the repository's existing Git workflow and project instructions.

The agent must:

* keep changes coherent
* avoid unrelated modifications
* avoid committing secrets
* avoid committing generated local databases
* avoid modifying ignored large source datasets
* keep the working tree understandable

The repository's explicit Git instructions take precedence over generic assumptions in this document.

---

# 31. Phase Completion Criteria

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
10. implementation state contains sufficient evidence

A green test suite alone does not prove phase completion.

---

# 32. Phase Completion Matrix

The canonical roadmap is:

| Phase | Capability                   |
| ----- | ---------------------------- |
| 1     | Foundation                   |
| 2     | Accounts & Identity          |
| 3     | Player Platform              |
| 4     | Exercise Ratings             |
| 5     | Gamification                 |
| 6     | Administration               |
| 7     | Content & Generators         |
| 8     | Analytics                    |
| 9     | Relationships                |
| 10    | Adaptive Training Foundation |

Phase status is maintained in:

```text
IMPLEMENTATION_STATE.md
```

That status must reflect repository reality.

---

# 33. Explicit Non-Goals

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

# 34. Future Expansion

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

These are **future extension points**, not current implementation requirements unless explicitly included in an accepted phase or specification.

---

# 35. Target Completion

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

# 36. Final Principle

The goal is not to build the largest possible system.

The goal is to build the **smallest clean architecture that can reliably grow into the MicroChess product vision**.

Every implementation decision should balance:

```text
Current usefulness
        +
Future extensibility
        +
Data quality
        +
Security
        +
Simplicity
```

Complexity should be introduced only when it creates concrete product or engineering value.

The platform should hide unnecessary complexity from players while keeping the internal architecture clear, testable, and maintainable.

---

# 37. Master Execution Rule

When the documentation package is accepted, the implementation agent should treat this document as the primary roadmap.

The agent must:

```text
Read the documentation.
        ↓
Inspect the repository.
        ↓
Determine actual current state.
        ↓
Identify the earliest incomplete dependency-safe phase.
        ↓
Implement the smallest safe change.
        ↓
Verify it.
        ↓
Update implementation state and documentation.
        ↓
Continue until all current in-scope phases are complete.
```

The repository determines the current state.

The accepted documentation determines the intended target state.

Accepted ADRs determine explicit architectural decisions.

Together, these define the implementation contract.
