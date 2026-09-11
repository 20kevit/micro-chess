# MicroChess Platform Architecture

## 1. Purpose

This document defines the target technical architecture for the MicroChess platform.

It describes:

* architectural style
* module boundaries
* dependency rules
* backend structure
* frontend structure
* data ownership
* workflow and transaction boundaries
* authentication and authorization boundaries
* historical data and analytics architecture
* content and generator architecture
* background processing
* observability
* extensibility
* performance expectations
* architectural invariants

This document defines the **target architecture**, not a claim about the current repository implementation.

Before implementing any part of this architecture, the implementation agent MUST inspect the existing repository and reconcile the target design with the actual codebase.

The existing repository is evidence of current state.

This document is the source of truth for desired architecture.

---

# 2. Architectural Goals

The platform must support:

1. Guest exercise usage.
2. Player accounts.
3. Guest-to-account migration.
4. Player profiles.
5. Exercise-specific ratings.
6. Detailed training history.
7. Gamification.
8. Player analytics.
9. Exercise analytics.
10. Puzzle analytics.
11. Platform analytics.
12. Administration.
13. Exercise management.
14. Puzzle management.
15. Puzzle generation.
16. Content validation and publishing.
17. Coach/student relationships.
18. Parent/student relationships.
19. Future adaptive training.
20. Future recommendation systems.
21. Future authentication expansion.
22. Future notification systems.

The architecture must achieve these goals without introducing unnecessary distributed-system complexity.

---

# 3. Primary Architectural Style

MicroChess SHALL use a:

> **Modular Monolith with Clean Architecture principles**

The application remains a single deployable system while being divided into strongly bounded business modules.

Conceptually:

```text
One Application
      │
      ├── Identity & Accounts
      ├── Player
      ├── Training
      ├── Ratings
      ├── Gamification
      ├── Analytics
      ├── Content
      ├── Administration
      ├── Relationships
      └── Support
```

Each module owns its business rules and authoritative data responsibilities.

Modules communicate through explicit public contracts rather than reaching directly into each other's internals.

The system MUST NOT begin as microservices.

Microservices may only be considered later if actual operational, scaling, security, or organizational evidence justifies extraction.

---

# 4. Why Modular Monolith

The platform currently has:

* a relatively small deployment footprint
* one primary product
* one development team
* strong transactional workflows
* many interconnected business concepts
* no demonstrated need for independent service scaling

Introducing distributed services now would create unnecessary complexity around:

* deployment
* networking
* authentication
* consistency
* retries
* distributed transactions
* observability
* local development
* testing

The platform should instead establish strong ownership and module boundaries inside one application.

The important architectural boundary is **logical ownership**, not physical deployment.

---

# 5. Current Technology Boundary

The target architecture must preserve the existing MicroChess technology direction unless repository evidence demonstrates a concrete reason to change it.

## Backend

* Python
* FastAPI
* SQLAlchemy
* Pydantic
* python-chess where chess-domain logic is required

## Frontend

* React
* TypeScript
* Vite
* Tailwind CSS
* React Router

## Database

Current development:

* SQLite

Future/production-ready direction:

* PostgreSQL-compatible relational model

## Existing Exercise Infrastructure

The platform MUST preserve and extend the existing shared exercise architecture.

Important existing concepts include:

* ExercisePlay
* ChessBoard
* PieceGameLayout / GameShell
* exercise catalog
* API client
* i18n
* design system
* server-authoritative validation
* Practice mode
* Speed mode

New platform functionality MUST integrate with these concepts rather than creating independent exercise implementations.

---

# 6. High-Level System Architecture

```text
┌──────────────────────────────────────────────────────────┐
│                    React Web Client                      │
│                                                          │
│ Public │ Auth │ Player │ Exercise │ Admin │ Coach        │
│ Parent │ Analytics │ Profile │ Support                  │
└──────────────────────────────┬───────────────────────────┘
                               │ HTTPS / JSON API
                               ▼
┌──────────────────────────────────────────────────────────┐
│                     FastAPI Application                   │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │                    API / Interfaces                │  │
│  └──────────────────────────┬─────────────────────────┘  │
│                             ▼                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │                 Application Layer                  │  │
│  └──────────────────────────┬─────────────────────────┘  │
│                             ▼                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │                    Domain Modules                  │  │
│  │                                                    │  │
│  │ Identity │ Player │ Training │ Ratings             │  │
│  │ Gamification │ Analytics │ Content │ Admin         │  │
│  │ Relationships │ Support                          │  │
│  └──────────────────────────┬─────────────────────────┘  │
│                             ▼                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │                Infrastructure Layer                │  │
│  │                                                    │  │
│  │ SQLAlchemy │ Database │ Files │ External APIs      │  │
│  │ Background Jobs │ Logging │ Configuration          │  │
│  └──────────────────────────┬─────────────────────────┘  │
└─────────────────────────────┼────────────────────────────┘
                              ▼
                     ┌─────────────────┐
                     │   Relational DB │
                     └─────────────────┘
```

