# MicroChess Platform — API Contracts

## 1. Document Status

**Status:** Accepted
**Document Type:** Target API Contract
**Scope:** Platform API behavior, resource contracts, authorization boundaries, and cross-cutting API rules

This document defines the **target API contract** for the MicroChess platform.

It does not imply that every endpoint currently exists.

The repository remains the source of truth for the current implementation.

Before implementing or changing an API, the agent MUST inspect:

* existing FastAPI routes
* Pydantic schemas
* application/domain services
* persistence/repositories
* authentication/session implementation
* frontend API client
* existing exercise-specific APIs
* existing tests

Existing working behavior must be preserved unless an intentional change is required, documented, and tested.

---

# 2. API Authority

API requirements are governed by:

1. accepted ADRs
2. `MASTER_PLAN.md`
3. the most specific applicable domain specification
4. `API_CONTRACTS.md`
5. active phase specification
6. repository implementation

If two accepted specifications conflict, the agent MUST identify the conflict instead of silently choosing one.

This document defines API behavior.

It does not define:

* domain algorithms
* database schema
* UI design
* implementation architecture in full
* current repository state

Those belong to their respective canonical documents.

---

# 3. API Design Principles

The API MUST be:

* predictable
* explicit
* typed
* versionable
* secure
* server-authoritative
* compatible with guest and authenticated users
* suitable for the React frontend
* extensible without premature infrastructure

The API SHOULD use standard HTTP semantics.

Routes/controllers MUST remain thin.

Business rules belong in application/domain layers.

---

# 4. API Versioning

The preferred public API prefix is:

```text
/api/v1
```

Examples:

```text
/api/v1/auth/login
/api/v1/me
/api/v1/exercises
/api/v1/training/sessions
/api/v1/training/attempts
```

The agent MUST reconcile this with the existing repository before introducing or changing the API prefix.

A second competing API prefix MUST NOT be introduced.

Breaking changes require:

* a new API version, or
* an explicit compatibility/migration strategy.

Breaking changes include:

* removing a response field
* changing field meaning
* changing a field type incompatibly
* changing authentication semantics
* changing required request fields
* changing endpoint meaning

Compatible response fields may generally be added without a new API version.

---

# 5. HTTP Methods

Use standard semantics:

| Method   | Typical use          |
| -------- | -------------------- |
| `GET`    | Read/query           |
| `POST`   | Create/submit/action |
| `PUT`    | Full replacement     |
| `PATCH`  | Partial update       |
| `DELETE` | Delete/deactivate    |

Action endpoints are appropriate when an operation represents a real domain action.

Example:

```http
POST /api/v1/training/attempts
```

is preferable to pretending that answer submission is a generic CRUD update.

---

# 6. Identity Model

The canonical persisted roles are:

```text
PLAYER
COACH
PARENT
ADMIN
```

Guest is **not** a persisted role.

A guest is a temporary training identity represented by a server-controlled guest session/credential.

The API must distinguish:

```text
Authentication
Who is making the request?

Authorization
Is this identity allowed to perform the operation?

Object authorization
Is this specific resource within the caller's allowed scope?
```

All applicable checks MUST be enforced server-side.

---

# 7. Authentication

## 7.1 Registration

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

Initial registration does not require:

* email
* phone
* real name
* FIDE identity
* Lichess identity
* Chess.com identity

The server creates the authenticated account/session according to the selected authentication architecture.

The response MUST NOT expose sensitive authentication material unnecessarily.

---

## 7.2 Login

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

Successful login establishes an authenticated session.

Invalid credentials MUST use a generic failure response and MUST NOT reveal whether:

* the username exists
* the password was nearly correct
* another account has related information

---

## 7.3 Logout

```http
POST /api/v1/auth/logout
```

Successful logout:

```http
204 No Content
```

The current authenticated session/credential becomes invalid.

---

## 7.4 Current User

```http
GET /api/v1/me
```

Example:

```json
{
  "user": {
    "id": "...",
    "username": "...",
    "roles": ["PLAYER"]
  },
  "profile": {}
}
```

Only authorized information may be returned.

Guest access MUST NOT be represented as:

```json
{
  "roles": ["GUEST"]
}
```

---

# 8. Guest Sessions

## 8.1 Create Guest Session

```http
POST /api/v1/guest/session
```

Example response:

```json
{
  "guest_session": {
    "expires_at": "..."
  }
}
```

The server establishes the guest identity through the selected session/credential mechanism.

The client MUST NOT be trusted to provide a guest database identifier as proof of ownership.

