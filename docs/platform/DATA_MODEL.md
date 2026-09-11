# MicroChess Platform Data Model

## 1. Purpose

This document defines the target logical data model for the MicroChess platform.

It covers:

* identity and accounts
* guest sessions
* player profiles
* external chess identities
* exercises
* puzzles
* training sessions
* attempts
* ratings
* rating history
* XP and gamification
* achievements
* goals and streaks
* analytics
* content generation
* content lifecycle
* administration
* audit history
* support
* coach/student relationships
* parent/student relationships
* future adaptive-training data

This document defines the **logical target model**.

It does not require the current repository to already contain these tables or fields.

The implementation agent MUST inspect the existing database models and migrations before making changes.

Existing models are current-state evidence.

This document describes desired state.

---

# 2. Data Modeling Principles

The platform uses a relational data model.

The primary principles are:

1. Every important entity has a stable identifier.
2. Relationships use explicit foreign keys.
3. Important business invariants are enforced at the database level where practical.
4. Historical facts are preserved.
5. Current state may be derived from historical state, but critical current state may also be materialized for efficient reads.
6. Repeated business facts should not be duplicated unnecessarily.
7. JSON is allowed where the data is genuinely flexible or configuration-oriented.
8. JSON must not be used as an excuse to avoid modeling important relational entities.
9. Analytical aggregates and projections must not replace authoritative raw training history.
10. Soft deletion is preferred for important historical entities where deletion would destroy useful history.
11. Cascading deletes must be used carefully.
12. Schema design must remain compatible with SQLite development and PostgreSQL production.
13. Indexes must follow actual query patterns.
14. Denormalization is allowed only when there is a measured or clearly justified reason.
15. Data ownership must remain aligned with the domain ownership defined in `ARCHITECTURE.md`.

Relational normalization exists primarily to reduce redundancy and protect data integrity. The platform should generally begin with a normalized transactional model and introduce deliberate denormalization only where useful.

---

# 3. Identifier Strategy

Every major entity should have a surrogate primary key.

Preferred conceptual form:

```text
id
```

The exact SQLAlchemy type must follow the existing project convention.

Do not introduce UUIDs, ULIDs, integer IDs, or another identifier strategy without first inspecting the existing repository.

External identifiers must remain separate from internal primary keys.

Example:

```text
PlayerProfile.id
PlayerExternalIdentity.external_id
```

An external identifier is NOT an internal primary key.

---

# 4. Common Metadata

Important entities should generally support:

```text
created_at
updated_at
```

Entities that require lifecycle state may additionally use:

```text
status
published_at
archived_at
deleted_at
```

Do not add timestamps to every table mechanically.

Use timestamps when they represent meaningful business or lifecycle information.

---

# 5. Identity Domain

## 5.1 User

Represents the persistent application identity.

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

Registration initially requires only:

```text
username
password
```

The database MUST enforce username uniqueness.

The following are NOT required at registration:

* email
* phone
* real name
* FIDE ID
* Lichess username
* Chess.com username

Those belong to later profile completion.

---

# 6. User Status

Possible conceptual statuses:

```text
active
suspended
disabled
deleted
```

The exact enum representation should follow project conventions.

Suspension or disablement must not destroy historical training data.

---

# 7. Roles

Roles should be modeled independently from the user record.

Canonical persisted roles are:

```text
PLAYER
COACH
PARENT
ADMIN
```

Guest is NOT a persisted role.

Conceptually:

```text
Role
----
id
code
name
```

Relationship:

```text
User
  │
  └── UserRole
         │
         └── Role
```

This allows future multi-role users.

Example:

```text
PLAYER + COACH
```

without changing the user schema.

---

# 8. UserRole

Conceptual fields:

```text
UserRole
--------
id
user_id
role_id
created_at
```

Recommended uniqueness:

```text
(user_id, role_id)
```

A user must not receive the same role twice.

---

# 9. Permissions

If explicit permission modeling is required:

```text
Permission
----------
id
code
description
```

And:

```text
RolePermission
--------------
id
role_id
permission_id
```

However, do not create a large permission-management UI unless the authorization requirements justify it.

The initial implementation may use application-defined permission mappings.