---

# 7. Domain Modules

The target architecture contains the following logical modules.

## 7.1 Identity & Accounts

Responsible for:

* users
* credentials
* authentication
* sessions
* guest identity
* account creation
* account lifecycle
* future password recovery
* future email verification
* future MFA/passkeys/social login

It owns identity-related security state.

It MUST NOT own training statistics.

Guest is a temporary access subject, not a persisted application role.

---

## 7.2 Player

Responsible for:

* player profile
* display name
* avatar
* bio
* optional personal information
* privacy preferences
* external chess identities

External identities include:

* FIDE
* Lichess
* Chess.com

External ratings are separate from MicroChess ratings.

---

## 7.3 Training

Responsible for:

* exercise sessions
* attempts
* answers
* correctness
* response time
* Practice/Speed mode behavior
* exercise completion
* training history

Training owns authoritative training facts.

It MUST preserve enough historical information for future analytics and adaptive training.

---

## 7.4 Ratings

Responsible for:

* exercise-specific rating
* rating state
* rating history
* rating changes
* provisional state

Advanced uncertainty/development modeling may be added later if required by the selected rating algorithm.

Ratings are scoped to an exercise or explicitly defined training category.

The exact rating algorithm is documented separately in `training/RATINGS.md`.

---

## 7.5 Gamification

Responsible for:

* XP
* levels
* streaks
* goals
* achievements
* badges
* milestones
* personal records
* exercise mastery
* challenges
* leaderboard state

Gamification consumes authoritative training outcomes and rating results.

It MUST NOT independently determine whether an answer was correct.

---

## 7.6 Analytics

Analytics is a **derived/read-oriented capability**, not the owner of raw training facts.

It is responsible for:

* player analytics
* exercise analytics
* puzzle analytics
* platform analytics
* time-based aggregations
* period comparisons
* retention metrics
* activity metrics
* accuracy analysis
* response-time analysis
* rating trends
* future difficulty-calibration analysis

Authoritative raw facts remain owned by their respective modules.

Analytics may maintain derived or materialized data for performance, but those records are not the source of truth for training state.

---

## 7.7 Content

Responsible for:

* exercises
* puzzles
* puzzle metadata
* difficulty metadata
* target rating
* tags
* content status
* validation
* review
* approval
* publication
* retirement
* generator configuration
* generated content

Content owns the lifecycle of training material.

---

## 7.8 Administration

Administration is a privileged interface over existing domain capabilities.

It is responsible for:

* admin dashboard
* user management
* exercise administration
* puzzle administration
* generator administration
* analytics views
* audit access
* support workflows
* moderation
* relevant operational controls

Admin MUST NOT duplicate domain rules that already belong to another module.

---

## 7.9 Relationships

Responsible for:

* coach/student relationships
* coach invitations
* groups/classes
* assignments
* progress visibility
* coach notes
* parent/student relationships
* parent permissions

Relationship functionality may initially expose only infrastructure and limited UI.

The architecture must not require the full relationship product before these boundaries exist.

---

## 7.10 Support

Responsible for:

* contact requests
* support tickets/messages
* issue status
* admin responses

Future notification delivery may integrate with Support, but notification delivery is not part of the initial Support domain.

---

# 8. Module Internal Structure

Each substantial backend module SHOULD follow this conceptual structure where its complexity justifies it:

```text
module/
├── domain/
│   ├── entities/
│   ├── value_objects/
│   ├── rules/
│   └── services/
│
├── application/
│   ├── commands/
│   ├── queries/
│   ├── services/
│   └── dto/
│
├── infrastructure/
│   ├── repositories/
│   ├── persistence/
│   ├── external/
│   └── adapters/
│
└── interfaces/
    ├── api/
    ├── schemas/
    └── dependencies/
```

This is a conceptual target, not a mandatory directory template.

Small modules MAY use a simpler structure.

The implementation agent MUST inspect the existing repository before creating or moving directories.

Do not reorganize the entire repository merely to make it visually match this diagram.

Repository abstractions MUST NOT be created mechanically for every model. Introduce them where persistence complexity or domain/application isolation justifies them.

---

# 9. Layer Dependency Rule

The preferred dependency direction is:

```text
Interfaces
    ↓
Application
    ↓
Domain

Infrastructure
    ↓
Application / Domain contracts
```

The domain MUST NOT depend on:

* FastAPI
* SQLAlchemy
* Pydantic
* HTTP
* database sessions
* filesystem
* external APIs
* frontend concepts

Application logic may depend on domain concepts and abstract infrastructure contracts.

Infrastructure implements those contracts.

Interfaces translate external requests into application operations.

---

# 10. Module Boundary Rule

A module MUST NOT directly access another module's:

* internal entity implementation
* repository
* database model
* private service
* internal helper
* internal SQL query
* internal storage implementation

Bad:

```text
Analytics → SQLAlchemy → training_attempts table
```

Good:

```text
Analytics → Training public contract
```

or:

```text
Training
   │
   └── exposes authoritative training data
                    ↓
               Analytics
```

Internal application/domain events MAY be used where they reduce coupling, but they are not a requirement for every cross-module interaction.

A distributed message broker is NOT required.

---

# 11. Data Ownership

Every important dataset MUST have one authoritative owner.

```text
Users              → Identity
Player profiles    → Player
Attempts           → Training
Training history   → Training
Ratings            → Ratings
Rating history     → Ratings
XP/Achievements    → Gamification
Exercises/Puzzles  → Content
Derived analytics  → Analytics
Relationships      → Relationships
Support tickets    → Support
Audit records      → Security / Administration boundary
```

Other modules may consume information through defined contracts or read-oriented projections.

They must not become secondary authoritative writers of another module's data.

---

# 12. Database Strategy

The application may use one physical relational database.

Logical ownership MUST remain modular.

Conceptually:

```text
Identity tables
Player tables
Training tables
Rating tables
Gamification tables
Content tables
Analytics-derived tables
Relationship tables
Support tables
Audit tables
```

A shared physical database does not mean a shared business data model.

Modules MUST NOT casually query each other's tables.

Cross-module reads should use:

1. public application contracts
2. explicitly designed query services
3. derived/read models
4. controlled internal application events where useful

The simplest suitable mechanism should be preferred.

---

# 13. Transaction Boundaries

Transactions should protect business invariants.

For an exercise submission, a conceptual workflow may be:

```text
Validate answer
      ↓
Persist authoritative attempt
      ↓
Update rating if rated
      ↓
Record rating history
      ↓
Apply gamification consequences
```

The exact atomic boundary must be determined by business invariants.

In general:

* authoritative answer validation and attempt persistence belong to the core training transaction
* a rated attempt and its rating update should remain consistent
* gamification consequences must not create duplicate rewards
* analytics processing must not make the core training transaction unnecessarily heavy

Analytics MUST NOT require a distributed transaction with Training.

Because the application is a modular monolith, operations that genuinely require atomicity may use one database transaction.

Modules must still preserve ownership boundaries.

---

# 14. Exercise Attempt Architecture

An exercise submission MUST follow the server-authoritative model.

Conceptually:

```text
Client
  │
  │ answer
  ▼
Training API
  │
  ├── identify player/session
  ├── identify exercise/session
  ├── validate request
  │
  ▼
Exercise/domain validator
  │
  ├── determine correctness
  ├── calculate authoritative score
  └── produce result
  │
  ▼
Training
  │
  └── persist attempt/history
  │
  ▼
Ratings
  │
  └── update exercise rating when eligible
  │
  ▼
Gamification
  │
  ├── XP
  ├── streak
  └── achievements
  │
  ▼
Analytics
  │
  └── derive/read metrics
```

The client MUST NOT be trusted for:

* correctness
* score
* rating delta
* XP
* authoritative timing result
* puzzle solution
* authoritative FEN
* hidden answer
* achievement eligibility

The server determines these values.

---

# 15. Guest Architecture

Guests are first-class temporary identities, but **not authenticated/persisted roles**.

A guest may:

* use exercises
* accumulate temporary progress
* receive temporary training state
* receive temporary scoring/rating state
* use Practice/Speed modes where supported

Guest data MUST NOT automatically become permanent until an explicit migration occurs.

Conceptually:

```text
Guest Session
     │
     ├── attempts
     ├── temporary rating state
     ├── temporary progress
     └── preferences
              │
              ▼
        Account Creation
              │
              ▼
       Migration / Merge
              │
              ▼
        Persistent Player
```

Guest migration must prevent:

* duplicate ownership
* accidental data loss
* unauthorized migration
* cross-account data leakage
* duplicate rewards

Detailed rules belong in `accounts/SESSIONS_AND_GUESTS.md`.

---

# 16. Authentication Architecture

Authentication is an Identity responsibility.

API handlers should not implement password verification directly.

Conceptually:

```text
API
 ↓
Authentication service
 ↓
Identity domain/application
 ↓
Credential/session infrastructure
```

Authentication answers:

> Who is this?

Authorization answers:

> What may this identity do?

These concerns remain separate.

---

# 17. Authorization Architecture

Authorization must use the canonical capability vocabulary defined in `SECURITY.md`.

Persisted application roles are exactly:

```text
PLAYER
COACH
PARENT
ADMIN
```

with persisted identifiers:

```text
player
coach
parent
admin
```

`GUEST` is NOT an authenticated/persisted role.

Guest access is represented by a temporary access/session state and its explicitly defined capabilities.

Do not encode authorization only as:

```python
if user.is_admin:
```

Authorization should evaluate:

* authenticated identity
* account status
* role/capability
* resource ownership
* relationship where applicable
* resource state
* relevant business rules

Exact capability names belong in `SECURITY.md`.

---

# 18. Exercise Architecture

The existing shared exercise architecture is a critical platform boundary.

Every exercise should integrate through common infrastructure where applicable:

```text
Exercise Catalog
      ↓
Exercise Definition
      ↓
Exercise Play
      ↓
Exercise Session
      ↓
Answer Submission
      ↓
Training History
      ↓
Rating / Gamification / Analytics
```

Exercise-specific logic remains inside the exercise/domain implementation.

Platform functionality must not force each exercise to independently implement:

* authentication
* rating
* XP
* history
* analytics
* session tracking
* navigation
* generic feedback

Those belong to shared platform infrastructure.

---

# 19. Content Architecture

Content follows a lifecycle:

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

Generated content is never automatically considered production-safe merely because generation succeeded.

A generated puzzle must pass the appropriate validation pipeline.

Publication is an explicit content decision.

---

# 20. Generator Architecture

Generators are content-producing components.

A generator SHOULD expose:

```text
Generator
 ├── identifier
 ├── supported exercise
 ├── configuration schema
 ├── generation operation
 ├── validation operation
 └── metadata
```

The system may support parameters such as:

* target rating
* target difficulty
* quantity
* allowed pieces
* board constraints
* thematic constraints
* uniqueness constraints
* exercise-specific constraints

Target rating and difficulty are objectives, not guarantees.

The generator must not directly publish content.

Conceptually:

```text
Admin
  ↓
Generator Configuration
  ↓
Generation
  ↓
Validation
  ↓
Deduplication
  ↓
Preview
  ↓
Review
  ↓
Approval
  ↓
Publication
```

---

# 21. Analytics Architecture

Analytics is a read-oriented capability built from authoritative historical data.

Authoritative raw facts include:

```text
Attempt
Session
Answer
Correctness
Response time
Score
Exercise
Puzzle
Mode
Rating before
Rating delta
Rating after
XP
Timestamp
Difficulty metadata
```

These facts remain owned by their respective modules.

Derived analytics may include:

* accuracy
* average response time
* active days
* attempts/day
* exercise completion
* rating trend
* rating change
* XP trend
* streak
* retention
* puzzle difficulty indicators
* exercise mastery
* period comparisons

Analytics MUST NOT replace authoritative history.

---

# 22. Analytics Flow

```text
Authoritative Historical Data
            │
            ▼
      Analytics Queries
            │
      ┌─────┴─────┐
      ▼           ▼
On-demand     Derived/
aggregation   materialized data
      │           │
      └─────┬─────┘
            ▼
      Player/Admin UI
```

Initial implementation should calculate many metrics directly from relational data.

Precomputed aggregates should only be introduced when profiling demonstrates a real performance need.

Do not build a separate analytics warehouse prematurely.

---

# 23. Difficulty Calibration

The architecture must preserve enough historical evidence to eventually compare:

```text
Declared Difficulty
        vs
Observed Difficulty
```

This may require:

* puzzle
* player rating
* outcome
* response time where relevant
* attempt count
* mode
* timestamp

Difficulty calibration is a **future capability**, not a required current subsystem.

No dedicated calibration engine is required until an accepted phase explicitly introduces it.

---

# 24. Gamification Architecture

Gamification reacts to authoritative outcomes.

Conceptually:

```text
Training Outcome
      │
      ├── Rating consequence
      ├── XP consequence
      ├── Streak update
      ├── Achievement evaluation
      └── Personal record evaluation
```

Gamification must not modify training correctness.

For example:

```text
Correct answer
```

is a Training fact.

```text
+XP
```

is a Gamification consequence.

These remain conceptually separate.

---

# 25. Internal Event Architecture

The platform MAY use lightweight in-process domain/application events where they provide real decoupling value.

Examples:

```text
UserRegistered
GuestMigrated
AttemptCompleted
RatingChanged
ExerciseCompleted
AchievementUnlocked
PuzzlePublished
RelationshipCreated
```

