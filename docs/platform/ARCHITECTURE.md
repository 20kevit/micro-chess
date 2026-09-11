# MicroChess Platform — Data Model

## 1. Document Status

**Status:** Accepted
**Document Type:** Target Logical Data Model
**Scope:** Identity, training, ratings, gamification, content, administration, relationships, analytics, and historical data

This document defines the **target logical data model** for MicroChess.

It does **not** require the current repository to already contain these entities, tables, fields, or relationships.

The repository remains the source of truth for the current implementation.

The implementation agent MUST inspect existing:

* SQLAlchemy models
* migrations
* database initialization
* seed data
* exercise persistence
* training persistence
* tests

before changing the database.

> **Documented ≠ Implemented.**
> **Logical target ≠ required current schema.**

Only capabilities required by the active phase should be implemented.

---

# 2. Authority and Related Documents

Data-model decisions are governed by:

1. accepted ADRs
2. `MASTER_PLAN.md`
3. the most specific domain specification
4. this document
5. `API_CONTRACTS.md`
6. `SECURITY.md`
7. active phase specification
8. repository implementation

This document defines:

* entities
* ownership
* relationships
* historical boundaries
* important invariants
* authoritative vs derived data

It does not define:

* HTTP behavior
* UI behavior
* authentication protocol
* rating algorithm
* exercise-specific algorithms

Those belong to their canonical documents.

---

# 3. Core Data Principles

The platform should use a relational transactional model with the following principles:

1. Important entities have stable identifiers.
2. Important relationships use explicit foreign keys.
3. Important invariants are enforced at the database level where practical.
4. Historical facts are preserved.
5. Current state may be materialized for efficient reads.
6. Derived data is never the sole source of truth for authoritative facts.
7. JSON is used only where structure is genuinely flexible.
8. Important relational entities must not be hidden inside arbitrary JSON.
9. Indexes follow actual query patterns.
10. Denormalization requires a concrete justification.
11. Destructive cascades are avoided for historical facts.
12. The model remains practical for SQLite development and PostgreSQL production.
13. Domain ownership remains aligned with `ARCHITECTURE.md`.
14. Future entities are not created before their phase requires them.

---

# 4. Current State vs Target State

The following distinction is mandatory:

```text
Repository
    = current implementation

DATA_MODEL.md
    = target logical model
```

The agent MUST NOT create every conceptual entity listed here merely because it appears in this document.

Before introducing a new table or field:

1. inspect existing structures
2. determine whether an equivalent already exists
3. determine whether the active phase actually requires it
4. reuse existing structures where appropriate
5. add only the missing capability

Unnecessary database redesign is prohibited.

---

# 5. Identifier Strategy

Every major entity should have a stable primary identifier.

Conceptually:

```text
id
```

The exact type must follow the existing repository convention.

Do not introduce a new global identifier strategy merely because another strategy may be theoretically better.

Do not mix identifier strategies without a demonstrated need.

External identifiers must remain separate from internal primary keys.

Example:

```text
User.id
ExternalIdentity.external_id
```

An external provider identifier is not the application's primary key.

---

# 6. Common Metadata

Use timestamps when they represent meaningful business information.

Common fields may include:

```text
created_at
updated_at
```

Lifecycle-managed entities may additionally use:

```text
published_at
retired_at
deleted_at
```

Do not mechanically add every timestamp to every table.

Historical events should have an explicit occurrence timestamp when needed.

---

# 7. Ownership Model

Owner-bearing training records use explicit ownership.

For records that may belong either to a registered user or to a guest session:

```text
user_id XOR guest_session_id
```

Exactly one owner must be present.

Do not use an unconstrained:

```text
owner_type
owner_id
```

pair when explicit foreign keys can preserve referential integrity.

Because SQLite and PostgreSQL differ in some nullable-constraint behavior, the implementation must use an appropriate constraint/index strategy.

---

# 8. Identity Domain

## 8.1 User

`User` represents a persistent application identity.

Conceptual fields:

```text
User
----
id
username
password_hash
status
created_at
updated_at
last_login_at
```

Initial registration requires:

```text
username
password
```

The database must enforce username uniqueness.

Registration does not initially require:

* email
* phone
* real name
* FIDE ID
* Lichess identity
* Chess.com identity

---

# 9. User Status

Possible conceptual states:

```text
ACTIVE
SUSPENDED
DISABLED
DELETED
```

Exact representation follows repository conventions.

Suspending or disabling an account must not destroy historical training facts.

---

# 10. Roles

Canonical persisted roles:

```text
PLAYER
COACH
PARENT
ADMIN
```