The architectural boundary must still allow explicit permissions later.

Permission codes should follow the canonical capability vocabulary defined in `SECURITY.md`.

---

# 10. Guest Sessions

Guests need a persistent temporary identity.

Conceptually:

```text
GuestSession
------------
id
token_identifier
created_at
last_seen_at
expires_at
status
```

The actual secret/token MUST NOT be stored in plaintext if the security model permits hashing.

A guest session may own temporary training state.

Guest is an access subject, not a persisted application role.

---

# 11. Guest-Owned Data

Guest activity may reference:

```text
guest_session_id
```

instead of:

```text
user_id
```

For a persistent player:

```text
user_id
```

is used.

For a guest:

```text
guest_session_id
```

is used.

For owner-bearing historical records, the model should enforce that exactly one owner is present:

```text
user_id XOR guest_session_id
```

where practical.

Avoid an unconstrained:

```text
owner_type
owner_id
```

pair when database referential integrity would be lost.

Prefer explicit nullable foreign keys or a dedicated owner abstraction where justified.

---

# 12. Guest Migration

Guest-to-account migration is a critical data operation.

Conceptually:

```text
GuestSession
     │
     ├── Training data
     ├── Rating data
     ├── Gamification data
     └── Progress data
              │
              ▼
        Migration Operation
              │
              ▼
             User
```

Migration must be:

* explicit
* authenticated where required
* atomic where practical
* idempotent
* replay-resistant
* auditable

The system must prevent:

* duplicate attempts
* duplicate XP
* duplicate achievements
* duplicate rating events
* cross-account migration

A migration record may be useful:

```text
GuestMigration
--------------
id
guest_session_id
user_id
started_at
completed_at
status
```

Guest-owned ratings and gamification state are temporary and may be transferred during migration.

Migration must preserve historical facts while changing ownership from the guest session to the authenticated user.

---

# 13. Player Profile

The persistent application identity and player profile are conceptually separate.

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

Not every field must be implemented immediately.

Personal information should be optional.

Sensitive personal data must be minimized.

A persistent player has at most one primary `PlayerProfile`.

---

# 14. External Chess Identities

External chess identity belongs to the player profile domain.

Conceptually:

```text
PlayerExternalIdentity
----------------------
id
player_profile_id
provider
username
external_id
rating
rating_type
is_verified
verified_at
created_at
updated_at
```

Possible providers:

```text
fide
lichess
chess_com
```

Possible rating types:

```text
standard
rapid
blitz
bullet
classical
```

depending on the provider.

The schema must not assume every provider supports every rating type.

---

# 15. External Rating Rules

External ratings are:

* self-reported initially
* unverified unless explicitly verified
* separate from MicroChess ratings
* timestamped when historical tracking is needed

Example:

```text
Lichess Rapid: 2050
MicroChess Pin: 1478
```

These values must never be treated as the same rating system.

Where provider-specific external IDs exist, provider-scoped uniqueness should be enforced where appropriate:

```text
UNIQUE(provider, external_id)
```

The exact constraint must account for providers that do not expose a stable external ID.

---

# 16. Exercise

The platform already has an exercise catalog.

Conceptually:

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

The exact current exercise model MUST be inspected before adding duplicate fields.

---

# 17. Exercise Configuration

Exercise-specific configuration may require flexible data.

Conceptually:

```text
ExerciseConfiguration
---------------------
exercise_id
config_json
version
updated_at
```

JSON is appropriate for configuration where the structure genuinely varies between exercises.

Examples:

* time limit
* scoring configuration
* selection count
* mode-specific settings
* exercise-specific parameters

Business-critical historical facts must NOT be stored only inside this JSON.

When persisted configuration affects historical interpretation, the relevant configuration or version must be snapshotted on the historical record.

---

# 18. Puzzle

A puzzle is a piece of exercise content.

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

Exercise-specific content may be represented through structured fields or a validated content payload.

Do not force every exercise into a fake universal puzzle schema.

---

# 19. Puzzle Content

Where puzzle structure varies significantly by exercise, a structured JSON payload may be appropriate:

```text
PuzzleContent
-------------
puzzle_id
content_json
schema_version
```

However, fields required for:

* searching
* filtering
* analytics
* uniqueness
* validation
* authorization
* reporting

should be modeled relationally when practical.

The large existing `puzzles.db` dataset remains a separate read-only content source unless an explicit migration/import requirement is approved.

---

# 20. Puzzle Lifecycle

Recommended states:

```text
draft
generated
validated
reviewed
approved
published
active
retired
```

Not every state requires a separate database table.

The current state may live on `Puzzle`.

Historical transitions should be captured separately when auditability matters.

---

# 21. Puzzle Status History

Conceptual:

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

This provides historical content lifecycle information.

---

# 22. Puzzle Tags

Tags should be normalized if they are used for filtering and analytics.

```text
PuzzleTag
---------
id
code
name
```

Relationship:

```text
PuzzleTagAssignment
-------------------
id
puzzle_id
tag_id
```

Recommended uniqueness:

```text
(puzzle_id, tag_id)
```

---

# 23. Training Session

A session represents a bounded period of exercise activity.

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

For owner-bearing sessions, exactly one of:

```text
user_id
guest_session_id
```

must be populated.

Depending on the exercise, a session may be optional.

Do not force every historical attempt to belong to a formal session if the product does not require it.

---

# 24. Attempt

Attempt is one of the most important historical entities.

Conceptual fields:

```text
TrainingAttempt
---------------
id
user_id
guest_session_id
session_id
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
created_at
```

For persistent historical ownership, exactly one of:

```text
user_id
guest_session_id
```

must be populated.

This record represents what happened at the time of the attempt.

---

# 25. Historical Snapshot Principle

Historical records should preserve relevant values as they were at the time.

For example:

```text
difficulty_snapshot
rating_before
rating_delta
rating_after
```

must not be reconstructed solely from today's state.

If a puzzle changes difficulty later, old attempts must still retain the historical context needed for analysis.

If scoring or exercise configuration materially affects interpretation, the relevant version or snapshot should also be retained.

---

# 26. Answer Data

Depending on exercise type, an attempt may need an answer payload.

Conceptually:

```text
AttemptAnswer
-------------
attempt_id
answer_json
```

The answer should be stored only if it provides meaningful historical or debugging value.

Do not store unnecessary sensitive or huge payloads.

For chess answers, store a canonical representation where practical.

Examples:

```text
square
move
piece selection
ordered selection
SAN/UCI where appropriate
```

The client-submitted answer must never become authoritative merely because it is stored.

---

# 27. Attempt Result

An attempt may contain:

```text
is_correct
score
feedback_code
```

The exact scoring result is produced by the server.

Client-provided values are ignored for authoritative calculations.

---

# 28. Rating Account

Each persistent player or guest session may have multiple rating states.

Conceptually:

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

Exactly one owner must be present:

```text
user_id XOR guest_session_id
```

For persistent players:

```text
user_id + exercise_id
```

identifies a current rating.

For guests:

```text
guest_session_id + exercise_id
```

identifies a temporary current rating.

Guest ratings are temporary and become persistent only through guest-to-account migration.

If rating categories eventually extend beyond individual exercises, use a stable rating scope abstraction.

Example:

```text
rating_scope_type
rating_scope_id
```

may be introduced later.

Do not over-generalize the first implementation without need.

---

# 29. Rating History

Every authoritative rating change should produce historical data.

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

Exactly one owner must be present:

```text
user_id XOR guest_session_id
```

Possible reasons:

```text
attempt
initialization
manual_adjustment
migration
calibration
```

Manual adjustment must be heavily controlled and audited if ever implemented.

---

# 30. Rating Invariants

For a normal attempt:

```text
rating_after = rating_before + rating_delta
```

The exact algorithm is defined in `RATINGS.md`.

The database should not attempt to reproduce the algorithm.

The application/domain layer is authoritative.

Rating updates and the corresponding rating event must be persisted atomically with the authoritative attempt result.

---

# 31. Rating Independence

Never create a single:

```text
User.rating
```

field as the canonical training rating.

Ratings belong to defined scopes.

At minimum, for persistent players:

```text
user_id + exercise_id
```

must identify a rating.

For guests:

```text
guest_session_id + exercise_id
```