Internal identifiers or secrets MUST NOT be exposed unless required by the protocol.

---

## 8.2 Current Guest Session

```http
GET /api/v1/guest/session
```

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

Expired or absent guest sessions MUST NOT expose another guest's information.

---

# 9. Guest Migration

Guest training data may be migrated to an authenticated account.

```http
POST /api/v1/guest/migrate
```

The guest identity MUST be derived from the current server-controlled guest credential/session.

The client MUST NOT submit arbitrary ownership identifiers.

The client MUST NOT submit authoritative values such as:

* rating
* rating delta
* XP
* achievements
* attempt history
* reward state
* session ownership

The server performs the migration.

Migration MUST be:

* atomic
* idempotent
* replay-resistant
* ownership-checked
* auditable where required

A retry MUST NOT create duplicate:

* attempts
* rating events
* XP awards
* achievements
* migrated sessions

After successful migration, the guest migration state becomes terminal.

---

# 10. Profiles

## Own Profile

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

Only explicitly writable fields may be modified.

Server-managed fields MUST NOT be writable through the profile API.

---

# 11. External Chess Identities

External chess identities are profile information.

They are separate from MicroChess exercise ratings.

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

Possible providers include:

```text
fide
lichess
chess_com
```

The provider registry is implementation-defined.

Self-reported ratings remain unverified unless a supported verification mechanism exists.

## Update

```http
PATCH /api/v1/me/chess-identities/{identity_id}
```

Verification state MUST NOT be client-controlled.

## Remove

```http
DELETE /api/v1/me/chess-identities/{identity_id}
```

Ownership MUST be checked.

---

# 12. Exercise Catalog

## List Exercises

```http
GET /api/v1/exercises
```

The response contains exercises available to the current caller.

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

Unavailable exercises MUST NOT accidentally become playable.

An exercise may be visible as:

* unavailable
* disabled
* coming soon

when the product requires such presentation.

---

## Exercise Detail

```http
GET /api/v1/exercises/{exercise_slug}
```

May return:

* stable identifier
* localized metadata
* supported modes
* availability
* relevant configuration
* current player state where appropriate

It MUST NOT expose:

* hidden answers
* server-only validation data
* authoritative solution data

---

# 13. Training Sessions

If an exercise uses explicit sessions:

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

The client MUST NOT determine:

* authoritative start time
* expiration
* score
* correctness
* rating
* rating delta
* XP
* final duration
* puzzle solution

---

# 14. Question Instances

A training session may contain one or more question instances.

A **question instance** represents the concrete server-issued question presented to the player during a session.

It is intentionally distinct from the underlying puzzle/content identifier.

Conceptually:

```text
Puzzle / Content
      ↓
Question Instance
      ↓
Attempt
```

The question instance binds the delivered question to:

* session
* exercise
* mode
* content
* delivery state
* server-side timing/context where applicable