Guest is not a persisted role.

Roles may be modeled independently:

```text
Role
----
id
code
name
```

and assigned through:

```text
UserRole
--------
id
user_id
role_id
created_at
```

Recommended invariant:

```text
UNIQUE(user_id, role_id)
```

The model permits a user to have multiple roles.

Example:

```text
PLAYER + COACH
```

---

# 11. Capabilities and Permissions

Authorization uses the canonical capability vocabulary defined by `SECURITY.md`.

A separate permission model may eventually contain:

```text
Permission
----------
id
code
description
```

and:

```text
RolePermission
--------------
role_id
permission_id
```

However, this is not automatically required.

The initial implementation may use application-defined role-to-capability mappings.

Do not build a permission-management subsystem unless the active requirements justify it.

---

# 12. Guest Session

Guest is represented by a temporary server-controlled session.

Conceptual fields:

```text
GuestSession
------------
id
created_at
last_seen_at
expires_at
status
```

A secure token/credential may identify the session.

The raw credential should not be stored in plaintext when hashing provides an appropriate security boundary.

The browser must never establish ownership merely by supplying a guest session ID.

---

# 13. Guest-Owned Data

Temporary training records may reference:

```text
guest_session_id
```

instead of:

```text
user_id
```

Guest-owned records must remain isolated from other guests.

Expired guest sessions may be retained only as long as required by the product and security policies.

---

# 14. Guest Migration

Guest-to-account migration transfers temporary state from:

```text
GuestSession
```

to:

```text
User
```

Relevant state may include:

* training attempts
* sessions
* ratings
* XP
* achievements
* progress

Migration must preserve the historical meaning of the records.

It must be:

* authenticated where required
* ownership-checked
* atomic where appropriate
* idempotent
* replay-resistant

A conceptual migration record may be:

```text
GuestMigration
--------------
id
guest_session_id
user_id
status
started_at
completed_at
```

The implementation should introduce this record only when the migration workflow requires durable migration state.

---

# 15. Player Profile

Persistent account identity and player profile are separate concerns.

```text
User
 │
 └── PlayerProfile
```

Conceptual fields:

```text
PlayerProfile
-------------
id
user_id
display_name
avatar_reference
bio
date_of_birth
privacy_settings
created_at
updated_at
```

Personal information should be optional and minimized.

Invariant:

```text
UNIQUE(user_id)
```

A persistent player has at most one primary player profile.

---

# 16. External Chess Identity

External chess identities are separate from the MicroChess identity and rating systems.

Conceptual fields:

```text
PlayerExternalIdentity
----------------------
id
user_id
provider
external_id
username
rating
rating_type
is_verified
verified_at
created_at
updated_at
```

Possible providers include:

```text
fide
lichess
chess_com
```

Provider-specific capabilities must not be assumed to be identical.

Where a provider exposes a stable external identifier, uniqueness should normally be enforced on:

```text
(provider, external_id)
```

Where the product requires only one identity per provider per player, an additional constraint may be applied.

External identity verification is server-controlled.

---

# 17. External Rating Independence

External ratings and MicroChess ratings are completely separate.

Example:

```text
Lichess Rapid: 2050
MicroChess Pin: 1478
```

The data model must never represent them as one rating.

Self-reported external ratings may initially be unverified.

---

# 18. Exercise

MicroChess already has an exercise concept.

Conceptual fields:

```text
Exercise
--------
id
slug
title_key
description_key
status
sort_order
difficulty
supports_practice
supports_speed
rating_enabled
created_at
updated_at
```

The implementation MUST first inspect the existing exercise model.

Do not create a second exercise entity if an existing model already serves this role.

---

# 19. Exercise Configuration

Flexible exercise-specific configuration may use JSON.

Conceptual:

```text
ExerciseConfiguration
---------------------
exercise_id
config_json
schema_version
updated_at
```

Appropriate uses include:

* time limits
* mode settings
* selection counts
* exercise-specific parameters

Important historical facts must not depend exclusively on mutable configuration JSON.

When configuration affects interpretation of historical data, the relevant version or snapshot must be preserved with the historical record.

---

# 20. Puzzle / Training Content

A puzzle is a concrete unit of exercise content.

Conceptual fields:

```text
Puzzle
------
id
exercise_id
identifier
status
difficulty
target_rating
source
source_reference
content_version
created_at
updated_at
published_at
retired_at
```

Not every exercise must use identical content semantics.

The data model must not force every exercise into a fake universal schema.

---

# 21. Puzzle Content Payload

Where exercise content varies significantly, structured JSON may be appropriate:

```text
PuzzleContent
-------------
puzzle_id
content_json
schema_version
```

Relational fields should be used when a value is frequently needed for:

* searching
* filtering
* authorization
* analytics
* uniqueness
* reporting

Do not hide important business entities inside JSON.

The existing large read-only `puzzles.db` remains a separate content source unless an explicit import/migration requirement is approved.

---

# 22. Content Lifecycle

Canonical conceptual lifecycle:

```text
DRAFT
  ↓
CREATED / GENERATED
  ↓
VALIDATED
  ↓
REVIEWED
  ↓
APPROVED
  ↓
PUBLISHED
  ↓
ACTIVE
  ↓
RETIRED
```

The current state may live directly on `Puzzle`.

Historical transitions may be recorded separately where auditability requires them.

---

# 23. Content Status History

When lifecycle auditing is required:

```text
PuzzleStatusHistory
-------------------
id
puzzle_id
from_status
to_status
changed_by_user_id
reason
created_at
```

Historical lifecycle records should be treated as append-only facts.

---

# 24. Puzzle Tags

If tags are required for filtering and analytics:

```text
PuzzleTag
---------
id
code
name
```

and:

```text
PuzzleTagAssignment
-------------------
puzzle_id
tag_id
```

Invariant:

```text
UNIQUE(puzzle_id, tag_id)
```

Do not create tagging infrastructure before content requirements require it.

---

# 25. Training Session

A training session is a bounded unit of exercise activity where the exercise requires an explicit session.

Conceptual fields:

```text
TrainingSession
---------------
id
user_id
guest_session_id
exercise_id
mode
started_at
ended_at
status
question_count
completed_count
score
```

Owner invariant:

```text
user_id XOR guest_session_id
```

Not every exercise must use a formal session.

The implementation must not introduce session persistence where the exercise architecture does not require it.

---

# 26. Question Instance

A question instance represents the concrete server-issued question delivered during a training session.

This is distinct from the underlying `Puzzle`.

Conceptually:

```text
Puzzle
  ↓
QuestionInstance
  ↓
Attempt
```

Possible fields:

```text
QuestionInstance
----------------
id
session_id
exercise_id
puzzle_id
sequence_number
issued_at
expires_at
status
```

A question instance binds content to its delivery context.

It allows the server to distinguish:

* the underlying reusable puzzle
* a specific occurrence of that puzzle in a training session

The client must submit the `question_instance_id`, not merely the `puzzle_id`, when the exercise uses question instances.

A question-instance model is not required for exercises whose current architecture does not need it.

---

# 27. Training Attempt

An attempt is an authoritative historical record of one submitted answer.

Conceptual fields:

```text
TrainingAttempt
---------------
id
user_id
guest_session_id
session_id
question_instance_id
exercise_id
puzzle_id
mode
started_at
answered_at
response_time_ms
is_correct
score
rating_before
rating_delta
rating_after
xp_awarded
difficulty_snapshot
exercise_version
content_version
created_at
```

Owner invariant:

```text
user_id XOR guest_session_id
```

When applicable:

```text
question_instance_id
```

must link the attempt to the concrete delivered question.

`puzzle_id` remains useful as historical/content reference.

---

# 28. Attempt as Historical Source

The attempt record represents what happened at the time.

Historical fields may include:

```text
difficulty_snapshot
rating_before
rating_delta
rating_after
response_time_ms
exercise_version
content_version
```

Old attempts must remain interpretable even if current:

* puzzle difficulty
* scoring configuration
* exercise configuration
* content version

changes later.

---

# 29. Attempt Answer

An attempt may store the submitted answer when historical/debugging value justifies retaining it.

Conceptually:

```text
AttemptAnswer
-------------
attempt_id
answer_json
schema_version
```

The stored answer is evidence of what was submitted.

It is not an authoritative result.

Do not store unnecessarily large payloads.

For chess exercises, use a canonical representation where practical.

---

# 30. Attempt Result

Server-generated result fields may include:

```text
is_correct
score
feedback_code
response_time_ms
```

The client cannot authoritatively assign these values.

---

# 31. Training History Immutability

Completed attempts should be treated as append-only historical facts.

Normal clients cannot:

* edit
* delete
* rewrite
* recompute

historical attempts.

Explicit administrative correction workflows, if ever required, must preserve the original meaning and create an auditable corrective record.

---

# 32. Rating State

MicroChess ratings are scoped independently.

At minimum, rating scope is:

```text
exercise
```

Conceptual fields:

```text
PlayerRating
------------
id
user_id
guest_session_id
exercise_id
rating
rating_deviation
is_provisional
games_count
updated_at
```