These are internal application mechanisms.

They do NOT imply:

* Kafka
* RabbitMQ
* Redis Streams
* cloud event infrastructure
* distributed event delivery
* event sourcing

Events are not the primary source of truth.

Authoritative records remain owned by their modules.

Use direct application-level orchestration when it is simpler and clearer.

Do not introduce an event mechanism merely because a workflow crosses modules.

---

# 26. Event Rules

Events, when used, must represent meaningful business/application facts.

Good:

```text
AttemptCompleted
```

Bad:

```text
DatabaseRowInserted
```

Events should not expose internal database implementation details.

Consumers should be idempotent where practical.

Persisted historical records are preferred when a fact must remain authoritative.

Do not turn the entire system into event sourcing unless explicitly decided in an ADR.

---

# 27. Background Processing

Background processing may be used for tasks such as:

* large puzzle generation
* bulk validation
* analytics aggregation
* imports
* future notification delivery
* expensive administrative operations

The initial architecture MUST NOT require distributed job infrastructure.

Start with the simplest reliable mechanism supported by the deployment environment.

The implementation agent must inspect the actual hosting/deployment constraints before choosing a worker system.

---

# 28. Frontend Architecture

The frontend should be organized around product areas rather than one giant component tree.

Conceptually:

```text
src/
├── app/
├── routes/
├── features/
│   ├── auth/
│   ├── player/
│   ├── training/
│   ├── ratings/
│   ├── gamification/
│   ├── analytics/
│   ├── admin/
│   ├── coach/
│   └── parent/
├── exercises/
├── components/
├── api/
├── i18n/
├── hooks/
├── state/
└── styles/
```

This is a conceptual target only.

The agent MUST inspect the existing frontend before reorganizing it.

Do not rewrite the frontend architecture simply for naming consistency.

---

# 29. Frontend Shells

The platform should eventually provide distinct application shells.

## Public Shell

For:

* landing
* exercise discovery
* guest usage
* login
* registration
* support

## Player Shell

For:

* dashboard
* training
* progress
* ratings
* achievements
* profile
* history

## Admin Shell

For:

* overview
* users
* exercises
* puzzles
* generators
* analytics
* support
* audit

## Coach Shell

Future:

* students
* groups
* assignments
* progress
* notes

## Parent Shell

Future:

* children
* progress
* reports
* permissions
* notifications

These shells may share visual primitives but should not become one massive conditional layout.

---

# 30. API Architecture

FastAPI routes should remain thin.

A route should primarily:

1. authenticate/identify the caller
2. validate request schema
3. resolve dependencies
4. call an application operation
5. serialize the result
6. return the HTTP response

Routes should NOT contain:

* complex business rules
* rating algorithms
* puzzle validation
* XP calculations
* direct cross-module database writes
* duplicated authorization logic

---

# 31. API Contract Boundary

API schemas are external contracts.

They should not automatically become domain entities.

Conceptually:

```text
HTTP Request
     ↓
Pydantic Request DTO
     ↓
Application Command
     ↓
Domain
     ↓
Application Result
     ↓
Pydantic Response DTO
     ↓
HTTP Response
```

This separation prevents API design from contaminating domain logic.

---

# 32. Error Handling

The platform should expose consistent API errors.

Errors should distinguish at least:

* authentication failure
* authorization failure
* validation failure
* resource not found
* business rule violation
* conflict
* rate limiting
* unexpected server failure

Internal exception details MUST NOT leak to clients.

User-facing messages should be localized on the frontend where appropriate.

---

# 33. Security Boundaries

Important trust boundaries:

```text
Browser
   │
   │ untrusted input
   ▼
API
   │
   ▼
Application
   │
   ▼
Domain
   │
   ▼
Persistence
```

Everything arriving from the browser is untrusted.

The server must validate all authoritative state.

Sensitive operations require explicit authorization.

Detailed security requirements belong in:

```text
docs/platform/SECURITY.md
```

---

# 34. File and Media Architecture

Future profile/avatar/content media must not be treated as arbitrary public files.

Storage should support:

* controlled upload
* validation
* size limits
* content-type validation
* safe filenames/identifiers
* authorization
* deletion
* future object-storage migration

The exact storage mechanism is an infrastructure decision.

Do not couple domain logic to local filesystem paths.

---

# 35. Caching

Caching is optional.

The system should first achieve:

* correct queries
* correct indexes
* acceptable database performance
* efficient API contracts

Only introduce caching after measuring an actual bottleneck.

Caching must never become the authoritative source of:

* score
* rating
* permissions
* correctness
* ownership

---

# 36. Performance Principles

The expected scale does not justify premature distributed architecture.

The system should instead focus on:

* correct database indexes
* bounded queries
* pagination
* avoiding N+1 queries
* efficient analytics queries
* efficient puzzle selection
* appropriate API payload sizes
* lazy loading where useful
* background processing for expensive bulk work

Large datasets must not be loaded into memory unnecessarily.

---

# 37. Pagination

Administrative and historical datasets must be paginated.

Examples:

* users
* attempts
* sessions
* puzzles
* audit logs
* support tickets
* analytics records

The API must not return unlimited datasets by default.

---

# 38. Observability

The platform should provide enough observability to diagnose:

* authentication problems
* exercise failures
* scoring bugs
* rating inconsistencies
* generator failures
* database failures
* unexpected API errors
* performance problems

At minimum:

* structured application logging
* useful error context
* request correlation where practical
* important business-operation logging
* admin/audit records for sensitive actions

Do not log:

* plaintext passwords
* session secrets
* authentication tokens
* unnecessary personal information
* sensitive credentials

---

# 39. Audit Architecture

Administrative actions affecting important state should be auditable.

Examples:

* user role changes
* account suspension
* puzzle publication
* puzzle retirement
* generator execution
* bulk content operations
* important configuration changes
* manual rating adjustments if ever supported

Audit records should capture enough information to answer:

```text
Who?
What?
When?
Which resource?
What changed?
Why, when applicable?
```

Audit storage is authoritative for audit history, but it must not become a generic replacement for domain history.

---

# 40. Relationships Architecture

Coach/parent functionality must not directly expose unrestricted player data.

Access should be relationship-based.

Example:

```text
Coach
  │
  └── relationship
          │
          ▼
       Student
```

Authorization must verify that the relationship grants the requested access.

A coach cannot query every player's progress merely because the coach is authenticated.

The same applies to parents.

---

# 41. Future Adaptive Training Boundary

The architecture must preserve data needed for future:

* weak-skill detection
* personalized exercise recommendations
* adaptive difficulty
* next-best-exercise selection
* spaced practice
* individualized training plans

However, no ML infrastructure is required now.

Initial architecture:

```text
Historical Training Data
          ↓
Analytics / Training Signals
          ↓
Future Recommendation Engine
```

Do not build a machine-learning platform before useful data exists.

---

# 42. Internationalization Boundary

The application is i18n-ready from the beginning.

Current default:

```text
fa
```

Future languages may include others.

User-facing strings should not be scattered as hard-coded text throughout business logic.

Backend business logic should generally operate on stable identifiers/codes.

Frontend localization maps those identifiers to user-facing strings.

---

# 43. RTL / Chessboard Boundary

The product UI is Persian RTL.

Chessboard coordinate/orientation behavior remains chess-domain behavior and must not be accidentally reversed by global RTL styles.

Therefore:

```text
Application UI → RTL
Chessboard → chess-coordinate-aware layout
```

Exercise screens must preserve the existing responsive rule:

> The complete exercise experience must fit inside the visible viewport without normal vertical page scrolling.

This applies to:

* desktop
* tablet
* mobile portrait
* mobile landscape

Do not solve this with blind `overflow: hidden`.

Use responsive layout constraints and viewport-aware sizing.

---

# 44. Shared Kernel

A small shared kernel MAY contain truly universal technical primitives such as:

* identifiers
* timestamps
* pagination primitives
* generic result/error primitives
* narrowly scoped localization infrastructure
* narrowly scoped security primitives

The shared kernel MUST remain small.

Business concepts MUST NOT be moved into the shared kernel merely to avoid defining module boundaries.

Bad:

```text
shared/
    rating.py
    puzzle.py
    user.py
    achievement.py
    training.py
```

unless a concept is genuinely a universal technical primitive.

---

# 45. Module Interaction Map

Modules have conceptual relationships, but these relationships do not authorize direct access to internal implementations.

The primary interaction patterns are:

```text
Identity
   │
   └── provides identity/authentication context

Player
   │
   └── owns player profile data

Content
   │
   └── provides exercise/puzzle definitions
          │
          ▼
       Training
          │
          ├── authoritative attempts/history
          │
          ├──→ Ratings
          │
          ├──→ Gamification
          │
          └──→ Analytics

Relationships
   │
   └── provides relationship/authorization context
          │
          └── scoped access to Player/Training/Analytics data
```

The actual implementation mechanism may be:

* direct application contract
* query service
* application orchestration
* read model
* lightweight in-process event

Choose the simplest mechanism that preserves ownership.

---

# 46. Avoiding Circular Dependencies

Circular module dependencies are architectural defects.

Forbidden example:

```text
Training → Analytics → Training
```

Prefer:

```text
Training
   ↓
authoritative training data
   ↓
Analytics
```