must identify a temporary rating.

External chess ratings remain completely separate.

---

# 32. XP Ledger

XP should be modeled as historical records rather than only one mutable total.

Conceptually:

```text
XPEvent
-------
id
user_id
guest_session_id
source_attempt_id
source_achievement_id
source_goal_id
source_challenge_id
amount
reason
created_at
```

Exactly one owner must be present:

```text
user_id XOR guest_session_id
```

Use explicit nullable foreign keys for known source types where practical.

Do NOT introduce an unconstrained generic:

```text
source_type
source_id
```

pair merely for convenience.

If a genuinely open-ended source is introduced later and explicit foreign keys are impractical, that decision must be documented and must not silently replace referentially safe relationships.

Examples of XP reasons:

```text
attempt_completed
exercise_completed
achievement
daily_goal
streak
challenge
```

---

# 33. Player XP State

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

Exactly one owner must be present.

The XP ledger remains the historical source.

The materialized total is a performance/read optimization.

For guests, this state is temporary and migratable.

---

# 34. Levels

Level thresholds should not be duplicated into every user row.

Conceptually:

```text
LevelDefinition
---------------
id
level
required_xp
title_key
```

If level definitions are simple application configuration, a database table may not be necessary initially.

The architecture must permit configuration later.

---

# 35. Streaks

Conceptual:

```text
PlayerStreak
------------
id
user_id
guest_session_id
current_streak
longest_streak
last_activity_date
updated_at
```

Exactly one owner must be present.

If streak history becomes analytically important, maintain historical records as well.

Do not rely exclusively on current streak state.

---

# 36. Daily / Weekly Goals

Goals may be configurable.

Conceptually:

```text
GoalDefinition
-------------
id
code
period
target_type
target_value
active
```

Player progress:

```text
PlayerGoalProgress
------------------
id
user_id
guest_session_id
goal_id
period_start
period_end
current_value
completed_at
```

Exactly one owner must be present.

This allows goals to change without destroying historical progress.

---

# 37. Achievements

Achievement definitions:

```text
Achievement
-----------
id
code
title_key
description_key
category
criteria_json
active
```

Player unlock:

```text
PlayerAchievement
-----------------
id
user_id
guest_session_id
achievement_id
unlocked_at
metadata_json
```

Exactly one owner must be present.

Uniqueness:

```text
(owner, achievement_id)
```

unless repeatable achievements are explicitly supported.

The exact relational constraint may follow the implementation strategy chosen for user/guest ownership.

---

# 38. Personal Records

The system may track records such as:

* highest exercise rating
* longest streak
* fastest correct answer
* highest session score
* best accuracy over a minimum sample
* most exercises completed

Conceptually:

```text
PlayerRecord
------------
id
user_id
guest_session_id
record_type
exercise_id
value
occurred_at
source_id
```

Exactly one owner must be present.

Records must have clear minimum-sample requirements where appropriate.

Do not allow trivial one-attempt results to become misleading permanent records.

---

# 39. Challenges

Future challenges may be represented as:

```text
Challenge
---------
id
code
title_key
description_key
start_at
end_at
criteria_json
reward_json
status
```

Participation:

```text
ChallengeParticipation
----------------------
id
challenge_id
user_id
guest_session_id
progress
completed_at
```

Exactly one owner must be present.

Challenges should not require a separate game engine.

---

# 40. Leaderboards

Leaderboards should generally be derived from authoritative state.

Possible dimensions:

* exercise rating
* XP
* streak
* achievement score
* challenge score

The system should distinguish:

```text
global leaderboard
exercise leaderboard
time-bounded leaderboard
```

Do not store every leaderboard position permanently unless required for historical leaderboard reporting.

Guest users should not appear in persistent public leaderboards unless explicitly supported by product policy.

---

# 41. Analytics

Analytics is a **derived/read-oriented domain**.

It does not own raw training facts.

Authoritative source data remains owned by the relevant domains:

```text
Training
Ratings
Gamification
Content
```

Analytics should normally derive metrics from those authoritative records.

A separate analytics fact table may be introduced only when a demonstrated performance, query-shape, or aggregation requirement justifies it.

If such a projection is introduced, it must remain rebuildable from authoritative source data.