The client receives only the data required to render and answer that instance.

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
    "instance_id": "...",
    "payload": {}
  }
}
```

The client MUST use the question instance identifier when submitting an answer.

The client MUST NOT use a raw puzzle/content identifier as a substitute for the question instance when the session uses question instances.

---

# 15. Question Payload

Question payloads are exercise-specific.

Example:

```json
{
  "instance_id": "...",
  "payload": {
    "position": "...",
    "side_to_move": "white"
  }
}
```

Payloads MUST contain only information required by the client.

Hidden authoritative answers MUST NOT be included.

Forbidden example:

```json
{
  "correct_answer": ["e2", "e4"]
}
```

This rule applies to every exercise type.

---

# 16. Attempt Submission

Core endpoint:

```http
POST /api/v1/training/attempts
```

Preferred request:

```json
{
  "session_id": "...",
  "question_instance_id": "...",
  "answer": {},
  "idempotency_key": "..."
}
```

`answer` is exercise-specific.

The server determines:

* correctness
* score
* response time
* rating change
* XP
* achievements
* authoritative feedback
* resulting training state

The client MUST NOT submit authoritative result values.

---

# 17. Attempt Validation

For every attempt, the server MUST validate as applicable:

1. caller identity
2. guest/authenticated ownership
3. session validity
4. question-instance ownership
5. exercise validity
6. content/question validity
7. mode validity
8. answer schema
9. answer correctness
10. timing
11. content availability
12. authorization
13. idempotency
14. session state

The server MUST reject an attempt when the question instance:

* belongs to another session
* belongs to another user/guest
* has expired
* is already terminal
* is invalid
* is unavailable
* has already been submitted where repeat submission is forbidden

---

# 18. Attempt Idempotency

Attempt submission MUST be idempotent.

The client SHOULD provide:

```text
idempotency_key
```

The server MUST bind the key to the relevant authenticated/guest identity and operation context.

A repeated request with the same valid idempotency key MUST NOT produce another authoritative result.

It MUST NOT create duplicate:

* attempts
* rating events
* XP
* achievements
* streak activity

The server may return the original result.

An idempotency key MUST NOT allow one identity to replay another identity's operation.

---

# 19. Attempt Response

Example:

```json
{
  "attempt": {
    "id": "...",
    "question_instance_id": "...",
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

Returned fields depend on the active product capabilities.

The response MUST represent server-authoritative results.

---

# 20. Speed Mode

Speed-mode timing is server-authoritative.

The client may display a local countdown for UX.

The server determines:

* session start
* deadline
* expiration
* whether submission was on time
* final duration
* final score

Client-provided timestamps MUST NOT override server timing.

---

# 21. Training History

## Own Attempts

```http
GET /api/v1/me/training/attempts
```

Possible filters:

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

Historical responses MUST represent facts as they occurred.

The API MUST NOT silently recalculate historical results using current exercise/rating configuration.

---

## Attempt Detail

```http
GET /api/v1/me/training/attempts/{attempt_id}
```

Only authorized information may be returned.

Historical fields should represent the relevant state at the time of the attempt.

Hidden solutions and private server validation data MUST remain excluded.

---

## Sessions

```http
GET /api/v1/me/training/sessions
```

Possible filters:

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

A session may expose aggregate information derived from attempts.

It MUST NOT expose hidden answer data.

---

# 22. Ratings

MicroChess ratings are independent per applicable exercise.

They are separate from:

* FIDE ratings
* Lichess ratings
* Chess.com ratings

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

## Exercise Rating

```http
GET /api/v1/me/ratings/{exercise_slug}
```

May return:

* current rating
* provisional state
* attempt count
* uncertainty/development information
* latest update

The rating algorithm is defined by the rating domain, not the API contract.

## Rating History

```http
GET /api/v1/me/ratings/{exercise_slug}/history
```

Possible filters:

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

There is no generic client-facing rating-write endpoint.

---

# 23. Gamification

Gamification state is server-controlled.

## Summary

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

## XP History

```http
GET /api/v1/me/gamification/xp
```

XP records are historical reward facts.

Clients cannot create, modify, or delete XP.

There must not be an endpoint such as:

```text
POST /api/v1/xp
```

## Achievements

```http
GET /api/v1/achievements
GET /api/v1/me/achievements
```

Unlocking is server-controlled.

## Goals

```http
GET /api/v1/me/goals
```

Goal progress and completion are server-calculated.

## Streak

```http
GET /api/v1/me/streak
```

The server determines qualifying activity.

---

# 24. Player Dashboard

```http
GET /api/v1/me/dashboard
```

The dashboard may aggregate:

* profile
* ratings
* recent activity
* gamification
* goals
* streak
* progress
* recommendations when available

The dashboard is a read model.

It MUST NOT become a second source of business truth.

Recommendations are optional until adaptive-training behavior is implemented.

---

# 25. Player Progress and Basic Summaries

Player-facing progress belongs to the player platform.

Examples may include:

```http
GET /api/v1/me/progress
GET /api/v1/me/progress/{exercise_slug}
```

These endpoints may provide:

* completion
* attempts
* basic accuracy
* current mastery
* recent activity
* basic improvement indicators

These are **player-product summaries**, not the complete analytics platform.

The full analytics system belongs to the Analytics domain and Phase 8.

---

# 26. Analytics

Analytics are derived/read-only views over authoritative data.

They MUST NOT modify:

* attempts
* ratings
* XP
* achievements
* puzzle state
* exercise configuration

## Player Analytics

```http
GET /api/v1/me/analytics
```

Standard periods:

```text
7d
30d
90d
all
custom
```

Possible filters:

```text
period
date_from
date_to
exercise
```

The server defines timezone and period semantics.

## Comparison

```http
GET /api/v1/me/analytics/comparison
```

Example:

```text
?current=7d&previous=7d
```

## Exercise Analytics

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
* mastery

## Puzzle Analytics

```http
GET /api/v1/me/analytics/puzzles/{puzzle_id}
```

Only personal information may be returned.

The endpoint MUST NOT expose hidden solutions.

---

# 27. Leaderboards

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

Possible types:

```text
rating
xp
streak
challenge
```

Only supported types are accepted.

Privacy, eligibility, visibility, and ranking scope are server-controlled.

---

# 28. Public Profiles

If public profiles are enabled:

```http
GET /api/v1/players/{username}
```

Only explicitly public information may be returned.

The endpoint MUST NOT expose:

* private analytics
* contact information
* private notes
* credentials
* unrelated user information

---

# 29. Administration API

Admin APIs use:

```text
/api/v1/admin
```

Examples:

```text
/api/v1/admin/dashboard
/api/v1/admin/users
/api/v1/admin/exercises
/api/v1/admin/puzzles
/api/v1/admin/generators
/api/v1/admin/analytics
/api/v1/admin/audit
```

Every admin endpoint requires explicit backend authorization.

Frontend route guards are not security controls.

Admin APIs MUST use application/domain workflows rather than direct database manipulation.

---

# 30. Admin Dashboard

```http
GET /api/v1/admin/dashboard
```

May expose aggregated operational information such as:

* user counts
* activity
* exercise usage
* puzzle statistics
* support status
* generator status
* system indicators

The endpoint is read-only.

---

# 31. Admin Users

## List

```http
GET /api/v1/admin/users
```

Possible filters:

```text
search
role
status
created_from
created_to
```

Pagination is mandatory.

## Detail

```http
GET /api/v1/admin/users/{user_id}
```

Must never expose:

* password hashes
* session tokens
* reset tokens
* authentication secrets
* unnecessary credentials

## Suspend

```http
POST /api/v1/admin/users/{user_id}/suspend
```

## Reactivate

```http
POST /api/v1/admin/users/{user_id}/reactivate
```

State-changing admin operations MUST:

* authorize the administrator
* validate state transitions
* preserve history
* create required audit records

---

# 32. Admin Roles

## Current Roles

```http
GET /api/v1/admin/users/{user_id}/roles
```

## Assign Role

```http
POST /api/v1/admin/users/{user_id}/roles
```

Example:

```json
{
  "role": "COACH"
}
```

The server MUST validate:

* acting administrator capability
* target user
* valid role
* self-protection rules
* final-admin protection where applicable

The client cannot grant itself a role.

---

# 33. Admin Exercise Management

Exercise administration belongs to the administration/content boundaries.

Possible endpoints:

```http
GET /api/v1/admin/exercises
GET /api/v1/admin/exercises/{exercise_id}
PATCH /api/v1/admin/exercises/{exercise_id}
```

Exercise changes MUST pass through the appropriate application/domain workflow.

Admin routes MUST NOT directly update database rows to bypass domain rules.

Phase 6 provides administrative foundation.

Phase 7 owns the complete content lifecycle.

---

# 34. Admin Puzzle Management

Possible endpoints:

```http
GET /api/v1/admin/puzzles
GET /api/v1/admin/puzzles/{puzzle_id}
POST /api/v1/admin/puzzles
PATCH /api/v1/admin/puzzles/{puzzle_id}
```

Possible filters:

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

Puzzle mutations MUST pass through content validation and lifecycle rules.

---

# 35. Content Lifecycle

The API must respect the content lifecycle:

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

Not every state requires a dedicated endpoint.

State transitions must be explicit domain actions where necessary.

The API MUST NOT allow arbitrary status manipulation that bypasses lifecycle validation.

---

# 36. Publishing

Where explicit publishing is required:

```http
POST /api/v1/admin/puzzles/{puzzle_id}/publish
```

Publishing MUST validate:

* content validity
* required metadata
* lifecycle state
* approval requirements
* authorization

Publishing a generated puzzle does not bypass review/approval requirements.

---

# 37. Retiring Content

Where applicable:

```http
POST /api/v1/admin/puzzles/{puzzle_id}/retire
```

Retirement MUST preserve historical training records.

Retiring content MUST NOT rewrite past attempts.

---

# 38. Generators

Generator management belongs to Phase 7.

Possible endpoints:

```http
GET /api/v1/admin/generators
GET /api/v1/admin/generators/{generator_id}
POST /api/v1/admin/generators/{generator_id}/runs
GET /api/v1/admin/generator-runs
GET /api/v1/admin/generator-runs/{run_id}
```

A generator run may specify:

* generator
* exercise
* target rating
* difficulty
* constraints
* batch size

Generated content is not automatically production content.

The generator pipeline must support:

```text
generate
→ validate
→ deduplicate
→ review
→ approve
→ publish
```

Target rating/difficulty are objectives, not guarantees.

---

# 39. Generator Run Safety

Generator operations MUST be:

* authorized
* bounded
* observable
* repeat-safe where appropriate
* protected against unbounded resource consumption

The API MUST NOT expose arbitrary executable generator configuration from untrusted clients.

---

# 40. Admin Analytics

Admin analytics belong to the analytics/content/administration boundaries.

Possible endpoints:

```http
GET /api/v1/admin/analytics
GET /api/v1/admin/analytics/exercises/{exercise_id}
GET /api/v1/admin/analytics/puzzles/{puzzle_id}
```

Possible metrics include:

* attempts
* unique players
* accuracy
* response time
* rating distribution
* observed difficulty
* trends

Analytics MUST NOT automatically mutate content.

For example, requesting puzzle analytics must not automatically:

* publish
* retire
* modify
* reprioritize

a puzzle.

---

# 41. Audit API

Where administrative audit is exposed:

```http
GET /api/v1/admin/audit
GET /api/v1/admin/audit/{audit_id}
```

Audit records are read-only to ordinary administrative clients unless a dedicated controlled maintenance workflow exists.

Sensitive audit information must follow the security policy.

---

# 42. Support API

Support is part of the administration foundation.

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

Guest support may be enabled when the support policy allows it.

Guest ownership MUST be derived from the server-controlled guest identity.

## Own Tickets

```http
GET /api/v1/me/support/tickets
GET /api/v1/me/support/tickets/{ticket_id}
```

Users may access only their own tickets.

## Admin Tickets

```http
GET /api/v1/admin/support/tickets
GET /api/v1/admin/support/tickets/{ticket_id}
POST /api/v1/admin/support/tickets/{ticket_id}/messages
POST /api/v1/admin/support/tickets/{ticket_id}/close
```

Privileged support operations MUST be authorized and auditable.

Notifications are not a separate canonical API phase in this plan.

---

# 43. Coach API

Coach/student functionality belongs to the Relationships phase.

Possible endpoints:

```http
GET /api/v1/coach/students
GET /api/v1/coach/students/{student_id}
```

Access requires:

* authenticated coach identity
* appropriate capability
* active coach/student relationship
* object-level authorization
* privacy rules

Being a coach does not grant access to all players.

---

# 44. Coach Assignments

Possible endpoints:

```http
POST /api/v1/coach/assignments
GET /api/v1/coach/assignments
PATCH /api/v1/coach/assignments/{assignment_id}
DELETE /api/v1/coach/assignments/{assignment_id}
```

Assignments must remain scoped to authorized students.

Only authorized coaches may create or modify their assignments.

---

# 45. Coach Analytics

Possible endpoint:

```http
GET /api/v1/coach/students/{student_id}/analytics
```

Access requires:

1. active relationship
2. appropriate capability
3. privacy permission
4. object-level authorization
5. permitted analytics scope

Revoked relationships MUST NOT retain ordinary ongoing access.

---

# 46. Parent API

Parent/student endpoints belong to the Relationships phase.

Possible endpoints:

```http
GET /api/v1/parent/children
GET /api/v1/parent/children/{student_id}
GET /api/v1/parent/children/{student_id}/analytics
```

Parent access requires an active authorized relationship.

Parent access is not administrator access.

Parents MUST NOT receive:

* passwords
* authentication tokens
* private credentials
* unrelated user information
* unrestricted administrative information

---

# 47. Pagination

List endpoints MUST use a consistent pagination strategy.

Initial strategy:

```text
page
page_size
```

Example:

```http
GET /api/v1/admin/users?page=2&page_size=25
```

The server MUST enforce a maximum page size.

Clients MUST NOT request unlimited records.

Preferred response:

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

The exact response shape must be reconciled with existing repository conventions before implementation.

Cursor pagination may be introduced later only where justified by measured requirements.

Do not introduce cursor pagination globally without evidence.

---

# 48. Filtering

Filters use explicit query parameters.

Example:

```http
GET /api/v1/admin/puzzles?exercise=pin&status=published&difficulty=3
```

Filterable fields MUST be explicitly whitelisted.

Do not create arbitrary database-column filtering.

---

# 49. Sorting

Where useful:

```text
sort
order
```

Example:

```http
GET /api/v1/admin/users?sort=created_at&order=desc
```

Sortable fields MUST be whitelisted.

Clients MUST NOT be able to inject SQL expressions.

---

# 50. Search

Search should use explicit parameters.

Example:

```http
GET /api/v1/admin/users?search=omid
```

Search semantics may vary by resource and should be documented by that resource when necessary.

Arbitrary query parameters MUST NOT be interpreted as database fields.

---

# 51. Date and Time Parameters

Date filters use a consistent representation.

Example:

```text
date_from=2026-01-01
date_to=2026-01-31
```

Application timezone semantics are defined centrally.

The same policy MUST be used for:

* analytics
* streaks
* goals
* date-based gamification
* training summaries

Timestamps transmitted by the API SHOULD use an unambiguous timezone-aware representation.

---

# 52. Response Envelopes

Do not introduce an unnecessary universal response wrapper.

Do not force every endpoint into:

```json
{
  "success": true,
  "data": {}
}
```

unless the existing API already follows that convention.

Resource-specific response shapes are acceptable.

Consistency is more important than artificial uniformity.

---

# 53. Error Contract

Errors MUST be machine-readable and predictable.

Preferred conceptual structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request is invalid.",
    "details": {}
  }
}
```

`code` is intended for programmatic handling.

`message` is safe user-facing/API-facing explanatory text.

`details` may contain structured validation information when safe.

The API MUST NOT expose:

* stack traces
* SQL statements
* internal secrets
* password information
* sensitive infrastructure details

---

# 54. HTTP Error Classes

Use appropriate HTTP status codes.

Typical mapping:

| Status | Meaning                                                                         |
| ------ | ------------------------------------------------------------------------------- |
| `400`  | Malformed/invalid request                                                       |
| `401`  | Authentication required/invalid                                                 |
| `403`  | Authenticated but not authorized                                                |
| `404`  | Resource unavailable/not exposed                                                |
| `409`  | State/conflict/idempotency conflict                                             |
| `422`  | Valid request structure but validation failure, where FastAPI conventions apply |
| `429`  | Rate limit exceeded                                                             |
| `500`  | Unexpected server failure                                                       |

The exact distinction between `400` and `422` must remain consistent with the implemented FastAPI conventions.

---

# 55. Not Found and Authorization Privacy

For sensitive resources, the API may intentionally return `404` instead of revealing that a resource exists.

This is particularly relevant to:

* private profiles
* another user's attempts
* guest sessions
* relationships
* administrative resources

The behavior must be consistent with the security policy.

---

# 56. Rate Limiting

Rate limiting should be applied to operations vulnerable to abuse, including where appropriate:

* registration
* login
* guest session creation
* password-related operations
* attempt submission
* support creation
* generator execution
* privileged administrative actions

Limits are security controls, not business logic.

Do not add an external distributed rate-limiting infrastructure unless actual requirements justify it.

---

# 57. Server Authority

The server is authoritative for:

* user identity
* roles
* capabilities
* ownership
* session state
* session timing
* question validity
* correctness
* chess rules
* scores
* ratings
* rating changes
* XP
* achievements
* streaks
* historical timestamps
* content lifecycle
* administrative authorization

The client MUST NOT be trusted for authoritative values.

Examples of untrusted client values include:

```text
user_id
role
admin
ownership
score
correctness
rating
rating_delta
XP
elapsed_time
server timestamps
content status
```

---

# 58. Chess Authority

For chess-based exercises, the server is authoritative for:

* legal moves
* FEN interpretation
* SAN parsing
* board state
* solution validation
* chess rules

Where `python-chess` is the established implementation mechanism, the server/domain implementation should continue using it rather than trusting client calculations.

---

# 59. API and Domain Separation

Preferred flow:

```text
HTTP Request
    ↓