Owner invariant:

```text
user_id XOR guest_session_id
```

Current-state uniqueness:

```text
(user_id, exercise_id)
```

or:

```text
(guest_session_id, exercise_id)
```

as applicable.

Do not create a global:

```text
User.rating
```

as the canonical MicroChess rating.

---

# 33. Rating History

Every authoritative rating change must be represented historically.

```text
RatingEvent
-----------
id
user_id
guest_session_id
exercise_id
attempt_id
rating_before
rating_delta
rating_after
reason
created_at
```

Owner invariant:

```text
user_id XOR guest_session_id
```

Possible reasons include:

```text
attempt
initialization
calibration
migration
manual_adjustment
```

Manual adjustments require an explicit controlled workflow and audit trail if ever implemented.

---

# 34. Rating Invariants

For ordinary rating changes:

```text
rating_after = rating_before + rating_delta
```

The exact rating algorithm is defined in:

```text
training/RATINGS.md
```

The database does not reproduce the rating algorithm.

The application/domain layer is authoritative.

The attempt result, rating state change, and rating event must be transactionally consistent.

---

# 35. Gamification

Gamification has two categories:

```text
Historical facts
+
Current/materialized state
```

Historical facts include:

* XP events
* achievement unlocks
* challenge completion
* other reward events

Current state may include:

* total XP
* level
* current streak
* mastery

Historical records remain authoritative.

---

# 36. XP Event

XP should be represented as historical reward events.

Conceptual:

```text
XPEvent
-------
id
user_id
guest_session_id
amount
reason
attempt_id
achievement_id
goal_id
challenge_id
created_at
```

Owner invariant:

```text
user_id XOR guest_session_id
```

Use explicit source relationships where practical.

Avoid:

```text
source_type
source_id
```

as a generic unconstrained pair unless a documented future requirement makes it necessary.

---

# 37. Current Gamification State

A materialized state may be stored for efficient reads:

```text
PlayerGamificationState
-----------------------
id
user_id
guest_session_id
total_xp
level
updated_at
```

Owner invariant:

```text
user_id XOR guest_session_id
```

This state is a read optimization.

The XP ledger remains the historical source of truth.

---

# 38. Achievements

Achievement definitions:

```text
Achievement
-----------
id
code
name_key
description_key
criteria_json
schema_version
active
```

Player unlocks:

```text
PlayerAchievement
-----------------
id
user_id
guest_session_id
achievement_id
unlocked_at
```

An unlock must reference a valid achievement definition.

Client-controlled achievement unlock is prohibited.

---

# 39. Streaks

Current streak state may be materialized.

Conceptually:

```text
PlayerStreak
------------
id
user_id
guest_session_id
current_streak
longest_streak
last_qualified_date
updated_at
```

The exact streak rules belong to the gamification domain.

The client cannot set streak state.

---

# 40. Goals

Future goal infrastructure may use:

```text
TrainingGoal
------------
id
user_id
goal_type
period
target
status
started_at
ended_at
```

Goal progress should be derived from authoritative training activity.

Do not implement a large goal subsystem before Phase 5 requires it.

---

# 41. Mastery

Exercise mastery is a current derived state.

Canonical conceptual states:

```text
NOT_STARTED
LEARNING
PRACTICING
PROFICIENT
MASTERED
```

Possible representation:

```text
PlayerExerciseMastery
---------------------
id
user_id
exercise_id
state
score
updated_at
```

The exact mastery algorithm belongs to the training/gamification domain.

Mastery must not replace raw attempt history.

---

# 42. Personal Records

Personal records may include:

* highest exercise rating
* best score
* fastest valid response
* longest streak
* highest XP period

These are derived or materialized values.

They should be recalculable from authoritative history where practical.

Do not create a separate record for every metric merely because a UI may display it.

---

# 43. Analytics

Analytics is a **derived/read-oriented domain**.

Analytics does not own:

* attempts
* rating events
* XP events
* content history

Those remain owned by their source domains.

Analytics may derive:

* player statistics
* exercise statistics
* puzzle statistics
* platform statistics

A separate analytics fact table or aggregate may be introduced only when there is a demonstrated performance/query requirement.

Any such projection should be rebuildable from authoritative source data where practical.

---

# 44. Analytics Aggregates

Possible future aggregates include:

```text
PlayerDailyStats
----------------
user_id
date
attempts
correct_attempts
accuracy
training_time_ms
xp
rating_change
```

```text
ExerciseDailyStats
------------------
exercise_id
date
attempts
correct_attempts
accuracy
avg_response_time_ms
unique_players
```