Conceptually, a derived fact may contain:

```text
TrainingAnalyticsFact
---------------------
id
user_id
exercise_id
puzzle_id
session_id
attempt_id
mode
event_type
is_correct
score
response_time_ms
rating_before
rating_delta
rating_after
xp
difficulty
occurred_at
```

This is a projection, not a second source of truth.

Do not duplicate the entire training dataset without a demonstrated analytical requirement.

---

# 42. Analytics Aggregates

Possible aggregate structures:

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
active
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

These are derived data.

They must never become the only source of truth.

They must be rebuildable or recalculable from authoritative historical data where practical.

---

# 43. Period Comparison

Analytics must support comparisons such as:

```text
Last 7 days
vs
Previous 7 days
```

and:

```text
Last 30 days
vs
Previous 30 days
```

This does not require storing every possible comparison.

Store timestamped authoritative facts and calculate comparisons from them or from rebuildable aggregates.

---

# 44. Content Generator

Generator definitions:

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

A generator is a registered capability, not merely a script file.

---

# 45. Generator Run

Every meaningful generation operation should be traceable.

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

The configuration snapshot is important because generator configuration may change later.

Generator runs are historical operational records and should not be silently rewritten.

---

# 46. Generated Content Link

Generated puzzles should be traceable to their generation source.

Possible fields on `Puzzle`:

```text
generator_run_id
generation_source
```

or a separate relation:

```text
GeneratedPuzzle
---------------
id
generator_run_id
puzzle_id
created_at
```

Use whichever structure best fits the existing content model.

Do not create both unless there is a concrete requirement.

---

# 47. Content Validation

Validation results may be stored:

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

This supports reproducibility.

A puzzle that was valid under validator version 1 may need revalidation after validator version 2.

---

# 48. Content Review

Human review may be represented as:

```text
ContentReview
-------------
id
puzzle_id
reviewer_user_id
decision
notes
created_at
```

Possible decisions:

```text
approved
rejected
needs_changes
```

---

# 49. Admin Audit Log

Conceptual:

```text
AuditLog
--------
id
actor_user_id
action
resource_type
resource_id
before_json
after_json
metadata_json
created_at
```

Do not store secrets in audit snapshots.

For sensitive data, record that a change occurred without copying the sensitive value.

Audit records are historical records and should be append-only.

---

# 50. Support

Support requests:

```text
SupportTicket
-------------
id
user_id
guest_session_id
subject
status
priority
created_at
updated_at
closed_at
```

For owner-bearing tickets, exactly one of:

```text
user_id
guest_session_id
```

must be populated.

Messages:

```text
SupportMessage
--------------
id
ticket_id
author_user_id
author_type
message
created_at
```

The guest flow should permit support without forcing account creation.

---

# 51. Coach / Student

The relationship should be explicit.

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

Possible statuses should follow the canonical relationship lifecycle defined in `COACH_STUDENT.md`.

A user must not be their own student.

Uniqueness and status rules must prevent duplicate active relationships.

---

# 52. Coach Groups

Future groups/classes:

```text
CoachGroup
----------
id
coach_user_id
name
description
created_at
updated_at
```

Membership:

```text
CoachGroupMember
----------------
id
group_id
student_user_id
joined_at
left_at
```

Historical membership should remain available when needed for assignment and reporting history.

---

# 53. Assignments

Future coach assignments:

```text
TrainingAssignment
------------------
id
coach_user_id
exercise_id
student_user_id
group_id
title
instructions
start_at
due_at
target_config_json
status
created_at
```

The system should allow assignment to either:

* individual student
* group

but not require both.

The invariant must be enforced by the application/domain layer and, where practical, database constraints.

---

# 54. Coach Notes

```text
CoachNote
---------
id
coach_user_id
student_user_id
content
created_at
updated_at
```

Visibility must be strictly controlled.

Notes are private coach data unless explicitly shared.

---

# 55. Parent / Child Relationship

Conceptually:

```text
ParentStudentRelationship
-------------------------
id
parent_user_id
student_user_id
status
created_at
accepted_at
ended_at
```

Parents should only access data permitted by the relationship and privacy policy.

A user must not be their own parent or child.

