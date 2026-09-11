# MicroChess Platform API Contracts

## 1. Purpose

This document defines the target API contract for the MicroChess platform.

It covers:

* API conventions
* authentication and sessions
* guest access and guest migration
* player profiles
* exercises and training
* attempts and sessions
* ratings
* gamification
* analytics
* content and puzzles
* generators
* administration
* support
* coach/student relationships
* parent/student relationships
* pagination, filtering, and sorting
* errors
* authorization
* idempotency
* server authority
* API versioning

This document defines the **target API contract**.

It does not assume that every endpoint currently exists.

Before implementation, the agent MUST inspect:

* existing API routes
* existing Pydantic schemas
* existing application/services
* existing authentication/session implementation
* existing frontend API client
* existing exercise-specific API contracts

Existing working behavior must be preserved unless an intentional change is explicitly documented and tested.

---

# 2. API Design Principles

The API MUST be:

* predictable
* explicit
* versionable
* secure
* typed
* consistent
* server-authoritative
* suitable for guest and authenticated users
* suitable for the React frontend
* extensible for future clients

The API should use standard HTTP semantics.

HTTP methods describe request intent, while HTTP status codes communicate the result class.

FastAPI can expose these contracts directly through OpenAPI, so implemented response models and status codes should remain synchronized with the documented contract.

---

# 3. API Base Path

The preferred target API prefix is:

```text
/api/v1
```

Examples:

```text
/api/v1/auth/register
/api/v1/auth/login
/api/v1/me
/api/v1/exercises
/api/v1/training/attempts
```

The exact prefix MUST be reconciled with the existing repository before implementation.

Do not introduce a second competing API prefix.

---

# 4. Versioning

The public API is versioned.

Initial target:

```text
v1
```

Breaking changes require either:

* a new API version, or
* an explicitly documented migration strategy that preserves existing clients.

Examples of breaking changes:

* removing a response field
* changing the meaning of an existing field
* changing authentication semantics
* changing required request fields
* changing the meaning of an endpoint
* changing an existing field's type incompatibly

Non-breaking additions may generally remain within the same API version.

---

# 5. HTTP Methods

Use HTTP methods according to their intended semantics.

Typical mapping:

```text
GET     Read
POST    Create / submit / perform an action
PUT     Replace
PATCH   Partial update
DELETE  Delete / deactivate
```

Not every business action needs to be represented as a generic CRUD update.

Action endpoints are acceptable when the operation is genuinely an action.

For example:

```http
POST /api/v1/training/attempts
```

is preferable to pretending that answer submission is simply a generic database update.

---

# 6. Identity, Authentication, and Authorization

The API distinguishes between:

### Authenticated identities

```text
PLAYER
COACH
PARENT
ADMIN
```

These are the canonical persisted roles.

### Guest access

Guest is **not a persisted role**.

A guest is a temporary unauthenticated training identity/session with a limited capability set.

Authentication answers:

> Who is making the request?

Authorization answers:

> Is this identity allowed to perform this operation on this resource?

Object-level authorization additionally answers:

> Is this particular resource within the caller's allowed scope?

The API MUST enforce all three where applicable.

---

# 7. Authentication Endpoints

## 7.1 Register

```http
POST /api/v1/auth/register
```

Request:

```json
{
  "username": "player123",
  "password": "..."
}
```

Initial registration requires only:

* username
* password

The following are NOT required for initial registration:

* email
* phone
* real name
* FIDE identity
* Lichess identity
* Chess.com identity

The response establishes an authenticated account/session according to the actual authentication architecture.

Example:

```json
{
  "user": {
    "id": "...",
    "username": "player123"
  },
  "session": {
    "authenticated": true
  }
}
```

The exact session representation is implementation-dependent.

---

# 8. Login

```http
POST /api/v1/auth/login
```

Request:

```json
{
  "username": "player123",
  "password": "..."
}
```

Successful login establishes the authenticated session.

Invalid credentials MUST NOT reveal whether:

* the username exists
* the password was almost correct
* another account has related information

Authentication failure responses must follow the security policy.

---

# 9. Logout

```http
POST /api/v1/auth/logout
```

Successful logout:

```http
204 No Content
```

Logout invalidates the current authenticated session or equivalent credential.

---

# 10. Current User

```http
GET /api/v1/me
```

Example:

```json
{
  "user": {
    "id": "...",
    "username": "...",
    "roles": ["player"]
  },
  "profile": {
    "display_name": "...",
    "avatar": null
  }
}
```

The response MUST NOT expose private information the caller is not authorized to see.

Roles returned by this endpoint are persisted roles only.

A guest MUST NOT appear as a `guest` role.

---

# 11. Guest Session

Guests may use training without creating an account.

Target endpoint:

```http
POST /api/v1/guest/session
```

Response:

```json
{
  "guest_session": {
    "expires_at": "..."
  }
}
```

The server establishes the guest credential through the selected session mechanism.

The client MUST NOT receive internal database identifiers or secrets unless explicitly required by the protocol.

Guest credentials MUST be treated as untrusted bearer/session credentials and protected according to the security architecture.

---

# 12. Guest Session State

```http
GET /api/v1/guest/session
```

Returns the current guest state when a valid guest session exists.

Example:

```json
{
  "authenticated": false,
  "guest": true,
  "session": {
    "expires_at": "..."
  }
}
```

An absent or expired guest session should not expose information about another guest.

---

# 13. Guest Migration