```text
PuzzleStats
-----------
puzzle_id
attempts
correct_attempts
accuracy
avg_response_time_ms
unique_players
observed_difficulty
```

These are derived structures.

They are not required in the initial implementation.

Do not duplicate the entire training history into an analytics table without evidence.

---

# 45. Period Comparisons

Analytics must eventually support:

```text
7d
30d
90d
all
custom
```

Comparisons should be calculated from authoritative timestamps or rebuildable aggregates.

Do not store every possible comparison as permanent data.

---

# 46. Content Generators

A generator is a registered content-generation capability.

Conceptual:

```text
GeneratorDefinition
-------------------
id
code
name
exercise_id
version
config_schema_json
active
created_at
updated_at
```

Generators are part of the content domain.

Do not create generator tables until Phase 7 requires them.

---

# 47. Generator Run

Meaningful generator operations should be traceable.

Conceptual:

```text
GeneratorRun
------------
id
generator_id
requested_by_user_id
exercise_id
target_rating
target_difficulty
requested_count
generated_count
validated_count
accepted_count
status
started_at
completed_at
config_snapshot_json
error_summary
```

The configuration snapshot preserves historical interpretation when generator configuration changes later.

Generator runs are operational historical records.

---

# 48. Generated Content Traceability

Generated content must be traceable to its generator run where applicable.

Prefer one clear relationship:

```text
Puzzle.generator_run_id
```

or:

```text
GeneratedPuzzle
---------------
generator_run_id
puzzle_id
```

Do not create both structures without a concrete requirement.

---

# 49. Content Validation

Where reproducibility matters:

```text
ContentValidation
-----------------
id
puzzle_id
validator
validator_version
status
result_json
validated_at
```

A validator version may affect the interpretation of a validation result.

Not every validation result needs permanent storage if validation is deterministic and does not require auditability.

---

# 50. Content Review

Where approval requires human review:

```text
ContentReview
-------------
id
puzzle_id
reviewer_user_id
status
notes
created_at
updated_at
```

This belongs to Phase 7.

Do not create content-review infrastructure in earlier phases merely because the target model describes it.

---

# 51. Administration

Administration primarily operates on entities owned by other domains.

Examples:

```text
users        → Identity
puzzles      → Content
training     → Training
ratings      → Ratings
analytics    → Analytics
```

Administration does not become the owner of the underlying business facts merely because administrators can manage them.

---

# 52. Audit Log

Sensitive administrative operations may produce:

```text
AuditLog
--------
id
actor_user_id
action
target_type
target_id
metadata_json
created_at
```

Audit is an administrative/security concern.

Audit records are historical facts.

Do not use audit records as a generic event bus.

---

# 53. Support

Support tickets belong to the support/administration boundary.

Conceptually:

```text
SupportTicket
-------------
id
user_id
guest_session_id
subject
status
created_at
updated_at
closed_at
```

Messages may later use:

```text
SupportMessage
--------------
id
ticket_id
author_user_id
author_guest_session_id
body
created_at
```

Support entities are not required before the relevant administration phase.

---

# 54. Coach / Student Relationship

Relationships use explicit lifecycle state.

Canonical states:

```text
PENDING
ACTIVE
REVOKED
```

Conceptual:

```text
CoachStudentRelationship
------------------------
id
coach_user_id
student_user_id
status
created_at
accepted_at
ended_at
```

Invariant:

```text
coach_user_id != student_user_id
```

Access requires:

* capability
* active relationship
* object authorization
* privacy rules

---

# 55. Coach Assignments

Assignments are a future relationship/content capability.

Conceptually:

```text
TrainingAssignment
------------------
id
coach_user_id
student_user_id
exercise_id
status
created_at
due_at
```

Do not implement assignment structures until Phase 9 requires them.

---

# 56. Parent / Student Relationship

Conceptual:

```text
ParentStudentRelationship
------------------------
id
parent_user_id
student_user_id
status
created_at
accepted_at
ended_at
```

Invariant:

```text
parent_user_id != student_user_id
```

Parents receive only data explicitly permitted by the relationship and privacy policy.

---

# 57. Relationship Scope

Relationship-specific scopes may eventually include:

```text
view_progress
view_analytics
view_assignments
view_achievements
```

Do not encode broad unrestricted access merely because a relationship exists.

The exact permission/consent model belongs to:

```text
relationships/
SECURITY.md
```

---

# 58. Privacy Settings

Where product behavior requires persistent privacy settings:

```text
PlayerPrivacySettings
---------------------
id
user_id
profile_visibility
leaderboard_visibility
coach_visibility
parent_visibility
analytics_visibility
updated_at
```