---

# 56. Parent Permissions

A parent relationship may eventually have explicit scopes:

```text
view_progress
view_analytics
view_assignments
view_achievements
receive_notifications
```

Do not assume that a parent automatically receives unrestricted access to all student data.

The exact capability and consent model belongs to `PARENT_STUDENT.md` and `SECURITY.md`.

---

# 57. Privacy Settings

Privacy should be represented explicitly where needed.

Conceptually:

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

Exact settings belong in the security/privacy specification.

---

# 58. Notification Infrastructure

Notifications are future infrastructure and are NOT part of the minimum platform data model.

Conceptually:

```text
Notification
------------
id
user_id
type
title_key
body_key
payload_json
read_at
created_at
```

Channels may later include:

```text
in_app
email
telegram
bale
push
```

Do not implement every channel immediately.

Notification infrastructure must not be introduced merely because this logical model mentions it.

---

# 59. Data Retention

Not all data has the same retention requirements.

### Long-lived

* account
* player profile
* ratings
* rating history
* achievements
* important training history
* content lifecycle
* audit records

### Potentially temporary

* expired guest sessions
* transient job state
* temporary upload metadata
* disposable caches

Retention rules must be explicit.

Do not automatically delete historical training facts merely to reduce database size.

---

# 60. Deletion Strategy

Deleting a player must not blindly cascade through all historical data.

The system should distinguish:

```text
account deactivation
account anonymization
account deletion
```

A later privacy policy must define which is used.

Historical analytics may require anonymization rather than destructive deletion.

Historical training, rating, XP, and audit records must not be destroyed through an accidental cascade.

---

# 61. Foreign Keys and Integrity

Foreign keys should enforce important relationships.

Examples:

```text
TrainingAttempt.exercise_id → Exercise.id
TrainingAttempt.puzzle_id → Puzzle.id
RatingEvent.attempt_id → TrainingAttempt.id
PlayerProfile.user_id → User.id
PlayerAchievement.achievement_id → Achievement.id
```

Owner-bearing records should use explicit foreign keys rather than unconstrained polymorphic identifiers where practical.

Foreign-key columns that are commonly used in joins should be indexed when query patterns justify it.

---

# 62. Unique Constraints

Important uniqueness rules should be enforced in the database.

Examples:

```text
User.username

UserRole(user_id, role_id)

PlayerProfile.user_id

PlayerExternalIdentity(player_id, provider)

PlayerRating(user_id, exercise_id)

PlayerAchievement(user_id, achievement_id)

PuzzleTagAssignment(puzzle_id, tag_id)
```

For guest-aware entities, uniqueness must be scoped to the appropriate owner:

```text
(user_id, exercise_id)
(guest_session_id, exercise_id)
```

Application-level checks alone are insufficient for important uniqueness invariants.

Where nullable owner columns are used, the implementation must account for database-specific NULL uniqueness behavior and use an appropriate constraint/index strategy.

---

# 63. Indexing Principles

Indexes should support actual access patterns.

Likely candidates include:

```text
User.username

TrainingAttempt.user_id
TrainingAttempt.guest_session_id
TrainingAttempt.exercise_id
TrainingAttempt.puzzle_id
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

Do not create indexes for every column.

Index design must be validated against actual query patterns and database behavior.

---

# 64. Soft Deletion

Soft deletion may be appropriate for:

* users
* puzzles
* exercises
* relationships
* support tickets

But it must not become automatic for every table.

Historical immutable facts such as completed attempts should generally not be deleted merely because a related content object is retired.

---

# 65. Immutable Historical Records

The following should generally be treated as append-only historical facts:

* training attempts
* rating events
* XP events
* achievement unlock records
* audit records
* content status transitions
* generator runs

Corrections should create explicit corrective records where practical rather than silently rewriting history.

---

# 66. Mutable Current State

The following may be mutable projections/state:

* current rating
* current XP total
* current level
* current streak
* current profile
* current puzzle status
* current relationship status

These values must remain consistent with their underlying historical facts where historical records exist.

---

# 67. Snapshot vs Reference

Historical records should store snapshots when the referenced value can change.

For example:

```text
Attempt
  ├── puzzle_id
  └── difficulty_snapshot