Guest training data may be migrated into an authenticated account.

Target endpoint:

```http
POST /api/v1/guest/migrate
```

The request should contain only the minimum information necessary to identify the guest session under the actual transport mechanism.

If the guest credential is already carried by the session/cookie/header, the client SHOULD NOT separately submit a guest database identifier.

Example:

```json
{}
```

The server determines which guest data belongs to the authenticated account.

The client MUST NOT submit migration instructions containing:

* rating totals
* XP totals
* achievements
* arbitrary attempt history
* arbitrary session ownership
* arbitrary reward state

The server performs the authoritative migration.

---

# 14. Guest Migration Semantics

Migration MUST be:

* atomic
* idempotent
* replay-resistant
* auditable
* ownership-checked

A retry MUST NOT create:

```text
duplicate attempts
duplicate rating changes
duplicate XP
duplicate achievements
```

A successful migration should establish a terminal migration state so that repeated requests cannot repeat the operation.

Example:

```json
{
  "migration": {
    "status": "completed"
  },
  "migrated": {
    "attempts": 42,
    "ratings": 5,
    "xp": 180,
    "achievements": 2
  }
}
```

The exact response may be simplified.

---

# 15. Player Profile

## Get Own Profile

```http
GET /api/v1/me/profile
```

## Update Own Profile

```http
PATCH /api/v1/me/profile
```

Example:

```json
{
  "display_name": "Omid",
  "bio": "...",
  "avatar_reference": "..."
}
```

Only explicitly permitted profile fields may be modified.

Server-managed fields MUST NOT be writable through this endpoint.

---

# 16. External Chess Identities

External chess identities are profile data and are separate from MicroChess ratings.

## List

```http
GET /api/v1/me/chess-identities
```

## Add

```http
POST /api/v1/me/chess-identities
```

Example:

```json
{
  "provider": "lichess",
  "username": "example",
  "rating": 2050,
  "rating_type": "rapid"
}
```

Supported providers may include:

```text
fide
lichess
chess_com
```

The exact provider registry is implementation-defined.

Self-reported ratings remain unverified unless an explicit verification mechanism exists.

---

# 17. Update External Identity

```http
PATCH /api/v1/me/chess-identities/{identity_id}
```

Only permitted fields may be changed.

Verification state MUST NOT be client-controlled.

The client MUST NOT be able to submit:

```json
{
  "is_verified": true
}
```

and cause the server to trust the identity.

---

# 18. Remove External Identity

```http
DELETE /api/v1/me/chess-identities/{identity_id}
```

Only the owning player or explicitly authorized administrator may perform this operation.

Object ownership MUST be checked.

---

# 19. Exercise Catalog

```http
GET /api/v1/exercises
```

The catalog returns exercises available to the current caller.

Example:

```json
{
  "items": [
    {
      "slug": "piece-recognition",
      "title": "...",
      "status": "active",
      "supports_practice": true,
      "supports_speed": true
    }
  ]
}
```

Disabled, unpublished, or otherwise unavailable exercises MUST NOT accidentally appear as playable exercises to ordinary users.

The API may expose metadata for an exercise that is visible but not currently playable if the product requires it.

---

# 20. Exercise Detail

```http
GET /api/v1/exercises/{exercise_slug}
```

Returns appropriate exercise metadata, including:

* stable identifier
* localized metadata
* supported modes
* availability
* relevant configuration
* current player state where appropriate

The response MUST NOT expose hidden puzzle answers or server-only validation data.

---

# 21. Exercise Session Creation

If an exercise requires an explicit training session:

```http
POST /api/v1/exercises/{exercise_slug}/sessions
```

Request:

```json
{
  "mode": "practice"
}
```

or:

```json
{
  "mode": "speed"
}
```

The server creates the authoritative session.

The client MUST NOT choose:

* score
* authoritative start timestamp
* rating
* puzzle solution
* final duration
* XP
* correctness

The server determines these values.

---

# 22. Session Response

Example:

```json
{
  "session": {
    "id": "...",
    "exercise": "pin",
    "mode": "practice",
    "started_at": "..."
  },
  "question": {
    "id": "...",
    "payload": {}
  }
}
```

`question.payload` is exercise-specific.

The payload MUST contain only information necessary for the client to render and answer the question.

---

# 23. Puzzle and Question Delivery

The API MUST return only information required to play the exercise.

It MUST NOT expose hidden authoritative answers.

Example for a pin exercise:

Allowed:

```json
{
  "position": "...",
  "side_to_move": "white",
  "selection_count": 3
}
```

Forbidden:

```json
{
  "correct_answer": ["e2", "e4", "e7"]
}
```

The same principle applies to all exercise types.

---

# 24. Attempt Submission

Core endpoint:

```http
POST /api/v1/training/attempts
```

Example:

```json
{
  "session_id": "...",
  "puzzle_id": "...",
  "answer": {}
}
```

The exact answer schema is exercise-specific.

The client submits only the answer and required request metadata.

The server determines:

* correctness
* score
* response time
* rating change
* XP
* achievement consequences
* authoritative feedback
* next training state

---

# 25. Attempt Validation

The server MUST validate:

1. caller identity
2. guest/authenticated ownership
3. session validity
4. exercise validity
5. puzzle/question validity
6. mode validity
7. answer schema
8. answer correctness
9. timing where applicable
10. submission uniqueness/idempotency
11. content availability
12. authorization

The server MUST ignore client-provided authoritative values such as:

```text
score
correctness
rating
rating_delta
xp
elapsed_time
```

when those values are calculated by the server.

---

# 26. Attempt Response

Example:

```json
{
  "attempt": {
    "id": "...",
    "correct": true,
    "score": 5,
    "response_time_ms": 2140
  },
  "rating": {
    "before": 1420,
    "delta": 8,
    "after": 1428
  },
  "gamification": {
    "xp_awarded": 5
  },
  "feedback": {
    "type": "correct"
  }
}
```

Fields are returned according to the capabilities enabled for the current user and exercise.

The response MUST represent server-authoritative results.

---

# 27. Speed Mode Timing

Speed mode timing is server-authoritative.

The client may display a local countdown for UX.

The server determines:

* session start
* expiration
* whether a submission was within the allowed time
* final session duration
* final score

The client cannot extend a session by submitting a different timestamp.

---

# 28. Training History

## Own Attempts

```http
GET /api/v1/me/training/attempts
```

Supported filters may include:

```text
exercise
mode
correct
date_from
date_to
```

Example:

```http
GET /api/v1/me/training/attempts?exercise=pin&mode=speed
```

The response represents historical training facts and MUST NOT silently recalculate historical results from current configuration.

---

# 29. Attempt Detail

```http
GET /api/v1/me/training/attempts/{attempt_id}
```

The response must expose only information the player is allowed to see.

Historical fields should represent the state relevant to the attempt at the time it occurred.

Private server-only validation data and hidden answers MUST remain excluded.

---

# 30. Training Sessions

```http
GET /api/v1/me/training/sessions
```

Supported filters:

```text
exercise
mode
date_from
date_to
```

Session detail:

```http
GET /api/v1/me/training/sessions/{session_id}
```

A session may expose aggregate information derived from its attempts.

It MUST NOT expose hidden answer data.

---

# 31. Ratings

## Current Ratings

```http
GET /api/v1/me/ratings
```

Example:

```json
{
  "items": [
    {
      "exercise": "pin",
      "rating": 1478,
      "provisional": true,
      "attempts_count": 31
    }
  ]
}
```

Each exercise has an independent MicroChess rating.

MicroChess ratings are separate from external FIDE/Lichess/Chess.com ratings.

---

# 32. Exercise Rating

```http
GET /api/v1/me/ratings/{exercise_slug}
```

Returns, where applicable:

* current rating
* provisional state
* attempts count
* uncertainty/development information if exposed
* latest update

The exact rating algorithm is defined by the training/rating domain specification, not by the API layer.

---

# 33. Rating History

```http
GET /api/v1/me/ratings/{exercise_slug}/history
```

Filters:

```text
date_from
date_to
```

Example:

```json
{
  "items": [
    {
      "occurred_at": "...",
      "before": 1450,
      "delta": 8,
      "after": 1458,
      "reason": "attempt"
    }
  ]
}
```

Rating history is read-only to ordinary clients.

---

# 34. Gamification Summary

```http
GET /api/v1/me/gamification
```

Example:

```json
{
  "xp": {
    "total": 1820,
    "level": 7
  },
  "streak": {
    "current": 5,
    "longest": 12
  },
  "achievements_unlocked": 14
}
```

The response represents server-calculated gamification state.

---

# 35. XP History

```http
GET /api/v1/me/gamification/xp
```

Supported filters may include:

```text
date_from
date_to
source_type
```

XP awards are historical reward records.

The client cannot create, modify, or delete XP awards.

Do not expose a generic client-facing endpoint such as:

```text
POST /xp
```

---

# 36. Achievements

## Available Achievements

```http
GET /api/v1/achievements
```

## Own Achievements

```http
GET /api/v1/me/achievements
```

Example:

```json
{
  "items": [
    {
      "code": "first_pin",
      "unlocked": true,
      "unlocked_at": "..."
    }
  ]
}
```

Achievement eligibility and unlocking are server-controlled.

---

# 37. Goals

```http
GET /api/v1/me/goals
```

Returns current daily/weekly goals and progress.

Goal completion is server-calculated.

The client cannot mark a goal as complete.

---

# 38. Streak

```http
GET /api/v1/me/streak
```

Example:

```json
{
  "current": 5,
  "longest": 12,
  "last_activity_date": "..."
}
```

The server determines qualifying activity.

---

# 39. Player Dashboard

```http
GET /api/v1/me/dashboard
```

Possible response:

```json
{
  "profile": {},
  "ratings": [],
  "recent_activity": [],
  "gamification": {},
  "goals": [],
  "streak": {},
  "recommended": []
}
```

The dashboard is a read/query operation.

It is an aggregation/read model and MUST NOT become a second source of business truth.

Recommendations are optional until the adaptive-training subsystem defines them.

---

# 40. Player Analytics

```http
GET /api/v1/me/analytics
```

Supported standard periods:

```text
7d
30d
90d
all
custom
```

Supported filters:

```text
period
date_from
date_to
exercise
```

The server defines timezone and period semantics.

---

# 41. Analytics Response

Example:

```json
{
  "period": {
    "from": "...",
    "to": "..."
  },
  "summary": {
    "attempts": 120,
    "accuracy": 0.81,
    "training_time_ms": 420000,
    "active_days": 6,
    "xp": 480
  },
  "rating": {
    "start": 1400,
    "end": 1478,
    "delta": 78
  }
}
```

Analytics are derived from authoritative training, rating, and gamification records.

Analytics responses MUST NOT modify those records.