Do not create a large privacy-settings table for settings that do not yet exist.

Privacy semantics remain governed by `SECURITY.md`.

---

# 59. Notifications

Notifications are **future infrastructure**.

They are not required by the minimum platform data model.

A future model may contain:

```text
Notification
------------
id
user_id
type
payload_json
read_at
created_at
```

Do not implement notification tables or channels merely because a future architecture may use them.

---

# 60. Data Retention

Retention differs by data category.

Long-lived data may include:

* account state
* player profile
* ratings
* rating history
* important training history
* achievement history
* content lifecycle history
* audit records

Potentially temporary data may include:

* expired guest sessions
* transient job state
* temporary uploads
* caches

Retention rules must be explicit.

Do not delete authoritative historical facts merely to reduce storage.

---

# 61. Deletion Strategy

The product must distinguish:

```text
account deactivation
account anonymization
account deletion
```

These are not automatically equivalent.

Historical records must not be blindly deleted through cascading foreign keys.

A future privacy policy must define which historical data is:

* deleted
* anonymized
* retained

---

# 62. Foreign Keys

Important relationships should use explicit foreign keys.

Examples:

```text
PlayerProfile.user_id → User.id

PlayerExternalIdentity.user_id → User.id

Puzzle.exercise_id → Exercise.id

QuestionInstance.session_id → TrainingSession.id

QuestionInstance.puzzle_id → Puzzle.id

TrainingAttempt.exercise_id → Exercise.id

TrainingAttempt.puzzle_id → Puzzle.id

TrainingAttempt.question_instance_id → QuestionInstance.id

RatingEvent.attempt_id → TrainingAttempt.id
```

Foreign-key columns should be indexed when query patterns justify it.

---

# 63. Uniqueness Constraints

Important invariants should be enforced by the database.

Examples:

```text
User.username

UserRole(user_id, role_id)

PlayerProfile.user_id

PlayerRating(user_id, exercise_id)

PlayerRating(guest_session_id, exercise_id)

PlayerAchievement(user_id, achievement_id)

PuzzleTagAssignment(puzzle_id, tag_id)
```

External identity uniqueness should normally use:

```text
(provider, external_id)
```

where provider identifiers are stable.

Database-specific nullable uniqueness behavior must be handled explicitly.

---

# 64. Indexing

Indexes must be based on actual access patterns.

Likely candidates include:

```text
User.username

TrainingAttempt.user_id
TrainingAttempt.guest_session_id
TrainingAttempt.exercise_id
TrainingAttempt.puzzle_id
TrainingAttempt.question_instance_id
TrainingAttempt.created_at

RatingEvent.user_id
RatingEvent.guest_session_id
RatingEvent.exercise_id
RatingEvent.created_at

XPEvent.user_id
XPEvent.guest_session_id
XPEvent.created_at

Puzzle.exercise_id
Puzzle.status
Puzzle.target_rating

AuditLog.actor_user_id
AuditLog.created_at
```

Composite indexes may be required for common queries such as:

```text
(user_id, exercise_id, created_at)
```

Do not index every field mechanically.

---

# 65. Soft Deletion

Soft deletion may be appropriate for:

* users
* exercises
* puzzles
* relationships
* support records

It is not mandatory for every table.

Historical facts such as attempts and rating events should generally remain immutable rather than soft-deleted.

---

# 66. Immutable Historical Records

The following should generally be append-only:

* training attempts
* rating events
* XP events
* achievement unlocks
* audit records
* content status transitions
* generator runs

Corrections should create explicit corrective records where practical rather than silently rewriting history.

---

# 67. Mutable Current State

The following may be mutable projections:

* current rating
* current XP total
* current level
* current streak
* current profile
* current content status
* current relationship status
* current mastery

Mutable state must remain consistent with authoritative historical facts where applicable.

---

# 68. Snapshot vs Reference

Historical records should snapshot values that can materially change over time.

Examples:

```text
TrainingAttempt
    ├── puzzle_id
    ├── difficulty_snapshot
    ├── exercise_version
    └── content_version
```

Do not depend solely on current:

```text
Puzzle.difficulty
ExerciseConfiguration
```

to interpret historical attempts.

This principle applies to:

* difficulty
* scoring configuration
* exercise configuration
* generator configuration
* important content metadata

---

# 69. JSON Usage

JSON is appropriate when:

* structure varies by exercise
* the data is configuration-oriented
* fields are not frequently queried
* schema versioning is needed
* the data is not itself a major business entity

Do not store the following exclusively in generic JSON:

* identity
* ownership
* attempts
* ratings
* achievements
* relationships
* permissions
* lifecycle state
* audit identity

These require relational structure.

---

# 70. JSON Schema Versioning

Persisted structured JSON should use:

```text
schema_version
```

when historical interpretation may matter.

Relevant examples:

* puzzle content
* exercise configuration
* generator configuration
* achievement criteria
* challenge criteria

The system must be able to interpret historical records after schema evolution.

---

# 71. SQLite / PostgreSQL Compatibility

The target model should remain compatible with:

```text
SQLite
PostgreSQL
```

Avoid relying on database-specific behavior unless the reason is documented.

When database behavior differs, prefer a portable strategy.

PostgreSQL-specific optimization should remain isolated to infrastructure when possible.

---

# 72. Migrations

All schema changes must use the project's migration system.

Migrations must:

* be deterministic
* preserve existing data
* support fresh databases
* support upgrades
* handle nullable/default transitions carefully
* avoid unnecessary destructive operations

Never manually modify production schema outside the migration workflow.

---

# 73. Data Migration Safety

When existing data must be transformed:

```text
Schema change
    ↓
Data migration/backfill
    ↓
Validation
    ↓
Application switch
```

Do not assume that adding a nullable field is sufficient for compatibility.

Guest-to-user ownership migration is a data migration operation, not merely an account update.

---

# 74. Authoritative Data Ownership

| Data                    | Owning domain           |
| ----------------------- | ----------------------- |
| User identity           | Identity                |
| Credentials             | Identity                |
| Roles                   | Identity                |
| Guest session           | Identity                |
| Player profile          | Player                  |
| External chess identity | Player                  |
| Exercise                | Content                 |
| Puzzle                  | Content                 |
| Training session        | Training                |
| Training attempt        | Training                |
| Question instance       | Training                |
| Rating state            | Ratings                 |
| Rating event            | Ratings                 |
| XP event                | Gamification            |
| Achievement             | Gamification            |
| Streak                  | Gamification            |
| Mastery                 | Training/Gamification   |
| Analytics projection    | Analytics               |
| Coach relationship      | Relationships           |
| Parent relationship     | Relationships           |
| Support ticket          | Support/Administration  |
| Audit record            | Administration/Security |

Analytics does not own authoritative training, rating, or gamification facts.

Administration may operate on another domain's data but does not automatically become its owner.

---

# 75. Core Relationship Map

```text
User
│
├── Roles
│
├── PlayerProfile
│   └── ExternalChessIdentities
│
├── TrainingSessions
│   └── QuestionInstances
│       └── TrainingAttempts
│           ├── RatingEvents
│           └── XPEvents
│
├── PlayerRatings
│   └── RatingEvents
│
├── GamificationState
│   ├── XPEvents
│   ├── Achievements
│   ├── Streaks
│   └── Mastery
│
├── Support
│
└── Relationships
```

For guests:

```text
GuestSession
├── TrainingSessions
├── TrainingAttempts
├── PlayerRatings
└── GamificationState
```

until migration.

---

# 76. Content Relationship Map

```text
Exercise
│
├── Puzzles
│   ├── Tags
│   ├── Validation
│   ├── Reviews
│   └── Status History
│
└── Generators
    └── Generator Runs
        └── Generated Puzzles
```

Only required branches are implemented in each phase.

---

# 77. Analytics Relationship Map

```text
Training Attempts
       │
       ├── Rating Events
       ├── Gamification Events
       │
       ▼
   Analytics
       │
       ├── Player statistics
       ├── Exercise statistics
       ├── Puzzle statistics
       └── Platform statistics
```

Analytics is downstream of authoritative data.

---

# 78. Data Model Invariants

The following invariants are mandatory where the corresponding entities exist.

### User

Every persistent user has a unique username.

### Profile

A user has at most one primary player profile.

### External Identity

Provider identifiers must follow the provider-specific uniqueness model.

### Guest Ownership

A guest-owned record references a valid guest session.

### Owner

Owner-bearing records have exactly one owner:

```text
user_id XOR guest_session_id
```

### Attempt

An attempt references a valid exercise.

### Question Instance

A question instance references a valid session and content.

### Puzzle

A puzzle belongs to a valid exercise.

### Rating

A player/guest has at most one current rating per rating scope.

### Rating History

Every authoritative rating change is traceable to a reason.

### Gamification

Reward events are traceable to legitimate sources where a source exists.

### Achievement

An unlock references a valid achievement definition.

### Content

Published content has passed required validation/review rules.

### Relationships