Pydantic Request DTO
    ↓
Application Command / Query
    ↓
Domain Rules
    ↓
Persistence
    ↓
Application Result
    ↓
Pydantic Response DTO
    ↓
HTTP Response
```

Pydantic API schemas are transport contracts.

They are not automatically domain entities.

Exact layering follows `ARCHITECTURE.md`.

---

# 60. API and Persistence Separation

Routes MUST NOT contain core business logic.

Avoid:

```python
@router.post(...)
def endpoint(...):
    db.add(...)
    db.commit(...)
```

when the operation contains business rules.

Prefer:

```text
Route
  ↓
Application Service / Use Case
  ↓
Domain Rules
  ↓
Repository / Persistence
```

Simple read-only infrastructure may be direct where justified.

Business rules must remain outside route handlers.

---

# 61. API and Content Separation

Content APIs MUST pass through content/application workflows.

They MUST NOT bypass:

* validation
* review
* approval
* publication
* retirement
* audit

through direct database mutation.

---

# 62. API and Rating Separation

Ordinary clients cannot directly modify ratings.

Forbidden:

```http
POST /api/v1/me/ratings
```

with a client-controlled rating delta.

Rating changes originate from authoritative training outcomes or explicitly authorized administrative correction workflows.

Administrative correction, if implemented, must be auditable and preserve historical meaning.

---

# 63. API and Gamification Separation

Clients cannot directly create rewards.

Forbidden:

```http
POST /api/v1/xp
POST /api/v1/achievements/unlock
```

XP, achievements, streaks, and related state result from server-authoritative application workflows.

---

# 64. API and Analytics Separation

Analytics are query/read operations.

Analytics MUST NOT mutate:

* attempts
* ratings
* XP
* achievements
* content
* exercise configuration

Analytics consume authoritative historical facts.

They do not become the source of truth.

---

# 65. Historical Semantics

APIs exposing historical records must represent the historical event rather than silently applying current rules.

For example, an old attempt should not change its:

* score
* correctness
* rating delta
* response time

because current exercise configuration changed.

Historical records are immutable facts unless an explicit correction workflow exists.

---

# 66. Object-Level Authorization

Every resource endpoint must determine whether the caller may access **that specific resource**.

Examples:

```text
/me/...
```

implicitly scopes resources to the current identity.

For resource IDs:

```text
GET /me/training/attempts/{attempt_id}
```

the server MUST verify that the attempt belongs to the caller.

Similarly:

```text
GET /admin/users/{user_id}
GET /coach/students/{student_id}
GET /parent/children/{student_id}
```

require explicit object-level authorization.

Knowing or guessing an identifier is never sufficient authorization.

---

# 67. Capability Authorization

Authorization should use the canonical capability model.

Examples of capabilities may include:

```text
users.read
users.manage
exercises.read
exercises.manage
puzzles.read
puzzles.manage
puzzles.publish
generators.run
analytics.view
support.manage
relationships.manage
```

The canonical capability registry belongs to the authorization/security specification.

This document defines API enforcement, not a second permission registry.

---

# 68. Guest Authorization

Guest access is restricted to explicitly allowed operations.

A guest MUST NOT gain authenticated-user capabilities by manipulating:

* role values
* user IDs
* request bodies
* query parameters
* guest session identifiers

Guest-owned resources must be resolved from the server-controlled guest identity.

---

# 69. Request Validation

All client input is untrusted.

Validate:

* type
* structure
* allowed values
* length
* range
* format
* resource ownership
* state transitions
* business constraints

Validation must occur at the appropriate API and domain boundaries.

Client-side validation is UX only.

---

# 70. Idempotency

Operations with duplicate/replay risk SHOULD use idempotency.

Mandatory or expected examples include:

* training attempt submission
* guest migration
* generator runs where duplicate execution is dangerous
* other high-impact actions when specified by their domain

Idempotency must be scoped to the caller and operation.

An idempotency key must never become an authorization mechanism.

---

# 71. API State Transitions

APIs that change lifecycle state should use explicit domain actions where arbitrary field mutation would be unsafe.

Examples:

```text
suspend
reactivate
publish
retire
approve
reject
close
```

Avoid:

```http
PATCH /resource/{id}
```

with an unrestricted:

```json
{
  "status": "anything"
}
```

when state transitions have business rules.

---

# 72. API Security Boundary

Every API request is untrusted.

The backend MUST derive authoritative values from:

* authenticated identity
* session state
* server-side resource ownership
* domain rules
* stored authoritative data

The backend MUST NOT trust client claims of:

```text
identity
role
ownership
admin status
score
rating
XP
correctness
elapsed time
content state
```

---

# 73. Admin Security

Every admin endpoint independently checks backend authorization.

This is insufficient:

```text
if frontend_path.startswith("/admin"):
    allow