---

# 42. Analytics Comparison

```http
GET /api/v1/me/analytics/comparison
```

Example:

```text
?current=7d&previous=7d
```

Example response:

```json
{
  "current": {},
  "previous": {},
  "changes": {
    "accuracy": 0.07,
    "attempts": 12,
    "training_time_ms": 30000
  }
}
```

The server defines comparison periods.

---

# 43. Exercise Analytics for Players

```http
GET /api/v1/me/analytics/exercises/{exercise_slug}
```

Possible metrics:

* attempts
* accuracy
* response time
* rating trend
* active days
* completion
* improvement
* recent performance
* mastery where available

The endpoint returns only data belonging to the current player.

---

# 44. Puzzle Analytics for Players

```http
GET /api/v1/me/analytics/puzzles/{puzzle_id}
```

Players may see appropriate personal statistics for puzzles they have attempted.

The endpoint MUST NOT expose hidden solution information merely because analytics are requested.

---

# 45. Leaderboards

```http
GET /api/v1/leaderboards
```

Possible filters:

```text
type
exercise
period
page
page_size
```

Possible leaderboard types:

```text
rating
xp
streak
challenge
```

Only supported leaderboard types should be accepted.

Privacy, eligibility, ranking scope, and visibility rules are enforced server-side.

---

# 46. Public Profile

If public profiles are enabled:

```http
GET /api/v1/players/{username}
```

Only explicitly public information is returned.

Private analytics, contact information, private notes, and sensitive profile data MUST NOT leak.

---

# 47. Admin API Boundary

Admin endpoints use:

```text
/api/v1/admin
```

Examples:

```text
/api/v1/admin/users
/api/v1/admin/exercises
/api/v1/admin/puzzles
/api/v1/admin/generators
/api/v1/admin/analytics
/api/v1/admin/audit
```

Every admin endpoint requires explicit backend authorization.

Frontend route guards are not security controls.

---

# 48. Admin Dashboard

```http
GET /api/v1/admin/dashboard
```

May return:

* user counts
* active users
* recent activity
* exercise activity
* puzzle statistics
* support status
* generator status
* system health indicators

This is an aggregated read operation.

It MUST NOT mutate platform state merely by being requested.

---

# 49. Admin Users

```http
GET /api/v1/admin/users
```

Filters:

```text
search
role
status
created_from
created_to
```

Pagination is mandatory.

The server must enforce reasonable limits.

---

# 50. Admin User Detail

```http
GET /api/v1/admin/users/{user_id}
```

The response may expose useful administrative information.

It MUST NOT return:

* password hashes
* session tokens
* reset tokens
* authentication secrets
* unnecessary sensitive credentials

---

# 51. Admin User Status

Possible actions:

```http
POST /api/v1/admin/users/{user_id}/suspend
```

```http
POST /api/v1/admin/users/{user_id}/reactivate
```

These are privileged state-changing operations.

They must:

* enforce authorization
* validate state transitions
* preserve historical records
* create appropriate audit records

---

# 52. Admin Roles

```http
GET /api/v1/admin/users/{user_id}/roles
```

Role assignment:

```http
POST /api/v1/admin/users/{user_id}/roles
```

Request:

```json
{
  "role": "coach"
}
```

Role changes must use the authorization/application layer.

The server must verify:

* acting administrator authorization
* target user validity
* valid role
* self-protection rules
* final-admin protection where applicable

The client cannot grant itself a role.

---

# 53. Admin Exercises

```http
GET /api/v1/admin/exercises
```

```http
GET /api/v1/admin/exercises/{exercise_id}
```

Exercise metadata may include:

* status
* ordering
* difficulty configuration
* rating configuration
* supported modes
* implementation availability
* puzzle count
* usage statistics

---

# 54. Admin Exercise Update

```http
PATCH /api/v1/admin/exercises/{exercise_id}
```

Editable fields depend on the exercise configuration and lifecycle.

Changes MUST pass through the Content/application layer.

Admin routes MUST NOT directly modify database rows to bypass domain rules.

---

# 55. Admin Puzzles

```http
GET /api/v1/admin/puzzles
```

Filters:

```text
exercise
status
difficulty
target_rating
source
tag
created_from
created_to
```

Pagination is mandatory.

---

# 56. Admin Puzzle Detail

```http
GET /api/v1/admin/puzzles/{puzzle_id}
```

May include:

* content
* lifecycle state
* validation results
* reviews
* statistics
* generation source
* tags
* version information
* history

Admin responses may expose information that ordinary players must never receive.

---

# 57. Manual Puzzle Creation

```http
POST /api/v1/admin/puzzles
```

The request contains exercise-specific content.

The server must:

1. validate request schema
2. validate exercise rules
3. validate uniqueness where required
4. assign the appropriate initial lifecycle state
5. record creator information
6. create appropriate audit history

Creation does not imply publication.

---

# 58. Puzzle Validation

```http
POST /api/v1/admin/puzzles/{puzzle_id}/validate
```

Example:

```json
{
  "status": "valid",
  "checks": []
}
```

Validation results may be persisted where useful.

Validation MUST NOT silently publish a puzzle.

---

# 59. Puzzle Review

```http
POST /api/v1/admin/puzzles/{puzzle_id}/review
```

Request:

```json
{
  "decision": "approved",
  "notes": "..."
}
```

Only authorized reviewers may perform the operation.

The exact valid decisions depend on the content lifecycle.