Or use a dedicated application orchestration layer if the workflow genuinely requires coordination.

Do not solve circular dependencies by creating a giant `utils` module.

---

# 47. Orchestration

Some workflows naturally span multiple modules.

Examples:

* account creation
* guest migration
* completed exercise attempt
* content publication
* coach assignment

These workflows should be orchestrated at the application level.

Domain modules remain owners of their own rules.

Example:

```text
SubmitAttemptUseCase
 ├── Training
 ├── Ratings
 └── Gamification
```

Analytics may consume the resulting authoritative data without becoming part of the core business transaction unless a specific invariant requires it.

The orchestration layer coordinates; it does not absorb the business rules of the participating modules.

---

# 48. Read Models

Read models may be introduced when a UI requires data from multiple domains.

Example:

```text
Player Dashboard
    │
    ├── Player
    ├── Rating
    ├── Training
    ├── Gamification
    └── Analytics
```

Do not force the frontend to make many requests merely because backend boundaries exist.

A dedicated dashboard query/application service may aggregate the required information.

This is a read concern and must not become a new owner of the underlying business data.

---

# 49. Admin Architecture

Admin is a privileged interface, not a separate copy of the application domain.

For example:

```text
Admin publishes puzzle
        ↓
Content application service
        ↓
Content domain rules
        ↓
Persistence
        ↓
Audit record
```

Not:

```text
Admin route
   ↓
direct SQL UPDATE
```

Admin actions must use the same authoritative business rules as normal operations.

---

# 50. Testing Architecture

Testing should follow business risk.

Required categories include:

## Domain Tests

For:

* scoring
* validation
* rating rules
* gamification rules
* content lifecycle rules
* permission rules

## Application Tests

For:

* workflows
* guest migration
* attempt submission
* cross-module orchestration
* authorization

## Integration Tests

For:

* database behavior
* repositories where present
* API contracts
* important persistence invariants

## Frontend Tests

For:

* important interaction flows
* shared exercise behavior
* authentication state
* critical admin/player flows

Do not create tests merely to increase coverage numbers.

Tests should protect meaningful behavior and discovered regressions.

---

# 51. Architectural Tests

Where practical, the project should eventually enforce:

* module dependency rules
* forbidden imports
* no cross-module repository access
* no route-level business logic
* no direct database writes from UI/API handlers
* no domain dependency on infrastructure
* no circular module dependencies

Architecture rules are most valuable when they can be automatically checked.

However, architecture tests MUST remain proportional to project complexity.

Do not build an elaborate architecture-testing framework before simple import/dependency checks become insufficient.

---

# 52. Migration Strategy

The platform will evolve from the existing MicroChess codebase.

Therefore implementation MUST be incremental.

Preferred approach:

```text
Inspect existing code
       ↓
Identify current boundary
       ↓
Add target capability
       ↓
Integrate with existing architecture
       ↓
Migrate/refactor only where necessary
       ↓
Test
       ↓
Document
```

Do NOT perform a giant rewrite.

Do NOT rename or move large numbers of files merely to satisfy this document.

Do NOT replace working exercise infrastructure without evidence.

---

# 53. Backward Compatibility

Existing exercises must continue to work while platform functionality is introduced.

Every platform phase must preserve:

* existing exercise behavior
* existing scoring semantics
* existing API behavior where intentionally public
* existing seed workflows
* existing frontend build
* existing tests

If a breaking change is genuinely required, document it explicitly before implementation.

---

# 54. Deployment Architecture

Initial target:

```text
Single frontend build
        +
Single backend application
        +
Single relational database
```

The exact hosting/deployment mechanism must be based on the repository and deployment environment.

The architecture must not assume:

* Kubernetes
* Docker orchestration
* multiple backend services
* message brokers
* distributed caches

unless later evidence justifies them.

---

# 55. Future Service Extraction

The modular architecture should preserve the possibility of extracting a module later.

Potential candidates could eventually include:

* external chess identity integration
* analytics
* content generation
* notification delivery

But extraction is NOT a current requirement.

A module should only be extracted if evidence shows:

* independent scaling requirements
* operational isolation needs
* different deployment cadence
* clear ownership boundary
* resource contention
* security isolation requirement
* meaningful organizational benefit

The existing module contract should become the extraction boundary.

---

# 56. Architecture Invariants

The following are mandatory.

### Invariant 1 — Server authority

The client never determines authoritative training outcomes.

### Invariant 2 — One owner per important dataset

There must be one authoritative writer for each business dataset.

### Invariant 3 — No cross-module internals

Modules never reach into another module's private implementation.

### Invariant 4 — Domain independence

Domain rules do not depend on HTTP, database, or frontend infrastructure.