```

Frontend route guards are UX controls only.

Admin actions must use backend capability checks and object-level authorization.

Sensitive actions should produce audit records.

---

# 74. Relationship Security

Coach/student and parent/student APIs require:

```text
authenticated identity
+
appropriate capability
+
active relationship
+
object authorization
+
privacy rules
```

A relationship does not provide unrestricted access.

Revoked relationships must lose ordinary ongoing access.

---

# 75. Privacy Boundary

API responses must expose the minimum information necessary for the operation.

Do not expose personal information merely because it exists in the database.

Particularly sensitive information includes:

* credentials
* authentication tokens
* private contact data
* private notes
* unrelated users' training data
* hidden puzzle answers
* internal security metadata

Detailed privacy rules belong in `SECURITY.md`.

---

# 76. File and Media References

Where APIs expose files/media, responses should use safe server-controlled references.

The client must not be able to:

* choose arbitrary filesystem paths
* access another user's private file
* bypass authorization through predictable URLs

Private media must follow the security architecture rather than being exposed as unrestricted static files.

---

# 77. API and Frontend Compatibility

The React frontend is a client of the API.

Frontend assumptions must not silently become backend contracts.

When changing an API:

1. inspect frontend usage
2. inspect backend usage
3. update schemas
4. update tests
5. update client code
6. verify backward compatibility where required

Do not break the existing exercise client while introducing platform functionality.

---

# 78. OpenAPI

The implemented FastAPI/OpenAPI schema must reflect the actual implementation.

Implemented endpoints should document, where applicable:

* authentication requirements
* request schema
* response schema
* status codes
* authorization requirements
* validation constraints
* important business rules
* error responses

Generated OpenAPI is the implementation-level API reference.

This document remains the target/product-level API contract.

The two must not knowingly contradict each other.

---

# 79. API Testing Requirements

Important API contracts require automated tests.

## Authentication

Test:

* registration
* duplicate username
* login
* invalid credentials
* logout
* protected endpoint access

## Guest

Test:

* guest session creation
* guest ownership
* guest training
* migration
* migration idempotency
* migration authorization
* expired guest session behavior

## Training

Test:

* valid attempt
* invalid answer
* wrong session
* wrong question instance
* unauthorized question instance
* duplicate submission
* idempotent retry
* expired speed session
* hidden-answer protection
* server-authoritative timing

## Ratings

Test:

* rating update
* rating history
* unauthorized modification
* duplicate attempt does not duplicate rating change

## Gamification

Test:

* XP award
* achievement unlock
* duplicate reward prevention
* client cannot award XP

## Administration

Test:

* admin access
* non-admin rejection
* capability enforcement
* object-level authorization
* state transitions
* audit creation
* self-protection rules

## Relationships

Test:

* active relationship access
* revoked relationship rejection
* object-level authorization
* privacy restrictions

---

# 80. API Implementation Rules

When implementing an endpoint, the agent MUST:

1. inspect existing route conventions
2. inspect existing schema conventions
3. inspect existing application services
4. inspect existing frontend consumers
5. identify the authoritative domain rule
6. implement the smallest coherent change
7. add meaningful tests
8. verify authorization
9. verify error behavior
10. verify API documentation/OpenAPI
11. avoid unrelated refactoring

Do not create a new abstraction merely because a future phase might use it.

---

# 81. Phase Scope

API capabilities follow the Master Plan.

### Phase 1

Foundation and API conventions required by later phases.

### Phase 2

Authentication, sessions, guest identity, roles, capabilities.

### Phase 3

Player profile, external identities, dashboard, progress, basic player summaries.

### Phase 4

Exercise ratings and rating history.

### Phase 5

Gamification APIs.

### Phase 6

Administration foundation, users, roles, account status, operational dashboard, support.

### Phase 7

Content lifecycle, puzzle management, generators, publishing.

### Phase 8

Full player/exercise/puzzle/platform analytics.

### Phase 9

Coach/student and parent/student APIs.

### Phase 10

Adaptive-training foundations and recommendation APIs where required.

This document does not authorize implementing future-phase APIs early.

---

# 82. No Speculative API Surface

Do not create endpoints merely because they may eventually be useful.

Examples:

```text
Do not create ML endpoints before adaptive training requires them.
Do not create notification APIs merely because notifications may exist later.
Do not create organization APIs without a product requirement.
Do not create payment APIs because monetization may be added later.
Do not create generic event APIs to connect unrelated domains.
```

The rule is:

> **Documented API ≠ implemented API.**

Only active-phase requirements and justified dependencies create implementation work.

---

# 83. API Completeness

An API capability is complete only when all required layers are implemented:

```text
Contract
  ↓
Schema
  ↓
Authorization
  ↓
Application behavior
  ↓
Persistence
  ↓
Frontend integration where applicable
  ↓
Tests
  ↓
OpenAPI accuracy
  ↓
Runtime verification
```

An endpoint existing in the router is not sufficient evidence of completion.

---

# 84. Final API Principles

The MicroChess API should remain:

```text
Explicit
Secure
Server-authoritative
Domain-aware
Versionable
Testable
Minimal
Consistent
```

The API must support the complete MicroChess product without becoming a second business-logic layer or a speculative abstraction framework.

The preferred direction is:

```text
Thin API
    ↓
Application Use Case
    ↓
Domain Rules
    ↓
Authoritative Data
```

The implementation should optimize for:

```text
Correctness
+
Security
+
Completeness
+
Maintainability
+
Low unnecessary complexity
```