---

# 60. Puzzle Publication

```http
POST /api/v1/admin/puzzles/{puzzle_id}/publish
```

Publishing MUST verify all required prerequisites.

Typical prerequisites include:

```text
validated
reviewed
approved
```

The exact prerequisites are defined by the content policy.

Publishing is an explicit privileged action.

---

# 61. Puzzle Retirement

```http
POST /api/v1/admin/puzzles/{puzzle_id}/retire
```

Retirement MUST NOT destroy historical attempts referencing the puzzle.

The puzzle becomes unavailable for new play according to the content policy.

Historical analytics and attempts remain intact.

---

# 62. Generator Catalog

```http
GET /api/v1/admin/generators
```

Returns registered generators and their capabilities.

---

# 63. Generator Detail

```http
GET /api/v1/admin/generators/{generator_id}
```

May expose:

* supported exercise
* configuration schema
* generator version
* active state
* supported constraints

Generator configuration exposed to administrators must not expose secrets.

---

# 64. Generator Run

```http
POST /api/v1/admin/generators/{generator_id}/runs
```

Example:

```json
{
  "exercise_id": "...",
  "target_rating": 1400,
  "target_difficulty": 3,
  "count": 100,
  "constraints": {}
}
```

`target_rating` and `target_difficulty` are generation targets, not guarantees.

Generated content MUST enter the content validation/review workflow.

Generation MUST NOT automatically publish content.

---

# 65. Generator Run Status

```http
GET /api/v1/admin/generator-runs/{run_id}
```

Possible statuses:

```text
queued
running
completed
partial
failed
cancelled
```

If generation is asynchronous, creation may return:

```http
202 Accepted
```

The run status endpoint is authoritative for processing state.

---

# 66. Generated Content Workflow

Generated content follows the same controlled publication boundary as manually created content.

Typical flow:

```text
generator run
     ↓
generated
     ↓
validated
     ↓
preview
     ↓
review
     ↓
approved
     ↓
published
     ↓
active
```

Generation does not imply approval or publication.

---

# 67. Admin Analytics

```http
GET /api/v1/admin/analytics
```

Filters:

```text
period
exercise
puzzle
date_from
date_to
```

Possible metrics:

* total attempts
* unique players
* accuracy
* average response time
* rating distribution
* rating change
* retention
* active users
* exercise usage
* puzzle performance

Analytics endpoints are read-only.

---

# 68. Exercise Analytics

```http
GET /api/v1/admin/analytics/exercises/{exercise_id}
```

Possible response:

```json
{
  "attempts": 5000,
  "unique_players": 420,
  "accuracy": 0.71,
  "avg_response_time_ms": 3200,
  "observed_difficulty": 1435
}
```

`observed_difficulty` is derived analytics data.

It MUST NOT silently modify the exercise or puzzle configuration.

Difficulty calibration remains a separate future/content workflow.

---

# 69. Puzzle Analytics

```http
GET /api/v1/admin/analytics/puzzles/{puzzle_id}
```

Possible metrics:

* attempts
* unique players
* accuracy
* response time
* rating distribution
* observed difficulty
* recent trend

Analytics MUST NOT automatically retire, publish, or otherwise mutate puzzle state unless an explicit authorized workflow performs that action.

---

# 70. Support API

## Create Ticket

```http
POST /api/v1/support/tickets
```

Request:

```json
{
  "subject": "...",
  "message": "..."
}
```

Guests may be allowed to create tickets according to the support policy.

Guest tickets must have an appropriate ownership mechanism that does not rely on trusting a client-supplied user ID.

---

# 71. Own Support Tickets

```http
GET /api/v1/me/support/tickets
```

Ticket detail:

```http
GET /api/v1/me/support/tickets/{ticket_id}
```

Authenticated users may access only their own tickets.

Guest ticket access, if supported, must use the guest/session ownership mechanism rather than a client-supplied identity.

---

# 72. Admin Support

```http
GET /api/v1/admin/support/tickets
```

```http
GET /api/v1/admin/support/tickets/{ticket_id}
```

Reply:

```http
POST /api/v1/admin/support/tickets/{ticket_id}/messages
```

Close:

```http
POST /api/v1/admin/support/tickets/{ticket_id}/close
```

Privileged support actions must be authorized and auditable.

---

# 73. Coach API

Initial infrastructure may expose:

```http
GET /api/v1/coach/students
```

```http
GET /api/v1/coach/students/{student_id}
```

Access requires:

* authenticated coach identity
* appropriate capability
* active coach/student relationship
* object-level authorization
* privacy rules

Being a coach does not grant access to every player.

---

# 74. Coach Assignments

```http
POST /api/v1/coach/assignments
```

```http
GET /api/v1/coach/assignments
```

```http
PATCH /api/v1/coach/assignments/{assignment_id}
```

```http
DELETE /api/v1/coach/assignments/{assignment_id}
```

Only the appropriate coach may create or modify assignments.

Assignments must remain scoped to authorized students.

---

# 75. Coach Student Analytics

```http
GET /api/v1/coach/students/{student_id}/analytics
```

The endpoint MUST enforce:

1. active relationship
2. appropriate capability
3. student privacy settings
4. object-level authorization
5. allowed analytics scope

Revoked relationships MUST NOT retain ordinary ongoing access.

---

# 76. Parent API

Parent endpoints may be introduced when the parent/student relationship workflow is implemented.

Target endpoints:

```http
GET /api/v1/parent/children
```