```

rather than assuming:

```text
Puzzle.difficulty
```

will always remain unchanged.

This principle applies to:

* difficulty
* rating
* scoring configuration
* generator configuration
* important exercise configuration

---

# 68. Configuration Data

Configuration may be stored in JSON when:

* structure varies by exercise
* schema versioning is needed
* fields are not commonly queried
* configuration is not itself a primary business entity

Do NOT put these exclusively in JSON:

* user identity
* attempts
* ratings
* achievements
* relationships
* permissions
* content lifecycle
* audit identity

These require relational structure.

---

# 69. JSON Schema Versioning

Whenever JSON is used for persisted structured data, consider:

```text
schema_version
```

This is particularly important for:

* puzzle content
* generator configuration
* exercise configuration
* achievement criteria
* challenge criteria
* derived analytics payloads

Future readers must be able to interpret historical records.

---

# 70. Database Compatibility

The model should work with:

* SQLite during development/testing
* PostgreSQL in production

Avoid relying on database-specific behavior unless explicitly documented.

If a PostgreSQL-specific optimization is eventually required, isolate it in infrastructure and document the reason.

When SQLite and PostgreSQL differ in constraint behavior, the implementation must choose a portable strategy or explicitly document the production-specific behavior.

---

# 71. Migrations

All schema changes must use the project's migration system.

Never manually modify production tables without a migration.

Every migration should:

* be deterministic
* preserve existing data
* handle nullable/default transitions carefully
* be tested against realistic data
* avoid unnecessary destructive operations

---

# 72. Data Migration Safety

For changes involving existing records:

```text
Schema migration
       ↓
Data backfill if needed
       ↓
Validation
       ↓
Application switch
```

Do not assume a new nullable column automatically solves historical compatibility.

Guest-to-user migration must be treated as a data migration operation, not merely an account update.

---

# 73. Core Relationship Map

The conceptual core is:

```text
User
 │
 ├── PlayerProfile
 │       └── ExternalIdentities
 │
 ├── Roles
 │
 ├── GuestMigration history
 │
 ├── TrainingSessions
 │       └── TrainingAttempts
 │               ├── Exercise
 │               ├── Puzzle
 │               ├── RatingEvent
 │               └── XPEvent
 │
 ├── PlayerRatings
 │       └── RatingEvents
 │
 ├── GamificationState
 │       ├── XPEvents
 │       ├── Achievements
 │       ├── Streaks
 │       ├── Goals
 │       └── Records
 │
 ├── SupportTickets
 │
 ├── Coach/Parent relationships
 │
 └── Audit participation
```

For guests, temporary training, rating, and gamification records are owned by `GuestSession` until migration.

---

# 74. Content Relationship Map

```text
Exercise
   │
   ├── Puzzles
   │      │
   │      ├── Tags
   │      ├── Validation
   │      ├── Reviews
   │      └── Status History
   │
   └── Generators
          │
          └── Generator Runs
                  │
                  └── Generated Puzzles
```

---

# 75. Analytics Relationship Map

```text
Training
   │
   ├── TrainingAttempt
   │
   ├── RatingEvent
   │
   └── Gamification records
             │
             ▼
        Analytics
             │
             ├── Player statistics
             ├── Exercise statistics
             ├── Puzzle statistics
             └── Platform statistics