### Invariant 5 — Thin routes

API routes coordinate; they do not implement business logic.

### Invariant 6 — Historical data is valuable

Important training facts are retained rather than overwritten.

### Invariant 7 — Internal ratings are separate

External chess ratings are never silently treated as MicroChess ratings.

### Invariant 8 — Content publication is explicit

Generated content is not automatically production content.

### Invariant 9 — Authorization is explicit

Authentication alone does not grant access.

### Invariant 10 — No premature distributed architecture

Do not introduce microservices or distributed infrastructure without evidence.

### Invariant 11 — Existing exercise architecture is preserved

Platform work must integrate with the shared exercise system.

### Invariant 12 — Responsive exercise screens

Exercise play screens must fit the viewport without normal page scrolling.

### Invariant 13 — Guest is not a persisted role

Guest access is temporary and must not be treated as a fourth/fifth application role.

### Invariant 14 — Analytics is not source of truth

Derived analytics must never replace authoritative training, rating, or gamification records.

---

# 57. Forbidden Architectural Patterns

The following are explicitly discouraged or forbidden unless a later ADR overrides them.

## Giant Service

```text
PlatformService
```

containing every business rule.

## Giant Model

A single User/Player model containing unrelated training, analytics, gamification and admin state.

## God Router

A route module implementing authentication, rating, scoring, XP and analytics.

## Cross-Module SQL

Direct SQLAlchemy access to another module's tables.

## Shared Mutable State

Global mutable objects holding business state.

## Client-Authoritative Scoring

Never trust client-provided score/rating/correctness.

## Hidden Business Rules in Serializers

Pydantic schemas should validate shape, not become the business domain.

## Analytics as Source of Truth

Aggregates must not replace authoritative history.

## Premature Microservices

No service splitting without evidence.

## Premature Event Infrastructure

No message broker merely because internal events exist conceptually.

## Generic Utility Dumping Ground

Do not hide domain coupling inside `utils.py`.

## Giant Refactor

Do not rewrite the existing repository simply to make it match this document.

## Mechanical Repository Abstraction

Do not create repository interfaces solely because the architecture diagram contains a `repositories/` directory.

## Architecture for Architecture's Sake

Do not introduce abstractions, layers, modules, background workers, caches, events, or read models without a concrete problem they solve.

---

# 58. Architectural Decision Process

When a new architectural question appears:

1. Inspect existing code.
2. Check this architecture document.
3. Check `MASTER_PLAN.md`.
4. Check the relevant domain specification.
5. Check existing ADRs.
6. Determine whether the decision is local or architectural.
7. If architectural and consequential, create an ADR.
8. Implement only after the decision is clear.

The implementation agent must not silently introduce a new architectural paradigm.

Local implementation choices do not require ADRs when they remain consistent with existing architectural constraints.

---

# 59. Documentation Hierarchy

When documents disagree, use the priority defined by `docs/platform/README.md`.

In general:

```text
Accepted ADR
    ↓
MASTER_PLAN.md
    ↓
Domain specification
    ↓
Architecture / Data / API / Security / UX
    ↓
Phase specification
    ↓
Current implementation
```

However, current implementation is evidence of reality and must always be inspected before modifying it.

---

# 60. Definition of Architectural Completion

The target architecture is considered established when:

* modules have clear ownership
* dependencies are understandable
* API routes are thin
* domain rules are isolated
* platform functionality integrates with existing exercises
* authoritative history is preserved
* ratings have a dedicated boundary
* gamification has a dedicated boundary
* analytics has a dedicated derived/read boundary
* content has a dedicated boundary
* admin uses domain capabilities rather than bypassing them
* guest migration has a defined boundary
* relationships have a defined authorization boundary
* future adaptive training can consume historical data
* architectural invariants are documented and, where practical, tested

The architecture does NOT require every future feature to be implemented immediately.

---

# 61. Final Rule for Implementation Agents

Before implementing any architecture described here:

1. Read `docs/platform/README.md`.
2. Read `docs/platform/MASTER_PLAN.md`.
3. Read this file.
4. Inspect the actual repository.
5. Identify which parts already exist.
6. Identify which parts are partially implemented.
7. Identify which parts are missing.
8. Do not recreate existing infrastructure.
9. Do not perform speculative rewrites.
10. Implement the smallest coherent change that advances the target architecture.
11. Run meaningful tests.
12. Verify existing exercises still work.
13. Update implementation-state documentation.
14. Continue to the next phase when no genuine blocker exists.

The goal is not to make the repository look architecturally perfect.

The goal is to make MicroChess **coherent, maintainable, extensible, secure, and capable of growing from an exercise platform into a complete player/training platform without architectural collapse.**