```http
GET /api/v1/parent/children/{student_id}
```

```http
GET /api/v1/parent/children/{student_id}/analytics
```

Parent access requires an appropriate active relationship and authorization.

Parent access is not equivalent to administrator access.

Parents MUST NOT receive:

* passwords
* authentication tokens
* private credentials
* unrelated users' information
* unrestricted administrative information

---

# 77. Pagination

List endpoints MUST use a consistent pagination strategy.

The initial implementation may use:

```text
page
page_size
```

Example:

```http
GET /api/v1/admin/users?page=2&page_size=25
```

The server MUST enforce a maximum page size.

Clients MUST NOT be able to request unlimited records.

Cursor pagination may be introduced later for endpoints where offset pagination becomes inefficient.

The implementation should not introduce cursor pagination everywhere without an actual requirement.

---

# 78. Pagination Response

Preferred offset-pagination shape:

```json
{
  "items": [],
  "pagination": {
    "page": 2,
    "page_size": 25,
    "total": 420,
    "pages": 17
  }
}
```

The exact shape should be reconciled with existing API conventions before implementation.

Do not create a second incompatible pagination format for existing endpoints.

---

# 79. Filtering

Filters should use predictable query parameters.

Example:

```http
GET /api/v1/admin/puzzles?exercise=pin&status=published&difficulty=3
```

Do not create dozens of bespoke endpoint variants for simple filtering.

Filter fields MUST be explicitly whitelisted.

---

# 80. Sorting

Where useful:

```text
sort
order
```

Example:

```http
GET /api/v1/admin/users?sort=created_at&order=desc
```

The server MUST whitelist sortable fields.

The client MUST NOT be able to inject arbitrary SQL expressions.

---

# 81. Search

Search should use explicit parameters.

Example:

```http
GET /api/v1/admin/users?search=omid
```

Search behavior should be documented per resource where semantics differ.

Do not interpret arbitrary query parameters as database column names.

---

# 82. Date Filters

Date ranges use a consistent representation.

Example:

```text
date_from=2026-01-01
date_to=2026-01-31
```

The application defines timezone semantics centrally.

Analytics, streaks, goals, and date-based gamification MUST use the same documented application timezone policy.

---

# 83. Response Envelope

Do not introduce an unnecessary universal response wrapper.

Avoid forcing:

```json
{
  "success": true,
  "data": {}
}
```

onto every endpoint unless the existing project already follows that convention.

Existing compatible response conventions should be preserved.

---

# 84. Error Contract

Errors must have a predictable machine-readable structure.

Preferred conceptual form:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request is invalid.",
    "details": {}
  }
}
```

`code` is stable and machine-readable.

`message` is safe for client display.

`details` contains structured validation or business information where appropriate.

FastAPI/Pydantic's existing validation response may be retained if changing it would create unnecessary compatibility risk. FastAPI supports structured HTTP error responses and OpenAPI documentation for declared responses.

---

# 85. Validation Error

Example:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Some fields are invalid.",
    "details": {
      "username": [
        "This username is already in use."
      ]
    }
  }
}
```

The exact framework-level validation representation may remain unchanged if it is already established.

Do not rewrite the complete error system merely for stylistic consistency.

---

# 86. Common HTTP Status Codes

Typical mapping:

| Status | Meaning                                                       |
| ------ | ------------------------------------------------------------- |
| 200    | Successful request                                            |
| 201    | Resource created                                              |
| 202    | Accepted for asynchronous processing                          |
| 204    | Successful request with no response body                      |
| 400    | Malformed or otherwise invalid request                        |
| 401    | Authentication required or invalid                            |
| 403    | Authenticated but not authorized                              |
| 404    | Resource not found or intentionally hidden                    |
| 409    | Resource/state conflict                                       |
| 422    | Request validation failure where framework conventions use it |
| 429    | Rate limited                                                  |
| 500    | Unexpected server failure                                     |
| 503    | Temporarily unavailable                                       |

FastAPI supports explicit response status declarations and includes them in generated OpenAPI documentation.

---

# 87. 401 vs 403

Use:

```text
401
```

when valid authentication is absent or invalid.

Use:

```text
403
```

when the caller is authenticated but lacks permission.

Do not use `403` for every authorization-related failure.

---

# 88. 404 and Resource Privacy

For resources where revealing existence would leak sensitive information, the API may intentionally return:

```text
404 Not Found
```

instead of revealing that the resource exists.

Example:

A player should not necessarily learn that another private user's resource exists merely by guessing its identifier.

This behavior should be defined consistently by the security policy.

---

# 89. Conflict

Use:

```http
409 Conflict
```

for state conflicts such as:

* duplicate username
* duplicate relationship
* invalid lifecycle transition
* incompatible state transition
* conflicting idempotency request

Not every validation error is a conflict.

---

# 90. Rate Limiting

Rate limiting should protect at minimum:

* login
* registration
* password-related attempts
* support submission
* expensive analytics
* generator operations
* abuse-prone public endpoints

Rate limiting is a server-side security policy.

The client cannot control rate limits.

---

# 91. Idempotency

Operations that may be retried MUST be designed to prevent harmful duplicate effects.

Important examples:

```text
guest migration
attempt submission
generator run creation
support submission where duplicate tickets are harmful
privileged state-changing operations where retry duplication is unsafe
```

An idempotency strategy may use:

```text
Idempotency-Key: <unique-client-generated-key>
```