```

Analytics remains downstream of authoritative domain data.

Analytics projections and aggregates are derived and rebuildable where practical.

---

# 76. Data Ownership Matrix

| Data                             | Owner                   |
| -------------------------------- | ----------------------- |
| User identity                    | Identity                |
| Credentials                      | Identity                |
| Roles                            | Identity                |
| Player profile                   | Player                  |
| External chess identity          | Player                  |
| Exercise                         | Content                 |
| Puzzle                           | Content                 |
| Generator                        | Content                 |
| Training session                 | Training                |
| Training attempt                 | Training                |
| Rating state                     | Ratings                 |
| Rating event                     | Ratings                 |
| XP event                         | Gamification            |
| Achievement                      | Gamification            |
| Streak                           | Gamification            |
| Goals                            | Gamification            |
| Analytics projections/aggregates | Analytics               |
| Coach relationship               | Relationships           |
| Parent relationship              | Relationships           |
| Support ticket                   | Support                 |
| Audit log                        | Administration/Security |

Analytics does NOT own authoritative training, rating, or gamification facts.

---

# 77. Data Model Invariants

The following must hold.

### User identity

Every persistent user has a unique username.

### Player profile

A persistent player has at most one primary player profile.

### External identity

A provider identity must not be ambiguously attached to multiple players where provider uniqueness rules prohibit it.

### Rating

A player or guest session has at most one current rating state per rating scope.

### Rating history

Every authoritative rating change is traceable to a reason.

### Attempt

Every persistent attempt belongs to exactly one owner:

* a user
* or a guest session

and never both.

### Attempt integrity

An attempt belongs to a valid exercise.

### Puzzle integrity

A puzzle belongs to a valid exercise.

### Gamification

XP is traceable to a valid source where a source relationship exists.

### Achievement

An achievement unlock is traceable to an achievement definition.

### Content

Published content must have passed the required validation/review rules.

### Relationships

A user cannot be their own coach/student or parent/child.

### Guest ownership

Guest-owned temporary state must reference a valid active or historically valid guest session.

### Analytics

Analytics projections are never the sole source of truth for training, rating, or gamification facts.

---

# 78. What Must Not Be Stored as Authoritative State

The following client-provided values must never be accepted as authoritative:

```text
score
rating
rating_delta
XP
achievement eligibility
correctness
puzzle solution
server time
```

The server calculates them.

Stored client answers are evidence of what was submitted, not authoritative results.

---

# 79. What Must Be Preserved for Future Intelligence

The data model must preserve enough information to eventually answer:

* Which exercises is this player weak at?
* Which puzzles are too easy?
* Which puzzles are too difficult?
* Which exercises improve after practice?
* What is the player's observed difficulty level?
* Which mistakes recur?
* What training patterns correlate with improvement?
* Which players stop training?
* Which exercises retain users?
* What should this player practice next?
* How effective are recommendations?
* How does performance change over time?

The system does not need to answer all of these immediately.

It must avoid destroying the data needed to answer them later.

---

# 80. Minimum Viable Data Model

The first platform implementation does NOT need every table in this document.

The minimum coherent foundation should include:

```text
User
Role / UserRole
GuestSession
PlayerProfile
PlayerExternalIdentity

Exercise
Puzzle

TrainingSession
TrainingAttempt

PlayerRating
RatingEvent

XPEvent
PlayerGamificationState
Achievement
PlayerAchievement

SupportTicket
AuditLog
```

Guest ownership support must be included in the relevant entities where guest training is part of the implemented scope.

Additional entities may be introduced in later phases.

Notification infrastructure, challenges, coach groups, assignments, parent permissions, and adaptive-training-specific structures do not need to be implemented in the initial foundation unless their phase explicitly requires them.

---

# 81. Implementation Rule

Before implementing this model:

1. Inspect existing SQLAlchemy models.
2. Inspect existing migrations.
3. Inspect existing seed scripts.
4. Identify current `User`, player, puzzle, exercise and training structures.
5. Map existing tables to this logical model.
6. Identify duplication.
7. Identify fields that already satisfy these requirements.
8. Reuse existing structures where correct.
9. Add only missing capabilities.
10. Preserve existing exercise behavior.
11. Create migrations incrementally.
12. Test migration paths against realistic existing data.
13. Verify Guest ownership and migration paths explicitly.
14. Verify database constraints and indexes against actual query patterns.

Do NOT blindly create every table listed in this document.

---

# 82. Final Data Model Principle

The database must make the important truths of MicroChess durable.

The most important truths are:

```text
Who is the player?
What did the player do?
What was the result?
What was the player's rating at that moment?
How did the rating change?
What progress/reward resulted?
Which content produced the result?
When did it happen?
What was the content's state at that time?
```

If the platform can reliably preserve these facts, the future player dashboard, analytics, gamification, administration, coach/parent systems and adaptive training can all be built on top of the same historical foundation.

The model should remain the **smallest coherent relational foundation that preserves these truths without introducing unnecessary abstractions or duplicate sources of truth**.