A user cannot be their own coach, student, parent, or child.

### Analytics

Analytics projections are never the sole source of truth.

---

# 79. Values That Must Never Become Client-Authoritative

The database/API boundary must not accept the following client values as authoritative:

```text
score
rating
rating_delta
XP
correctness
achievement eligibility
server time
session ownership
content lifecycle state
```

A stored client answer represents what was submitted.

It does not establish the result.

---

# 80. Historical Information Required for Future Analytics

The model should preserve enough information to answer future questions such as:

* Which exercises is a player weak at?
* Which puzzles are too easy?
* Which puzzles are too difficult?
* How does performance change over time?
* Which mistakes recur?
* Which practice patterns correlate with improvement?
* Which players stop training?
* Which content performs well?
* What should the player practice next?

The system does not need to answer all of these immediately.

It must avoid destroying the source data needed to answer them later.

---

# 81. Adaptive Training Readiness

The future adaptive-training system may require:

* historical performance
* exercise-level performance
* puzzle-level performance
* response time
* rating development
* mastery
* training frequency
* recurring mistakes

These are downstream consumers of authoritative history.

Do not create a separate adaptive-training database merely to prepare for future recommendations.

---

# 82. Minimum Foundation

The platform does not need every entity in this document at once.

The minimum foundation evolves by phase.

### Identity foundation

```text
User
Role
UserRole
GuestSession
```

### Player foundation

```text
PlayerProfile
PlayerExternalIdentity
```

### Existing training/content foundation

```text
Exercise
Puzzle
```

### Training foundation

```text
TrainingSession
QuestionInstance       # only where required
TrainingAttempt
```

### Rating foundation

```text
PlayerRating
RatingEvent
```

### Gamification foundation

```text
XPEvent
PlayerGamificationState
Achievement
PlayerAchievement
```

### Administration foundation

```text
AuditLog
SupportTicket
```

Later phases may add:

```text
GeneratorDefinition
GeneratorRun
ContentValidation
ContentReview
Relationships
Assignments
Analytics projections
Adaptive-training structures
```

The active phase determines what is actually implemented.

---

# 83. Phase Alignment

The data model follows the Master Plan.

## Phase 1

Foundation and safe schema/migration conventions.

## Phase 2

User, roles, sessions, guest identity, and account ownership.

## Phase 3

Player profile, external identities, player-facing progress support.

## Phase 4

Ratings and rating history.

## Phase 5

Gamification state and historical reward data.

## Phase 6

Administrative/audit/support foundations.

## Phase 7

Content lifecycle, puzzle management, validation, review, generators.

## Phase 8

Analytics projections and aggregates where justified.

## Phase 9

Coach/student and parent/student relationships and assignments.

## Phase 10

Adaptive-training-specific structures only where required.

This document does not authorize implementation of future-phase entities ahead of their phase.

---

# 84. Implementation Procedure

Before changing the data model, the implementation agent MUST:

1. inspect current SQLAlchemy models
2. inspect migrations
3. inspect seed/fixture data
4. inspect existing exercise persistence
5. inspect existing training persistence
6. identify equivalent existing entities
7. identify schema duplication
8. map existing structures to this logical model
9. determine the minimum missing change
10. implement only active-phase requirements
11. create migrations incrementally
12. verify existing data
13. verify fresh database creation
14. verify upgrade migration
15. verify relevant constraints
16. verify indexes against actual queries
17. verify guest ownership where applicable
18. run meaningful tests
19. preserve existing exercise behavior

The agent MUST NOT blindly create every conceptual table.

---

# 85. Schema Change Rules

Every schema change should answer:

1. Why is this required now?
2. Which active-phase requirement needs it?
3. Does an existing field/entity already solve it?
4. What existing data is affected?
5. What invariant should the database enforce?
6. What migration path is required?
7. What queries need indexes?
8. What historical behavior must remain unchanged?

If these questions cannot be answered from repository evidence and accepted specifications, do not invent the schema.

---

# 86. Final Data Model Principle

The database must make the important truths of MicroChess durable:

```text
Who is the player?

What did the player do?

Which question was actually delivered?

What was submitted?

What was the authoritative result?

What was the rating at that moment?

How did the rating change?

What reward/progress resulted?

Which content produced the result?

When did it happen?

Under which content/configuration version?
```

The target is not the largest possible schema.

The target is:

```text
Smallest coherent relational foundation
+
Strong historical integrity
+
Clear domain ownership
+
Safe migrations
+
Useful future analytical data
+
No unnecessary abstractions
```

Future capabilities must build on the same authoritative history rather than creating competing sources of truth.