or an equivalent domain-specific mechanism.

The implementation should introduce idempotency storage only for operations that actually require it.

Do not add a generic idempotency subsystem to every endpoint without justification.

---

# 92. Attempt Idempotency

Attempt submission is a critical idempotency boundary.

A network retry MUST NOT create:

```text
two attempts
two rating changes
two XP awards
duplicate achievement effects
```

The server should associate a submission with a unique request/session identity appropriate to the exercise.

The exact mechanism may use an idempotency key, a session/question sequence identifier, or a combination where appropriate.

The mechanism MUST be enforced server-side.

---

# 93. Authorization Contract

Every protected endpoint should define:

```text
Authentication requirement
Authorization requirement
Ownership requirement
Relationship requirement where applicable
Privacy requirement where applicable
```

Example:

```text
GET /api/v1/me/ratings

Authentication: required
Authorization: self
Ownership: current user
```

Example:

```text
GET /api/v1/admin/users

Authentication: required
Authorization: users.read
Ownership: none
```

Example:

```text
GET /api/v1/coach/students/{student_id}/analytics

Authentication: required
Authorization: analytics.read_related
Relationship: active coach/student relationship
Object access: required
Privacy: required
```

---

# 94. Object-Level Authorization

Route-level role checks are insufficient.

For example:

```text
Coach
```

does not mean:

```text
Coach may access every student.
```

The server MUST verify the specific relationship and resource scope.

This applies to:

* coach → student
* parent → child
* player → own data
* admin → privileged resources
* support → ticket ownership
* guest → guest session ownership

---

# 95. Sensitive Response Fields

Responses must follow least privilege.

Never expose:

* password hashes
* session secrets
* reset tokens
* authentication secrets
* unnecessary personal information
* private coach notes
* private parent information
* hidden puzzle answers
* internal security metadata

Administrative responses may expose additional operational information only when explicitly authorized.

---

# 96. Time and Clock Authority

The server is authoritative for:

* session start time
* session expiration
* attempt timestamp
* speed-mode deadline
* rating event timestamp
* XP award timestamp
* streak date calculation

The browser clock may be used for visual countdowns and presentation only.

---

# 97. Chess Data Authority

For chess exercises, the server is authoritative for:

* legal moves
* FEN interpretation
* SAN parsing
* solution validation
* board state validation
* chess rules

Where `python-chess` is the established implementation mechanism, exercise/domain logic should continue using it rather than trusting client calculations.

---

# 98. API Security Boundary

Every API request is untrusted input.

Never trust client-provided authoritative values such as:

```text
user_id
role
score
rating
rating_delta
XP
correctness
admin flag
ownership
elapsed_time
```

The server derives these values from:

* authenticated identity
* session state
* domain rules
* authoritative stored data

---

# 99. Admin API Security

Admin endpoints require explicit backend authorization.

This is forbidden:

```text
if frontend_route.startsWith("/admin"):
    allow
```

Frontend guards are UX controls only.

The backend MUST independently enforce admin capabilities.

---

# 100. API and Domain Separation

Pydantic request/response schemas are API contracts.

They are not automatically domain entities.

Preferred flow:

```text
HTTP
 ↓
Pydantic DTO
 ↓
Application command/query
 ↓
Domain rules
 ↓
Persistence
 ↓
Application result
 ↓
Response DTO
 ↓
HTTP
```

The exact internal layering follows `ARCHITECTURE.md`.

---

# 101. API and Database Separation

API routes MUST NOT contain core business logic or arbitrary database operations.

Avoid:

```python
@router.post(...)
def endpoint(...):
    db.add(...)
    db.commit(...)
```

when the operation contains business rules.

Preferred:

```text
Route
 ↓
Application service / use case
 ↓
Domain rules
 ↓
Repository / persistence abstraction
 ↓
Database
```

Simple read-only infrastructure may be implemented more directly where justified, but business rules MUST remain outside route handlers.

---

# 102. API and Analytics Separation

Analytics endpoints are read/query operations.

They MUST NOT modify:

* attempts
* ratings
* XP
* achievements
* puzzle state
* exercise configuration

merely because analytics were requested.

Analytics consume authoritative historical data.

They do not become the source of truth for that data.

---

# 103. API and Content Separation

Admin content APIs MUST use Content application/domain workflows.

They MUST NOT bypass:

* validation
* review
* approval
* publication
* retirement
* audit

through direct database updates.

---

# 104. API and Gamification Separation

The client never directly creates rewards.

There must not be a client-authoritative endpoint such as:

```text
POST /xp
```

XP and achievements result from server-authoritative training/application workflows.

The API may expose read operations such as:

```text
GET /me/gamification
GET /me/gamification/xp
GET /me/achievements
```

but reward creation remains server-controlled.

---

# 105. API and Rating Separation

The client cannot submit:

```json
{
  "rating_delta": 50
}
```

to change its rating.

Rating changes result from authoritative training outcomes or explicitly controlled administrative correction workflows.

Ordinary clients have no generic rating-write endpoint.

---

# 106. API Evolution

New response fields may generally be added without breaking compatible clients.

Removing or changing the meaning/type of existing fields requires:

* migration strategy
* documentation
* tests
* compatibility review
* API versioning where necessary

The implementation must avoid breaking the existing frontend while introducing platform functionality.

---

# 107. OpenAPI and API Documentation

The implemented FastAPI/OpenAPI specification should reflect the actual API.

Documentation should include, where relevant:

* authentication requirements
* request schema
* response schema
* status codes
* authorization requirements
* important business constraints
* error responses

Generated OpenAPI documentation is the implementation-level contract.

This document remains the product-level API contract.

When additional response codes are possible, they should be declared so that the OpenAPI schema remains accurate.

---

# 108. API Testing

Important API tests should cover meaningful contracts.

## Authentication

* registration
* duplicate username
* login
* invalid credentials
* logout
* protected endpoint access

## Guest

* session creation
* guest training access
* guest ownership
* migration
* migration idempotency
* migration authorization

## Training

* valid attempt
* invalid answer
* unauthorized session
* duplicate submission
* expired speed session
* hidden-answer protection

## Ratings

* correct rating update
* rating history
* unauthorized modification attempt
* duplicate attempt does not duplicate rating change

## Gamification

* valid XP award
* achievement unlock
* duplicate reward prevention
* client cannot award XP

## Admin

* admin access
* non-admin rejection
* capability enforcement
* object-level authorization
* audit creation
* self-protection rules

## Content

* puzzle validation
* lifecycle transitions
* publication prerequisites
* retirement
* generated-content separation

## Relationships

* coach/student authorization
* parent/child authorization
* revoked relationship access
* unrelated student access rejection

Tests should protect meaningful contracts, not merely increase endpoint count.

---

# 109. API Contract Invariants

The following invariants are mandatory.

### Invariant 1

The client cannot determine authoritative correctness.

### Invariant 2

The client cannot determine authoritative score.

### Invariant 3

The client cannot determine authoritative rating.

### Invariant 4

The client cannot award XP.

### Invariant 5

The client cannot unlock achievements.

### Invariant 6

The client cannot bypass content lifecycle.

### Invariant 7

Frontend permissions do not replace backend authorization.

### Invariant 8

Private resources require object-level authorization.

### Invariant 9

Retrying an attempt cannot duplicate its authoritative effects.

### Invariant 10

Guest migration cannot duplicate history or rewards.

### Invariant 11

Hidden puzzle answers are never returned to ordinary players.

### Invariant 12

Analytics endpoints are read-only.

### Invariant 13

API routes do not contain core business rules.

### Invariant 14

Guest is not a persisted application role.

### Invariant 15

External chess ratings are separate from MicroChess ratings.

### Invariant 16

Analytics are not the source of truth for training history.

---

# 110. Minimum API Foundation

The first platform phase does not need every endpoint in this document.

The minimum coherent foundation should support the actual Phase 1/2/3 scope.

Target foundation:

```text
POST /auth/register
POST /auth/login
POST /auth/logout
GET  /me

POST /guest/session
GET  /guest/session
POST /guest/migrate

GET  /me/profile
PATCH /me/profile

GET  /exercises
GET  /exercises/{slug}

POST /exercises/{slug}/sessions
POST /training/attempts

GET  /me/training/attempts
GET  /me/training/sessions

GET  /me/ratings
GET  /me/gamification
GET  /me/dashboard
GET  /me/analytics
```

Administrative and content endpoints should be introduced according to the phase plan.

Do not implement the entire target API before its dependencies are ready.

---

# 111. Implementation Rules

Before modifying APIs, the agent MUST:

1. inspect existing routes
2. inspect existing Pydantic schemas
3. inspect existing frontend API calls
4. inspect existing authentication/session behavior
5. identify existing API conventions
6. identify existing exercise-specific contracts
7. preserve compatible existing contracts
8. reuse existing authentication infrastructure where correct
9. avoid duplicate endpoints
10. implement server-authoritative workflows
11. add meaningful tests
12. update OpenAPI/API documentation
13. verify frontend compatibility

The agent MUST NOT rewrite the entire API merely to make route names aesthetically consistent.

If an existing endpoint already provides the required behavior, extend it where practical instead of creating a duplicate endpoint.

---

# 112. Implementation Priority

API implementation should follow dependency order rather than endpoint count.

Preferred order:

```text
Authentication / Sessions
        ↓
Authorization foundation
        ↓
Profile / Identity
        ↓
Exercise discovery / sessions
        ↓
Attempt submission
        ↓
Training history
        ↓
Ratings
        ↓
Gamification
        ↓
Dashboard / Analytics
        ↓
Administration
        ↓
Content / Generators
        ↓
Relationships
        ↓
Adaptive training
```

The phase documents define the actual implementation sequence.

This document defines the target contract, not a requirement to implement every endpoint immediately.

---

# 113. API Contract Change Rule

A change to an accepted API contract must identify:

* affected endpoint(s)
* request/response impact
* compatibility impact
* affected frontend clients
* affected tests
* affected documentation
* whether versioning is required

Breaking changes MUST NOT be introduced silently.

If an accepted architecture or security decision is affected, the relevant ADR must also be updated through the documented ADR process rather than silently changing the meaning of this document.

---

# 114. Final API Principle

The API is the boundary between an untrusted client and authoritative MicroChess state.

Therefore:

```text
Client
   ↓
Request
   ↓
Authentication
   ↓
Authorization
   ↓
Validation
   ↓
Application Workflow
   ↓
Domain Rules
   ↓
Persistence
   ↓
Authoritative Result
   ↓
Response
```

The most important rule is:

> **The client may request an outcome; only the server may decide the outcome.**

This applies to:

* correctness
* score
* rating
* XP
* achievements
* timing
* ownership
* permissions
* content publication
* analytics inputs
* historical records
