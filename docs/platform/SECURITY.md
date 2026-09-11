# MicroChess Platform Security

## 1. Purpose

This document defines the security architecture and security requirements for the MicroChess platform.

It covers:

* authentication
* sessions
* guest users
* account migration
* passwords
* authorization
* roles and permissions
* object-level access control
* player privacy
* child/teen safety
* admin security
* API security
* input validation
* output safety
* file handling
* rate limiting
* abuse prevention
* audit logging
* sensitive data
* analytics privacy
* security testing
* future authentication features

This document defines the target security model.

Before implementation, the agent MUST inspect the existing repository and preserve secure existing mechanisms where appropriate.

---

# 2. Security Principles

MicroChess follows these principles:

1. Server authority
2. Least privilege
3. Deny by default
4. Defense in depth
5. Explicit authorization
6. Object-level authorization
7. Secure defaults
8. Minimal data collection
9. Minimal data exposure
10. Privacy by design
11. Auditability
12. Fail safely
13. Validate untrusted input
14. Never trust client-calculated business state
15. Prefer simple security mechanisms over unnecessary complexity

Authorization is distinct from authentication and must be enforced for the specific resource/action being requested.

---

# 3. Threat Model

MicroChess is primarily a browser-based educational application.

Relevant threats include:

* account takeover
* password brute force
* credential stuffing
* session theft
* session fixation
* privilege escalation
* IDOR/BOLA
* unauthorized admin access
* malicious puzzle submissions
* cheating through API manipulation
* score/rating/XP manipulation
* guest-session abuse
* guest migration abuse
* spam
* automated account creation
* analytics scraping
* sensitive-data leakage
* malicious file uploads
* XSS
* CSRF where applicable
* SQL injection
* command injection
* SSRF where applicable
* denial of service
* replay of state-changing requests
* abuse of expensive generators
* abuse of support endpoints
* privacy violations involving minors

---

# 4. Security Boundary

The browser is untrusted.

Anything received from the browser may be manipulated.

Never trust:

```text
user_id
role
is_admin
score
rating
rating_delta
XP
achievement
correctness
elapsed_time
session_state
puzzle_solution
exercise_state
ownership
```

The server must derive authoritative values.

---

# 5. Authentication vs Authorization

Authentication answers:

> Who is this?

Authorization answers:

> What is this identity allowed to do?

A successful login does not grant access to every resource.

For example:

```text
Player
≠
Admin
```

and:

```text
Coach
≠
Owner of every student account
```

---

# 6. Initial Registration Model

Initial registration requires only:

```text
username
password
```

The system must not require:

* email
* phone number
* real name
* FIDE ID
* Lichess account
* Chess.com account

These can be added later.

This minimizes unnecessary personal-data collection.

---

# 7. Username Security

Usernames must:

* have a defined maximum length
* have a defined minimum length
* use a controlled character set
* be normalized consistently
* be unique according to documented rules

The system must define whether usernames are case-sensitive.

Preferred behavior:

```text
Omid
omid
OMID
```

should not accidentally create multiple visually equivalent identities.

The exact normalization rule must be established once and reused everywhere.

---

# 8. Password Storage

Passwords must never be stored in plaintext.

The system must use a password hashing algorithm designed for password storage.

Preferred choices may include:

* Argon2id
* bcrypt
* another established password-hashing implementation supported by the selected authentication stack

Do not implement password hashing manually.

OWASP recommends secure password storage and safe password-hash comparison rather than plaintext or reversible storage.

---

# 9. Password Policy

The system should prioritize strong passwords without creating unreasonable usability barriers.

Requirements:

* minimum length
* reasonable maximum length
* no silent truncation
* reject obviously invalid input
* never log passwords
* never return passwords in API responses

Password strength rules must be documented and tested.

---

# 10. Login Security

Login must protect against:

* brute force
* credential stuffing
* password spraying
* username enumeration

Authentication endpoints require stronger abuse controls than ordinary low-risk endpoints.

OWASP specifically recommends anti-brute-force protections and stricter controls for authentication endpoints.

---

# 11. Authentication Error Messages

Login failures should not reveal unnecessary account existence information.

Avoid responses such as:

```text
Username does not exist.
```

or:

```text
Username exists but password is incorrect.
```

Prefer a generic authentication failure.

This reduces username enumeration risk.

---

# 12. Authentication Rate Limiting

Rate limiting should apply to:

```text
registration
login
password reset
password change
account recovery
```

where applicable.

The exact thresholds must be configurable.

Do not hard-code arbitrary limits throughout route handlers.

---

# 13. Session Security

The session mechanism must provide:

* unpredictable session identifiers
* server-side validation
* expiration
* logout invalidation
* appropriate cookie attributes where cookies are used
* protection against session fixation
* secure transport

OWASP recommends unique, difficult-to-predict session identifiers and secure session management.

---

# 14. HTTPS

Production authentication and authenticated traffic must use HTTPS.

Sensitive data must not be transmitted over plaintext HTTP.

TLS protects credentials, sessions and data in transit.

HTTP should redirect to HTTPS where appropriate.

---

# 15. Secure Cookies

If browser sessions use cookies, production cookies should use appropriate attributes such as:

```text
Secure
HttpOnly
SameSite
```

The exact SameSite policy depends on the final deployment architecture.

Session cookies must not be accessible to normal JavaScript unless there is a documented architectural reason.

---

# 16. Session Expiration

Authenticated sessions require an expiration policy.

The policy should distinguish:

```text
idle timeout
absolute timeout
```

where appropriate.

The exact durations should be configurable rather than scattered throughout the application.

---

# 17. Logout

Logout must invalidate the relevant authenticated session.

Logging out from one session must not accidentally delete unrelated users or sessions.

Future multi-device session management may allow:

```text
current session
all sessions
individual sessions
```

but this is not required for the first implementation.

---

# 18. Sensitive Operations

Future sensitive operations should support re-authentication where appropriate.

Examples:

* password change
* account recovery
* adding authentication factors
* changing critical account credentials
* destructive administrative operations

OWASP recommends re-authentication for sensitive account changes and risk events.

---

# 19. Future Authentication

The architecture should allow future addition of:

* password reset
* email verification
* MFA
* passkeys
* OAuth/OIDC
* social login
* account recovery

These are future capabilities.

Do not add them prematurely if the current product does not need them.

---

# 20. Roles

Initial target roles:

```text
Player
Coach
Parent
Admin
```

Guest is not an authenticated role.

It is an unauthenticated/temporary identity state.

---

# 21. Role-Based Access Control

Roles provide coarse-grained permissions.

Example:

```text
Player
Coach
Parent
Admin
```

But roles alone are not sufficient.

Object-level and relationship-level authorization must also be enforced.

---

# 22. Deny by Default

If an endpoint does not explicitly allow an operation, access must be denied.

Do not implement:

```text
if user is not admin:
    reject
```

only for some sensitive endpoints.

Every protected capability must define its authorization requirement.

---

# 23. Permission Model

The architecture should support permissions more granular than roles.

Conceptually:

```text
users.read
users.manage
exercises.manage
puzzles.create
puzzles.review
puzzles.publish
generators.run
analytics.view
audit.view
support.manage
```

The initial implementation may map permissions to roles.

Do not create an unnecessarily complex policy engine.

---

# 24. Admin Security

Admin capabilities are high risk.

Administrative operations must require:

1. authentication
2. admin authorization
3. object-level checks where relevant
4. audit logging for sensitive state changes

Frontend route protection is never sufficient.

---

# 25. Admin API Protection

A request to:

```text
/api/v1/admin/*
```

must be authorized server-side.

A malicious user must not gain admin access by:

* changing a frontend route
* modifying a request body
* adding `is_admin=true`
* changing a role field
* manipulating local storage

---

# 26. Object-Level Authorization

Every resource access must be checked against the specific object.

Example:

```text
GET /me/training/attempts/123
```

must verify that attempt `123` belongs to the current user.

It is not enough that:

```text
current_user.role == "player"
```

Object-level authorization is essential against IDOR/BOLA-style attacks. OWASP recommends checking access to the specific object on every request.

---

# 27. Coach Authorization

A coach may access a student's data only when an appropriate relationship exists.

This is invalid:

```text
Coach role
→
all student data
```

Correct:

```text
Coach
  ↓
Active relationship
  ↓
Specific student
  ↓
Allowed data scope
```

---

# 28. Parent Authorization

A parent may access a child's permitted data only through an explicit parent/student relationship.

Parent access must not imply:

* admin access
* access to unrelated students
* access to private administrative data
* unrestricted account control

---

# 29. Relationship Revocation

When a coach/student or parent/student relationship ends:

```text
relationship = inactive
```

access granted solely by that relationship must stop.

Historical records may remain available according to privacy and retention policy.

---

# 30. Player Privacy

Players should control appropriate profile visibility.

Potential visibility levels:

```text
private
public
limited
```

The exact policy should be defined by the profile specification.

Private profile data must not appear in:

* leaderboards
* public profiles
* analytics
* coach views
* parent views

unless authorized.

---

# 31. Child and Teen Privacy

MicroChess is child-first.

Therefore the platform must minimize unnecessary collection of personal information.

Do not require:

* real name
* address
* phone
* email

for initial account creation.

The system should avoid exposing personal information through:

* usernames
* leaderboards
* public profiles
* analytics
* support
* coach relationships

---

# 32. External Chess Identities

FIDE, Lichess and Chess.com identities are optional.

External ratings must be clearly distinguished from MicroChess ratings.

Example:

```text
Lichess Rapid: 2050
MicroChess Pin Rating: 1478
```

The system must never silently interpret an external rating as an authoritative MicroChess rating.

---

# 33. External Identity Verification

Initially:

```text
self-reported
```

is acceptable.

Future verification may be introduced.

The client must never be able to set:

```text
verified = true
```

directly.

Verification must be performed by an authoritative server-side process.

---

# 34. Guest Security

Guests must receive only temporary capabilities.

Guest sessions must have:

* expiration
* limited privileges
* limited data exposure
* abuse controls

Guests must not access:

* admin
* private player profiles
* other users' history
* privileged analytics

---

# 35. Guest Migration Security

Guest migration is security-sensitive.

The migration process must ensure:

1. guest session belongs to the requester
2. guest session is valid
3. migration occurs only once
4. data is not duplicated
5. rewards are not duplicated
6. another user's guest data cannot be claimed
7. migration is atomic where required

---

# 36. Guest Data Ownership

Guest data must be associated with a server-generated guest identity.

Never trust a client-supplied:

```text
guest_user_id
```

as proof of ownership.

A guest identifier is an identifier, not an authorization credential.

---

# 37. Training Integrity

A player must not be able to manipulate:

```text
correctness
score
rating
XP
achievement progress
session duration
```

through request payloads.

The server evaluates the answer.

---

# 38. Puzzle Answer Protection

Hidden puzzle answers must never be sent to the browser before the player submits an answer.

This includes:

* direct answer fields
* hidden JSON
* HTML attributes
* JavaScript variables
* source maps
* API metadata

If the browser receives the answer, client-side hiding is not security.

---

# 39. Exercise Security

Exercise validation must happen server-side.

For example:

```text
Pin
```

must not trust the React client to determine whether three selected squares constitute a valid pin.

The server validates the exercise-specific answer.

---

# 40. Speed Mode Security

The browser may display:

```text
60
59
58
...
```

but the server determines whether the session has expired.

A malicious client must not be able to submit:

```text
elapsed_time = 2
```

and thereby bypass a 60-second deadline.

---

# 41. Rating Security

Rating changes are generated by server-side rating logic.

Forbidden:

```json
{
  "rating": 2500
}
```

as an instruction to set the rating.

The client may display a rating but does not own the rating state.

---

# 42. Gamification Security

XP, achievements, streaks and milestones must be derived from authoritative events.

Never expose an endpoint equivalent to:

```text
POST /me/xp
```

where the client chooses the amount.

---

# 43. Replay Protection

State-changing requests that can produce rewards or historical records must protect against replay.

Especially:

* attempt submission
* guest migration
* achievement awarding
* generator execution
* administrative lifecycle actions

Idempotency keys or server-side unique constraints should be used where appropriate.

---

# 44. Transaction Integrity

Operations that update multiple authoritative records should use appropriate transaction boundaries.

For example, a successful training attempt may affect:

```text
attempt
rating
rating event
XP event
achievement progress
streak
analytics facts
```

The system must define which updates are atomic and which can be derived asynchronously.

The user must never receive a misleading success response if the core authoritative operation failed.

---

# 45. Analytics Integrity

Analytics should be derived from authoritative records.

Do not trust:

```text
client analytics
client counters
client activity totals
```

as source-of-truth data.

Raw historical facts should remain available for recalculation.

---

# 46. Audit Logging

Security-sensitive administrative events should be auditable.

Examples:

```text
login failures
role changes
account suspension
account reactivation
admin puzzle changes
puzzle publication
puzzle retirement
generator runs
permission changes
support administrative actions
```

Audit records should include useful context such as:

```text
actor
action
target
timestamp
result
request/context metadata where appropriate
```

Never log passwords, tokens or secrets.

---

# 47. Authentication Logging

Authentication events worth monitoring include:

* successful login
* failed login
* logout
* password change
* password recovery
* account lockout
* suspicious authentication activity

OWASP recommends logging authentication failures and monitoring authentication functions.

---

# 48. Security Event Logging

Security logs should help answer:

> Who did what, to which object, when, and whether it succeeded?

Logs must not become a secondary database containing unnecessary personal information.

---

# 49. Log Injection

Never concatenate untrusted user input directly into structured security logs without safe encoding.

Usernames, support messages and search strings may contain malicious characters.

---

# 50. Secrets

Secrets must never be committed to Git.

Examples:

```text
database passwords
session secrets
API keys
OAuth secrets
encryption keys
admin bootstrap secrets
```

Use environment/configuration mechanisms appropriate to the deployment.

---

# 51. Environment Separation

Development, testing and production credentials must be separate.

Never reuse production secrets in tests.

Never commit production credentials to:

```text
.env
source code
tests
fixtures
documentation
```

---

# 52. Database Security

The application database user should have only the permissions required by the application.

The application must not rely on a database superuser in production.

SQL injection protection must come from:

* parameterized queries
* ORM/query-builder mechanisms
* strict input validation

Never construct SQL using raw string interpolation from user input.

---

# 53. Input Validation

All external input must be validated.

Sources include:

* JSON
* query parameters
* path parameters
* form fields
* uploaded files
* headers
* cookies
* external provider data

Validation must happen before business logic.

---

# 54. Schema Validation

Pydantic models should define API request schemas where appropriate.

Validation should include:

* type
* length
* range
* enum
* required/optional status
* nested structure

Do not rely solely on frontend validation.

---

# 55. Business Validation

Schema validation is not enough.

Example:

```text
rating = integer
```

may be syntactically valid while:

```text
rating = -500
```

is business-invalid.

Business rules belong in the application/domain layer.

---

# 56. Output Encoding

User-controlled text must be safely rendered.

Potential sources include:

* display names
* bios
* support messages
* admin notes
* puzzle metadata

Do not inject raw user content into HTML.

React's normal escaping behavior should be preserved.

Avoid unsafe HTML rendering unless explicitly required and safely sanitized.

---

# 57. XSS

The system must protect against:

* stored XSS
* reflected XSS
* DOM-based XSS

Particular attention is required for:

* bios
* support messages
* admin content
* generated content metadata

---

# 58. CSRF

The final CSRF strategy depends on the authentication transport.

If authentication uses browser cookies, state-changing requests must have appropriate CSRF protection.

If a different architecture is used, document why CSRF protection is or is not required.

Do not simply disable CSRF because the frontend is React.

---

# 59. CORS

CORS must be explicitly configured.

Do not use:

```text
allow_origins = *
```

for authenticated production APIs unless there is a documented security reason.

Allowed origins should match the actual deployment architecture.

---

# 60. HTTP Methods

Only supported methods should be enabled for each endpoint.

Unexpected methods should be rejected.

REST security guidance recommends restricting allowed HTTP methods rather than allowing arbitrary method behavior.

---

# 61. Request Size Limits

The API should enforce reasonable request-size limits.

This protects against:

* memory exhaustion
* oversized JSON
* malicious uploads
* accidental huge payloads

---

# 62. File Upload Security

Future profile/avatar/file uploads must be treated as untrusted.

Controls should include:

* file-size limits
* allowed MIME types
* extension validation
* content validation
* safe filenames
* non-executable storage
* controlled download behavior

Never trust only the filename extension.

---

# 63. Avatar Security

Avatars should not be stored as executable files.

Prefer normalized server-generated filenames.

The original user filename should not become the storage path.

---

# 64. Static File Security

Private files must not be placed in a publicly accessible static directory.

If a file is private:

```text
request
 ↓
authorization
 ↓
controlled file response
```

not:

```text
/public/uploads/private-file
```

---

# 65. Path Traversal

User-controlled filenames or paths must never directly determine filesystem paths.

Reject or safely normalize:

```text
../
..\ 
absolute paths
```

and equivalent traversal patterns.

---

# 66. Generator Security

Puzzle generators may be computationally expensive.

Admin generator endpoints require:

* authorization
* parameter validation
* resource limits
* run tracking
* cancellation where supported
* audit logging

Do not allow an untrusted user to trigger unlimited generation.

---

# 67. Background Jobs

If expensive work becomes asynchronous, jobs must have:

* authenticated creator
* authorization
* unique ID
* status
* resource limits
* failure handling
* auditability

Do not introduce a message broker merely because background jobs exist.

Use the simplest infrastructure appropriate to actual scale.

---

# 68. SSRF

If future features fetch external URLs, such as:

* external profile verification
* imported content
* remote images

the implementation must explicitly defend against SSRF.

Never blindly fetch arbitrary user-supplied URLs from the server.

---

# 69. External Provider Data

Data from FIDE, Lichess, Chess.com or other external providers is untrusted input.

Validate:

* schema
* size
* identifiers
* expected values

before storing or using it.

---

# 70. API Enumeration Protection

Sensitive resources must not be accessible merely because a user can guess IDs.

Object authorization must remain mandatory.

Random IDs may reduce guessing probability, but they do not replace authorization. OWASP explicitly warns against relying on identifier obscurity as the primary protection.

---

# 71. Privacy-Preserving Analytics

Analytics should expose only the data necessary for the intended viewer.

For example:

### Player

Own detailed analytics.

### Coach

Only authorized student analytics.

### Parent

Only authorized child information.

### Admin

Broader operational analytics, subject to privacy policy.

### Public

Only intentionally public aggregate/profile information.

---

# 72. Leaderboard Privacy

Leaderboards must not automatically reveal personal information.

Possible public fields:

```text
display name
avatar
score/rating
rank
```

only where permitted.

Avoid exposing:

* real name
* email
* private profile information
* detailed training history

---

# 73. Account Deletion

The architecture must eventually support account deletion or anonymization.

Deletion must distinguish between:

```text
personal identity data
historical training facts
aggregate analytics
audit records
legal/security retention
```

Historical educational statistics may need anonymization rather than unrestricted deletion.

The exact retention policy must be defined before implementing destructive deletion.

---

# 74. Data Retention

Do not retain personal information indefinitely without purpose.

Different categories may have different retention rules:

```text
sessions
support tickets
training history
analytics
audit logs
external identities
```

Retention policies should be configurable where appropriate.

---

# 75. Data Export

A future player-facing data export capability should allow a user to retrieve appropriate personal data.

The architecture should not make export impossible by scattering user information across opaque uncontrolled structures.

---

# 76. Security Headers

Production web responses should use appropriate browser security headers.

Potential controls include:

* Content-Security-Policy
* X-Content-Type-Options
* Referrer-Policy
* frame-ancestors / clickjacking protection
* Strict-Transport-Security where appropriate

Exact policy must be compatible with the frontend architecture.

---

# 77. Dependency Security

Dependencies should be:

* pinned or constrained appropriately
* periodically reviewed
* updated deliberately
* checked for known vulnerabilities

Do not blindly upgrade the entire dependency tree during unrelated feature work.

---

# 78. Database Migrations

Security-sensitive schema changes must use the project's migration system.

Never manually alter production schema in an undocumented way.

Migration changes must be:

* reviewable
* reversible where practical
* tested
* compatible with deployment order

---

# 79. Authorization Testing

Authorization tests are mandatory for important protected resources.

At minimum test:

```text
player → own resource
player → another player's resource
coach → assigned student
coach → unrelated student
parent → own child
parent → unrelated child
admin → privileged resource
non-admin → admin resource
```

The goal is to test denial as well as success.

---

# 80. Security Testing Priorities

High-value tests include:

### Authentication

* invalid credentials
* brute-force controls
* session invalidation

### Authorization

* horizontal privilege escalation
* vertical privilege escalation
* object-level access

### Training integrity

* forged score
* forged rating
* forged XP
* forged correctness
* expired session
* duplicate submission

### Guest

* guest takeover
* duplicate migration
* expired migration
* cross-session migration

### Admin

* non-admin access
* role manipulation
* lifecycle bypass

### Input

* invalid schemas
* oversized requests
* injection attempts
* malicious filenames

---

# 81. Security and Error Handling

Production error responses must not expose:

* stack traces
* SQL statements
* filesystem paths
* secrets
* internal architecture unnecessarily

Detailed diagnostics belong in protected server logs.

---

# 82. Fail Closed

When authorization information is missing or ambiguous:

```text
deny
```

Do not assume permission.

Examples:

```text
missing relationship → deny
unknown role → deny
invalid session → deny
missing ownership → deny
unknown lifecycle state → deny
```

---

# 83. Workflow Security

Important workflows must be validated server-side.

Example puzzle lifecycle:

```text
Draft
 ↓
Validated
 ↓
Reviewed
 ↓
Approved
 ↓
Published
 ↓
Retired
```

An attacker must not be able to skip directly from:

```text
Draft → Published
```

by calling the publication endpoint.

OWASP specifically recommends server-side workflow-state validation to prevent out-of-order execution.

---

# 84. Security of Content Generation

Generated content is untrusted until validated.

Pipeline:

```text
Generator
 ↓
Generated
 ↓
Validation
 ↓
Review
 ↓
Approval
 ↓
Publication
```

Generation itself does not imply correctness.

---

# 85. Security of Analytics

Analytics queries must be protected against:

* unauthorized data access
* expensive unrestricted queries
* cross-user leakage
* arbitrary filtering abuse

Admin analytics may require pagination, aggregation and query limits.

---

# 86. Security of Future Adaptive Training

Future recommendation systems must not become an authorization bypass.

Recommendations may use:

* training history
* ratings
* accuracy
* response time
* difficulty

but must respect privacy and authorization boundaries.

---

# 87. No Premature Security Infrastructure

Do not introduce:

* microservice identity providers
* external IAM platforms
* service meshes
* message brokers
* complex policy engines

unless actual product scale or security requirements justify them.

A modular monolith can provide strong security when its boundaries are enforced correctly.

---

# 88. Security Architecture

Target flow:

```text
Browser
   ↓
HTTPS
   ↓
API
   ↓
Authentication
   ↓
Authorization
   ↓
Input Validation
   ↓
Application Service
   ↓
Domain Rules
   ↓
Repository
   ↓
Database
```

For protected resources:

```text
Authentication
      ↓
Role/Permission Check
      ↓
Object/Relationship Check
      ↓
Business Rule Check
      ↓
Operation
```

---

# 89. Security Invariants

The following rules are mandatory.

### Invariant 1

Passwords are never stored in plaintext.

### Invariant 2

Passwords are never logged.

### Invariant 3

Sessions are unpredictable and securely managed.

### Invariant 4

Every protected API operation performs authorization.

### Invariant 5

Object ownership is checked server-side.

### Invariant 6

Roles are not trusted when supplied by the client.

### Invariant 7

Scores are not trusted from the client.

### Invariant 8

Ratings are not trusted from the client.

### Invariant 9

XP is not trusted from the client.

### Invariant 10

Puzzle answers are not exposed to players before submission.

### Invariant 11

Guest migration cannot duplicate rewards or history.

### Invariant 12

Admin operations are auditable.

### Invariant 13

Private files are not publicly accessible.

### Invariant 14

Analytics do not bypass privacy rules.

### Invariant 15

Invalid authorization state fails closed.

### Invariant 16

Content lifecycle transitions are enforced server-side.

### Invariant 17

Security-sensitive state changes cannot be performed solely through frontend controls.

---

# 90. Implementation Rules

Before implementing security-related features:

1. Inspect existing authentication.
2. Inspect session implementation.
3. Inspect existing middleware/dependencies.
4. Inspect current user model.
5. Inspect current API authorization.
6. Inspect database constraints.
7. Inspect frontend auth state.
8. Identify existing security mechanisms.
9. Preserve correct existing mechanisms.
10. Replace insecure mechanisms deliberately.
11. Add meaningful security tests.
12. Document important decisions.

Do not rewrite authentication or authorization merely for stylistic reasons.

---

# 91. Security Definition of Done

A platform security feature is complete only when:

* authentication behavior is defined
* authorization behavior is defined
* object-level access is enforced where required
* sensitive values are server-authoritative
* invalid input is rejected
* important abuse cases are considered
* errors do not leak sensitive internals
* security-sensitive actions are auditable
* meaningful security tests exist
* frontend restrictions are backed by backend restrictions
* documentation matches implementation

---

# 92. Final Security Principle

The platform must assume:

> **The browser, the network request, and every client-provided value can be manipulated.**

Therefore:

```text
Authenticate the identity.
Authorize the action.
Authorize the object.
Validate the input.
Apply the business rule.
Persist the authoritative result.
Audit sensitive operations.
Expose only what the caller is allowed to know.
```

Security is not a frontend feature.

Security is a property of the complete system.

# 93. Concrete Security Decision Matrix

This matrix is normative.

When implementing a feature, the agent must use this matrix as the default authorization decision unless a more specific domain specification explicitly overrides it.

The client UI must never be treated as the source of authorization truth.

## 93.1 Access Decision Model

Every protected operation follows:

```text
Request
  ↓
Is the session authenticated?
  ├─ No → Public/Guest rule
  └─ Yes
       ↓
Is the account active?
  ├─ No → DENY
  └─ Yes
       ↓
Does the role have the required capability?
  ├─ No → DENY
  └─ Yes
       ↓
Does the user have access to this specific object?
  ├─ No → DENY
  └─ Yes
       ↓
Are relationship/state/business conditions satisfied?
  ├─ No → DENY
  └─ Yes → ALLOW
```

Authorization must be checked on every protected request and must fail closed.

---

## 93.2 Role Capability Matrix

| Capability                             |       Guest |      Player |        Coach |            Parent | Admin |
| -------------------------------------- | ----------: | ----------: | -----------: | ----------------: | ----: |
| Browse public exercises                |       ALLOW |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| Start public practice                  |       ALLOW |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| Start public speed session             |       ALLOW |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| Submit training attempt                |      ALLOW* |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| View own training history              |   TEMPORARY |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| View own rating                        |   TEMPORARY |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| View own analytics                     |   TEMPORARY |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| View own achievements                  |   TEMPORARY |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| Manage own profile                     |        DENY |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| Manage own password                    |        DENY |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| Manage own external chess identities   |        DENY |       ALLOW |        ALLOW |             ALLOW | ALLOW |
| View another player's profile          | PUBLIC-ONLY | PUBLIC-ONLY |  PUBLIC-ONLY |       PUBLIC-ONLY | ALLOW |
| View another player's detailed history |        DENY |        DENY | RELATIONSHIP |      RELATIONSHIP | ALLOW |
| View another player's analytics        |        DENY |        DENY | RELATIONSHIP |      RELATIONSHIP | ALLOW |
| Manage student assignments             |        DENY |        DENY | RELATIONSHIP |              DENY | ALLOW |
| Manage parent/child relationship       |        DENY |        DENY |         DENY | SELF/RELATIONSHIP | ALLOW |
| Access admin dashboard                 |        DENY |        DENY |         DENY |              DENY | ALLOW |
| Manage users                           |        DENY |        DENY |         DENY |              DENY | ALLOW |
| Manage roles                           |        DENY |        DENY |         DENY |              DENY | ALLOW |
| Manage exercises                       |        DENY |        DENY |         DENY |              DENY | ALLOW |
| Manage puzzles                         |        DENY |        DENY |         DENY |              DENY | ALLOW |
| Run generators                         |        DENY |        DENY |         DENY |              DENY | ALLOW |
| Publish content                        |        DENY |        DENY |         DENY |              DENY | ALLOW |
| View platform analytics                |        DENY |        DENY |         DENY |              DENY | ALLOW |
| View audit logs                        |        DENY |        DENY |         DENY |              DENY | ALLOW |
| Manage support requests                |        DENY |        DENY |         DENY |              DENY | ALLOW |

`*` Guest submissions are permitted only within the guest-session rules and must not grant access to another user's data.

---

## 93.3 Resource-Level Decision Matrix

### Player-owned resources

| Resource         |          Guest | Owner |                        Other Player |                                  Coach |                      Parent | Admin |
| ---------------- | -------------: | ----: | ----------------------------------: | -------------------------------------: | --------------------------: | ----: |
| Profile          |      Temporary | ALLOW |                  PUBLIC fields only |                  PUBLIC/allowed fields |       PUBLIC/allowed fields | ALLOW |
| Training Attempt | Own guest only | ALLOW |                                DENY |                  Assigned student only |                  Child only | ALLOW |
| Training Session | Own guest only | ALLOW |                                DENY |                  Assigned student only |                  Child only | ALLOW |
| Rating           | Own guest only | ALLOW |      PUBLIC summary only if enabled |                       Assigned student |                       Child | ALLOW |
| Rating History   | Own guest only | ALLOW |                                DENY |                       Assigned student |                       Child | ALLOW |
| Analytics        | Own guest only | ALLOW |                                DENY |                       Assigned student |                       Child | ALLOW |
| Achievements     | Own guest only | ALLOW | Public achievements only if enabled |                       Assigned student |                       Child | ALLOW |
| Personal Goals   | Own guest only | ALLOW |                                DENY | Assigned student if explicitly allowed | Child if explicitly allowed | ALLOW |

---

## 93.4 Public vs Private Profile Fields

The API must explicitly control field visibility.

| Field              |              Owner |               Public |                           Coach |                          Parent |                     Admin |
| ------------------ | -----------------: | -------------------: | ------------------------------: | ------------------------------: | ------------------------: |
| Username           |              ALLOW | Depending on privacy |                           ALLOW |                           ALLOW |                     ALLOW |
| Display name       |              ALLOW | Depending on privacy |                           ALLOW |                           ALLOW |                     ALLOW |
| Avatar             |              ALLOW | Depending on privacy |                           ALLOW |                           ALLOW |                     ALLOW |
| Bio                |              ALLOW | Depending on privacy |                           ALLOW |                           ALLOW |                     ALLOW |
| FIDE ID            |              ALLOW |      DENY by default |                    If permitted |                    If permitted |                     ALLOW |
| FIDE username      |              ALLOW | If explicitly public |                    If permitted |                    If permitted |                     ALLOW |
| FIDE rating        |              ALLOW | If explicitly public |                    If permitted |                    If permitted |                     ALLOW |
| Lichess username   |              ALLOW | If explicitly public |                    If permitted |                    If permitted |                     ALLOW |
| Lichess rating     |              ALLOW | If explicitly public |                    If permitted |                    If permitted |                     ALLOW |
| Chess.com username |              ALLOW | If explicitly public |                    If permitted |                    If permitted |                     ALLOW |
| Chess.com rating   |              ALLOW | If explicitly public |                    If permitted |                    If permitted |                     ALLOW |
| Email              |              ALLOW |                 DENY | DENY unless explicitly required | DENY unless explicitly required |                     ALLOW |
| Phone              |              ALLOW |                 DENY |                            DENY |                            DENY | ALLOW only when necessary |
| Internal IDs       | ALLOW where needed |                 DENY |                            DENY |                            DENY |        ALLOW where needed |

The implementation must not serialize the complete user object and rely on the frontend to hide fields.

Field-level authorization is required for sensitive attributes.

---

## 93.5 Relationship Authorization Matrix

Relationship-based access is required for Coach and Parent functionality.

| Relationship             | Resource            | Allowed               |
| ------------------------ | ------------------- | --------------------- |
| Coach → Student          | Student profile     | Allowed fields        |
| Coach → Student          | Training history    | ALLOW                 |
| Coach → Student          | Training analytics  | ALLOW                 |
| Coach → Student          | Ratings             | ALLOW                 |
| Coach → Student          | Assignments         | ALLOW                 |
| Coach → Student          | Password            | DENY                  |
| Coach → Student          | Login/session       | DENY                  |
| Coach → Student          | Private credentials | DENY                  |
| Coach → Unrelated player | Detailed data       | DENY                  |
| Parent → Child           | Profile             | Allowed fields        |
| Parent → Child           | Training history    | ALLOW                 |
| Parent → Child           | Analytics           | ALLOW                 |
| Parent → Child           | Ratings             | ALLOW                 |
| Parent → Child           | Assignments         | ALLOW where supported |
| Parent → Child           | Password            | DENY by default       |
| Parent → Child           | Login/session       | DENY                  |
| Parent → Unrelated child | Any private data    | DENY                  |

A role alone is never sufficient for relationship-scoped resources.

---

## 93.6 Administrative Decision Matrix

| Admin Action             | Admin | Non-Admin | Audit Required |
| ------------------------ | ----: | --------: | -------------: |
| View admin dashboard     | ALLOW |      DENY |             No |
| View user list           | ALLOW |      DENY |             No |
| View user private fields | ALLOW |      DENY |             No |
| Suspend user             | ALLOW |      DENY |            YES |
| Reactivate user          | ALLOW |      DENY |            YES |
| Change user role         | ALLOW |      DENY |            YES |
| Delete/anonymize user    | ALLOW |      DENY |            YES |
| Edit exercise metadata   | ALLOW |      DENY |            YES |
| Disable exercise         | ALLOW |      DENY |            YES |
| Create puzzle            | ALLOW |      DENY |            YES |
| Edit puzzle              | ALLOW |      DENY |            YES |
| Validate puzzle          | ALLOW |      DENY |            YES |
| Review puzzle            | ALLOW |      DENY |            YES |
| Approve puzzle           | ALLOW |      DENY |            YES |
| Publish puzzle           | ALLOW |      DENY |            YES |
| Retire puzzle            | ALLOW |      DENY |            YES |
| Run generator            | ALLOW |      DENY |            YES |
| View generator run       | ALLOW |      DENY |             No |
| View platform analytics  | ALLOW |      DENY |             No |
| View audit log           | ALLOW |      DENY |             No |
| Manage support           | ALLOW |      DENY |            YES |

---

## 93.7 Content Lifecycle Authorization

The following transitions require server-side authorization:

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

### Matrix

| Transition            | Player | Coach | Parent | Admin |
| --------------------- | -----: | ----: | -----: | ----: |
| Draft → Validated     |   DENY |  DENY |   DENY | ALLOW |
| Generated → Validated |   DENY |  DENY |   DENY | ALLOW |
| Validated → Reviewed  |   DENY |  DENY |   DENY | ALLOW |
| Reviewed → Approved   |   DENY |  DENY |   DENY | ALLOW |
| Approved → Published  |   DENY |  DENY |   DENY | ALLOW |
| Published → Active    |   DENY |  DENY |   DENY | ALLOW |
| Active → Retired      |   DENY |  DENY |   DENY | ALLOW |
| Retired → Active      |   DENY |  DENY |   DENY | ALLOW |

The client must not be able to select an arbitrary lifecycle state.

---

## 93.8 Training Submission Decision Matrix

| Condition                                           | Decision                                |
| --------------------------------------------------- | --------------------------------------- |
| Valid authenticated player + valid exercise session | ALLOW                                   |
| Valid guest session                                 | ALLOW under guest rules                 |
| Expired session                                     | DENY                                    |
| Session belongs to another user                     | DENY                                    |
| Exercise disabled                                   | DENY                                    |
| Puzzle unpublished                                  | DENY                                    |
| Answer schema invalid                               | DENY                                    |
| Client submits score                                | Ignore/reject client score              |
| Client submits rating change                        | Ignore/reject client rating             |
| Client submits XP                                   | Ignore/reject client XP                 |
| Client submits correctness                          | Ignore/reject client correctness        |
| Client submits fabricated elapsed time              | Do not trust                            |
| Duplicate idempotency key                           | Return original result or safe conflict |
| Attempt for another user's session                  | DENY                                    |

---

## 93.9 Guest Decision Matrix

| Operation                            | Guest |
| ------------------------------------ | ----: |
| Browse exercises                     | ALLOW |
| Start exercise                       | ALLOW |
| Submit exercise answer               | ALLOW |
| Create temporary history             | ALLOW |
| View own temporary history           | ALLOW |
| View another guest's history         |  DENY |
| View registered user's history       |  DENY |
| Modify another guest session         |  DENY |
| Convert own guest session to account | ALLOW |
| Convert another guest session        |  DENY |
| Access admin                         |  DENY |
| Access private profiles              |  DENY |
| Access platform analytics            |  DENY |

---

## 93.10 Guest Migration Decision Matrix

| Condition                                       | Decision                                                  |
| ----------------------------------------------- | --------------------------------------------------------- |
| Valid guest session + authenticated new account | ALLOW                                                     |
| Guest session belongs to requester              | Required                                                  |
| Guest session expired                           | DENY                                                      |
| Guest already migrated                          | DENY or idempotent original result                        |
| Guest belongs to another account                | DENY                                                      |
| Attempt to migrate arbitrary guest ID           | DENY                                                      |
| Duplicate migration request                     | Idempotent                                                |
| Migration partially fails                       | Roll back atomic data or enter explicit recoverable state |
| XP already migrated                             | Never award twice                                         |
| Achievement already migrated                    | Never award twice                                         |
| Rating history already migrated                 | Never duplicate                                           |

---

## 93.11 API Authorization Matrix

Every protected API endpoint must declare:

```text id="a5uj4s"
authentication requirement
required capability
object scope
relationship requirement
field restrictions
rate limit
audit requirement
```

Example:

| Endpoint Type           | Auth     | Capability      | Object Check              | Audit |
| ----------------------- | -------- | --------------- | ------------------------- | ----- |
| Public exercise catalog | None     | None            | No                        | No    |
| Own profile             | Required | profile.read    | Self                      | No    |
| Update own profile      | Required | profile.write   | Self                      | No    |
| Own history             | Required | history.read    | Self                      | No    |
| Student history         | Required | history.read    | Coach/Parent relationship | No    |
| Admin users             | Required | users.read      | Admin                     | No    |
| Admin role change       | Required | users.manage    | Admin + target            | YES   |
| Puzzle publish          | Required | puzzles.publish | Admin + puzzle            | YES   |
| Generator run           | Required | generators.run  | Admin                     | YES   |
| Audit log               | Required | audit.read      | Admin                     | No    |

---

## 93.12 HTTP Decision Matrix

| Situation                                 | HTTP Result                                       |
| ----------------------------------------- | ------------------------------------------------- |
| No authentication where required          | `401 Unauthorized`                                |
| Authenticated but insufficient permission | `403 Forbidden`                                   |
| Resource intentionally hidden from caller | `404 Not Found` may be used                       |
| Invalid request schema                    | `400 Bad Request` or validation-specific response |
| Valid schema but invalid business state   | `409 Conflict` where appropriate                  |
| Rate limit exceeded                       | `429 Too Many Requests`                           |
| Successful read                           | `200 OK`                                          |
| Successful creation                       | `201 Created`                                     |
| Successful deletion with no body          | `204 No Content`                                  |

The exact API error envelope remains governed by `API_CONTRACTS.md`.

---

## 93.13 Field-Level Mass Assignment Matrix

The server must maintain an explicit allowlist of fields that each operation may modify.

### Player self-update

Allowed examples:

```text
display_name
avatar
bio
privacy_settings
external_chess_identities
```

Forbidden:

```text
role
permissions
rating
rating_history
xp
achievements
account_status
verified
created_at
```

### Admin update

Admin operations may modify additional fields, but still through explicit command schemas.

Never accept an entire database model as an update payload.

---

## 93.14 Security Decision Priority

When multiple rules appear to apply, use this order:

```text
1. Account/session validity
2. Global security restriction
3. Role/capability
4. Object ownership
5. Relationship
6. Resource state
7. Field-level permission
8. Business rule
9. Rate limit / abuse policy
10. Allow
```

Any failed mandatory check results in denial.

---

## 93.15 Authorization Test Matrix

Every major protected resource should have tests covering at least:

| Actor            | Target              | Expected |
| ---------------- | ------------------- | -------- |
| Player A         | Player A data       | ALLOW    |
| Player A         | Player B data       | DENY     |
| Coach A          | Assigned Student A  | ALLOW    |
| Coach A          | Student B           | DENY     |
| Parent A         | Child A             | ALLOW    |
| Parent A         | Child B             | DENY     |
| Player           | Admin endpoint      | DENY     |
| Coach            | Admin endpoint      | DENY     |
| Parent           | Admin endpoint      | DENY     |
| Admin            | Admin resource      | ALLOW    |
| Guest            | Public resource     | ALLOW    |
| Guest            | Private player data | DENY     |
| Expired session  | Protected resource  | DENY     |
| Disabled account | Protected resource  | DENY     |
| Forged object ID | Unauthorized object | DENY     |
| Forged role      | Privileged endpoint | DENY     |

These tests are mandatory because authorization bugs often occur at object, function, and field boundaries rather than simply at the top-level role check.

---

## 93.16 Final Decision Rule

If the implementation cannot answer all of the following questions for an endpoint, the endpoint is not security-complete:

```text
Who is calling?
What capability do they have?
What exact object are they accessing?
Do they own it?
If not, what relationship grants access?
What fields may they see?
What fields may they modify?
What resource state is required?
What abuse controls apply?
Should the operation be audited?
```

If any answer is unknown:

```text
DENY BY DEFAULT
```

This matrix is the concrete implementation baseline for the platform's authorization model.

# 94. Canonical Role and Capability Vocabulary

This section defines the canonical vocabulary for roles and capabilities across the entire MicroChess platform.

These identifiers are normative.

The same names must be used consistently across:

* backend authorization
* database role/permission records
* API policies
* frontend permission checks
* tests
* audit logs
* documentation
* seed data
* admin UI
* future integrations

Do not introduce synonymous identifiers for the same concept.

The authorization model uses roles for coarse-grained identity classification and capabilities for explicit permissions. Object ownership, relationship state, resource state and other attributes remain separate authorization conditions.

This avoids excessive dependence on role-only checks and supports the more fine-grained relationship/attribute checks required by the platform. OWASP recommends least privilege, deny-by-default, permission validation on every request, and relationship/attribute-aware authorization for complex applications.

---

## 94.1 Canonical Roles

The platform has exactly four authenticated application roles at the current target state:

```text id="roles"
PLAYER
COACH
PARENT
ADMIN
```

There is also:

```text id="guest"
GUEST
```

but `GUEST` is not an authenticated account role.

It represents a temporary/unauthenticated training identity.

---

## 94.2 Role Definitions

### `PLAYER`

The normal authenticated MicroChess learner.

A Player may:

* maintain their own profile
* practice exercises
* participate in speed sessions
* submit answers
* accumulate training history
* receive exercise-specific ratings
* receive XP
* earn achievements
* manage personal goals
* view personal analytics
* optionally expose selected public profile information
* optionally provide external chess identities

A Player does not automatically gain access to another player's private data.

---

### `COACH`

A Coach is an authenticated user who has coaching capabilities.

A Coach may:

* maintain their own Player-like profile
* perform normal training activities
* access authorized student information
* view assigned student history
* view assigned student analytics
* view assigned student ratings
* manage permitted student assignments
* eventually assign exercises/training plans

A Coach does **not** automatically have access to:

* all players
* all student accounts
* passwords
* authentication credentials
* unrestricted private information
* administrative functionality

Coach access is relationship-scoped.

```text id="coachrelationship"
COACH
  +
ACTIVE COACH_STUDENT RELATIONSHIP
  +
ALLOWED CAPABILITY
  =
AUTHORIZED ACCESS
```

---

### `PARENT`

A Parent is an authenticated user who has parent/child access.

A Parent may:

* maintain their own account
* access permitted information about their children
* view authorized training history
* view authorized analytics
* view authorized ratings
* eventually receive progress reports and notifications

Parent access is relationship-scoped.

A Parent is not an Admin and does not automatically have unrestricted control over the child's account.

---

### `ADMIN`

An Admin is an authenticated privileged user responsible for platform administration.

Admin capabilities include:

* user management
* role management
* exercise management
* puzzle management
* generator management
* content lifecycle management
* platform analytics
* support management
* audit-log access
* platform configuration where explicitly permitted

Admin privileges must still be implemented through explicit capabilities.

Do not use:

```python
if user.role == "admin":
    allow_everything()
```

as the authorization architecture.

---

## 94.3 Role Storage

The canonical persisted role identifiers are:

```text
player
coach
parent
admin
```

The implementation may represent these using:

* enum
* constrained string
* normalized database table

depending on the existing repository architecture.

The exact storage mechanism must be determined after repository inspection.

The semantic vocabulary must not change.

---

# 95. Canonical Capability Vocabulary

Capabilities are normalized identifiers representing an allowed action.

The canonical naming convention is:

```text
<resource>.<action>
```

Examples:

```text
profile.read
profile.write
training.attempt
users.read
users.manage
puzzles.publish
```

Do not use mixed naming conventions such as:

```text
manage_users
user.manage
adminUsers
USER_ADMIN
```

for the same capability.

---

## 95.1 Capability Categories

The initial canonical capability namespaces are:

```text
profile.*
training.*
history.*
ratings.*
gamification.*
analytics.*
leaderboards.*
relationships.*
users.*
roles.*
exercises.*
puzzles.*
generators.*
support.*
audit.*
system.*
```

---

# 96. Profile Capabilities

```text id="profilecap"
profile.read
profile.write
profile.read_public
profile.manage_external_identities
profile.manage_privacy
```

### Definitions

`profile.read`

Read the caller's own profile.

`profile.write`

Modify permitted fields of the caller's own profile.

`profile.read_public`

Read fields explicitly marked as public on another player's profile.

`profile.manage_external_identities`

Create, update or remove the caller's FIDE/Lichess/Chess.com identity information.

`profile.manage_privacy`

Modify the caller's profile/privacy visibility settings.

---

# 97. Training Capabilities

```text id="trainingcap"
training.read
training.start
training.attempt
training.manage_session
```

### Definitions

`training.read`

Read training information that the caller is authorized to see.

`training.start`

Start an exercise/session.

`training.attempt`

Submit an exercise answer.

`training.manage_session`

Perform permitted lifecycle operations on the caller's own training session.

The server remains authoritative for:

* correctness
* score
* timing
* rating
* XP
* achievements

Possessing `training.attempt` does not grant permission to modify those values directly.

---

# 98. History Capabilities

```text id="historycap"
history.read
history.read_related
history.delete
```

### Definitions

`history.read`

Read the caller's own historical training records.

`history.read_related`

Read history belonging to a user who is connected through an authorized Coach/Parent relationship.

`history.delete`

Delete or request deletion of historical records where the product policy permits it.

Historical deletion must never be interpreted as permission to alter immutable rating or audit records arbitrarily.

---

# 99. Rating Capabilities

```text id="ratingcap"
ratings.read
ratings.read_related
```

Ratings are generated by the platform.

There is intentionally no generic capability such as:

```text
ratings.write
```

for normal players.

A player's rating is an authoritative derived state.

Administrative correction, recalculation or migration must use dedicated administrative capabilities rather than exposing arbitrary rating mutation.

Future capabilities may include:

```text
ratings.recalculate
ratings.correct
```

but they are not part of the initial player vocabulary.

---

# 100. Gamification Capabilities

```text id="gamificationcap"
gamification.read
gamification.read_related
```

These allow reading:

* XP
* levels
* achievements
* streaks
* goals
* milestones
* records

There is intentionally no player-facing:

```text
gamification.write
```

capability.

Gamification state must be derived from authoritative platform events.

---

# 101. Analytics Capabilities

```text id="analyticscap"
analytics.read
analytics.read_related
analytics.read_platform
analytics.read_exercise
analytics.read_puzzle
```

### `analytics.read`

Read the caller's own analytics.

### `analytics.read_related`

Read analytics for authorized Coach/Parent relationships.

### `analytics.read_platform`

Read platform-level administrative analytics.

### `analytics.read_exercise`

Read exercise-level analytics.

### `analytics.read_puzzle`

Read puzzle-level analytics.

The last three are administrative capabilities unless a future product decision explicitly exposes a subset elsewhere.

---

# 102. Leaderboard Capabilities

```text id="leaderboardcap"
leaderboards.read
leaderboards.manage
```

`leaderboards.read`

Read leaderboards subject to privacy rules.

`leaderboards.manage`

Configure or administer leaderboard behavior.

Players must never receive unrestricted access to private leaderboard source data merely because they can view a public leaderboard.

---

# 103. Relationship Capabilities

```text id="relationshipcap"
relationships.read
relationships.create
relationships.accept
relationships.manage
relationships.revoke
```

These capabilities govern relationship lifecycle operations.

However, possessing a relationship capability does not itself authorize access to every object involved.

For example:

```text
relationships.read
```

does not automatically grant access to private student analytics.

The relationship and the requested resource capability must both be satisfied.

---

# 104. User Management Capabilities

```text id="usercap"
users.read
users.read_private
users.manage
users.suspend
users.reactivate
users.delete
```

### `users.read`

Read administrative user information that does not require sensitive fields.

### `users.read_private`

Read sensitive user information when administratively justified.

### `users.manage`

Perform permitted administrative account changes.

### `users.suspend`

Suspend an account.

### `users.reactivate`

Reactivate an account.

### `users.delete`

Perform an approved deletion/anonymization operation.

These capabilities are administrative.

---

# 105. Role Management Capabilities

```text id="rolecap"
roles.read
roles.assign
roles.revoke
```

Role changes are security-sensitive and must be audited.

A client must never be able to assign itself a role by submitting:

```json
{
  "role": "admin"
}
```

Role changes must be performed through an authorized server-side operation.

---

# 106. Exercise Management Capabilities

```text id="exercisecap"
exercises.read
exercises.create
exercises.update
exercises.enable
exercises.disable
exercises.delete
```

Normal players may read published exercise information through the public/player training surface.

Administrative management capabilities control the exercise definition itself.

`exercises.delete` should be avoided for published content where retirement is safer.

---

# 107. Puzzle Management Capabilities

```text id="puzzlecap"
puzzles.read
puzzles.create
puzzles.update
puzzles.validate
puzzles.review
puzzles.approve
puzzles.publish
puzzles.retire
```

The lifecycle is:

```text
create
  ↓
validate
  ↓
review
  ↓
approve
  ↓
publish
  ↓
retire
```

A capability must not implicitly grant every lifecycle transition.

For example:

```text
puzzles.update
```

does not imply:

```text
puzzles.publish
```

This separation is intentional.

---

# 108. Generator Capabilities

```text id="generatorcap"
generators.read
generators.create
generators.update
generators.run
generators.cancel
generators.delete
```

Generator execution may be computationally expensive.

Therefore:

```text
generators.run
```

must be independently authorized and rate/resource limited.

Generated content remains untrusted until validation/review/approval.

---

# 109. Support Capabilities

```text id="supportcap"
support.create
support.read_own
support.read
support.respond
support.close
support.manage
```

### Player/Guest

Normally:

```text
support.create
support.read_own
```

### Admin

May additionally have:

```text
support.read
support.respond
support.close
support.manage
```

Support messages may contain personal information and must be protected accordingly.

---

# 110. Audit Capabilities

```text id="auditcap"
audit.read
audit.export
```

Audit logs are administrative/security data.

Normal players, coaches and parents must not have access to platform audit logs.

---

# 111. System Capabilities

System capabilities are reserved for internal application processes.

Initial vocabulary:

```text id="systemcap"
system.jobs
system.maintenance
system.recalculate
```

These are not normal user permissions.

They must not be granted to Player, Coach or Parent accounts.

The exact internal mechanism may use service identities rather than application roles.

---

# 112. Canonical Role-to-Capability Baseline

The following is the initial baseline.

### Player

```text
profile.read
profile.write
profile.read_public
profile.manage_external_identities
profile.manage_privacy

training.read
training.start
training.attempt
training.manage_session

history.read

ratings.read

gamification.read

analytics.read

leaderboards.read

support.create
support.read_own
```

---

### Coach

Coach inherits the normal Player capabilities appropriate to their own account and additionally receives:

```text
history.read_related
ratings.read_related
gamification.read_related
analytics.read_related

relationships.read
relationships.create
relationships.accept
relationships.manage
relationships.revoke
```

Additional assignment capabilities may be introduced when the Coach assignment feature is implemented.

---

### Parent

Parent inherits normal Player capabilities appropriate to their own account and additionally receives:

```text
history.read_related
ratings.read_related
gamification.read_related
analytics.read_related

relationships.read
relationships.accept
relationships.revoke
```

Parent does not automatically receive:

```text
relationships.create
```

for arbitrary relationships.

Parent/child relationship creation should use the dedicated invitation/verification workflow.

---

### Admin

Admin receives the administrative capabilities required for platform operation, including:

```text
users.read
users.read_private
users.manage
users.suspend
users.reactivate
users.delete

roles.read
roles.assign
roles.revoke

exercises.read
exercises.create
exercises.update
exercises.enable
exercises.disable
exercises.delete

puzzles.read
puzzles.create
puzzles.update
puzzles.validate
puzzles.review
puzzles.approve
puzzles.publish
puzzles.retire

generators.read
generators.create
generators.update
generators.run
generators.cancel
generators.delete

analytics.read_platform
analytics.read_exercise
analytics.read_puzzle

support.read
support.respond
support.close
support.manage

audit.read
audit.export
```

Admin capabilities must still be checked individually where practical.

---

# 113. Capability Does Not Equal Access

A capability is only one input into the authorization decision.

The final decision is conceptually:

```text
ALLOW =
    authenticated
    AND account_active
    AND has_capability
    AND object_allowed
    AND relationship_allowed
    AND resource_state_allowed
    AND business_rules_allowed
```

For public operations:

```text
ALLOW =
    explicitly_public
    AND resource_state_allowed
```

For guest operations:

```text
ALLOW =
    valid_guest_session
    AND guest_capability
    AND guest_scope
```

---

# 114. No Wildcard Capabilities

Do not introduce:

```text
*
admin.*
all
everything
superuser
```

as normal application capabilities.

A privileged role may map to many explicit capabilities, but the capability vocabulary itself should remain explicit and auditable.

This supports least privilege and makes authorization decisions easier to test and review.

---

# 115. No Synonym Capabilities

The following are examples of forbidden duplicates:

```text
users.manage
user.manage
users.admin
admin.users
manage_users
manage.users
```

Choose one canonical identifier:

```text
users.manage
```

and use it everywhere.

---

# 116. No Capability Inference From Names

Do not implement logic such as:

```python
if capability.startswith("admin."):
    ...
```

or:

```python
if "manage" in capability:
    ...
```

Capabilities are identifiers, not executable policy.

Authorization policy must explicitly map capabilities to actions.

---

# 117. Capability Registry

The implementation should have one authoritative capability registry.

Conceptually:

```text
CapabilityRegistry
    profile.read
    profile.write
    profile.read_public
    ...
```

The registry should define at least:

```text
identifier
description
category
sensitive
administrative
```

The exact implementation location must be determined after repository inspection.

Do not duplicate the canonical vocabulary across unrelated files.

---

# 118. Capability Naming Rules

Every capability must:

1. use lowercase
2. use dot-separated namespaces
3. use stable English identifiers
4. represent an action
5. avoid implementation-specific terminology
6. avoid database-table names when unnecessary
7. remain understandable without reading source code

Good:

```text
puzzles.publish
analytics.read_platform
profile.manage_privacy
```

Bad:

```text
canPublishPuzzle
PuzzleModel.publish_allowed
ADMIN_PUZZLE_7
do_puzzle_admin
```

---

# 119. Adding a New Capability

A new capability may be introduced only when:

1. a real business action requires it
2. the existing vocabulary cannot represent it safely
3. its authorization semantics are documented
4. affected roles are documented
5. object/relationship conditions are documented
6. tests are added
7. audit requirements are documented where appropriate

Do not create a new capability merely because an endpoint exists.

---

# 120. Capability Removal

Removing a capability requires checking:

* backend authorization
* API contracts
* frontend permission checks
* database seeds
* tests
* audit logs
* documentation
* role mappings

Never silently rename a capability.

If a semantic replacement is required, treat it as an explicit authorization change.

---

# 121. Role Changes

Roles are intentionally fewer than capabilities.

Do not create roles such as:

```text
PuzzleManager
AnalyticsManager
SupportManager
SeniorCoach
JuniorCoach
ContentReviewer
```

unless a real product requirement later justifies them.

When a distinction is about **what a user can do**, prefer a capability.

When a distinction is about **what kind of relationship/identity the user has**, prefer a role or relationship.

When a distinction is about **which specific object the user may access**, use object/relationship authorization.

This prevents role explosion and keeps the model maintainable. OWASP notes that RBAC can become difficult to manage as roles proliferate and recommends finer-grained attribute/relationship-based controls for complex authorization.

---

# 122. Canonical Vocabulary Summary

## Roles

```text
player
coach
parent
admin
```

## Profile

```text
profile.read
profile.write
profile.read_public
profile.manage_external_identities
profile.manage_privacy
```

## Training

```text
training.read
training.start
training.attempt
training.manage_session
```

## History

```text
history.read
history.read_related
history.delete
```

## Ratings

```text
ratings.read
ratings.read_related
```

## Gamification

```text
gamification.read
gamification.read_related
```

## Analytics

```text
analytics.read
analytics.read_related
analytics.read_platform
analytics.read_exercise
analytics.read_puzzle
```

## Leaderboards

```text
leaderboards.read
leaderboards.manage
```

## Relationships

```text
relationships.read
relationships.create
relationships.accept
relationships.manage
relationships.revoke
```

## Users

```text
users.read
users.read_private
users.manage
users.suspend
users.reactivate
users.delete
```

## Roles

```text
roles.read
roles.assign
roles.revoke
```

## Exercises

```text
exercises.read
exercises.create
exercises.update
exercises.enable
exercises.disable
exercises.delete
```

## Puzzles

```text
puzzles.read
puzzles.create
puzzles.update
puzzles.validate
puzzles.review
puzzles.approve
puzzles.publish
puzzles.retire
```

## Generators

```text
generators.read
generators.create
generators.update
generators.run
generators.cancel
generators.delete
```

## Support

```text
support.create
support.read_own
support.read
support.respond
support.close
support.manage
```

## Audit

```text
audit.read
audit.export
```

## System

```text
system.jobs
system.maintenance
system.recalculate
```

---

# 123. Final Authorization Vocabulary Rule

The canonical model is:

```text
ROLE
  ↓
grants baseline CAPABILITIES
  ↓
CAPABILITY
  ↓
permits an ACTION
  ↓
OBJECT / RELATIONSHIP / STATE checks
  ↓
FINAL AUTHORIZATION DECISION
```

Therefore:

```text
Role ≠ Permission
Permission ≠ Ownership
Ownership ≠ Relationship
Relationship ≠ unrestricted access
Frontend visibility ≠ authorization
```

The backend remains the final authority.

Any implementation that cannot map an authorization decision to this vocabulary must document the reason before introducing a new role, capability, or policy concept.

This vocabulary is the baseline contract for all future platform authorization work.

# 124. Explicit Guest Capability Policy

Guest access is intentionally limited.

A Guest is a temporary training identity, not an authenticated application role.

Guest access exists to reduce friction before registration while ensuring that temporary access cannot become a substitute for an authenticated account.

The Guest policy is explicit and deny-by-default.

A capability not listed in this section is **not available to Guests**.

---

# 124. Explicit Guest Capability Policy

Guest is a temporary access subject, not a separate capability vocabulary.

The canonical authorization vocabulary defined in Section 95 MUST remain the only capability vocabulary used by the platform.

Guest access therefore uses the same canonical capability identifiers as authenticated users, but with a strictly narrower scope.

A capability being available to a Player does **not** mean that the Guest automatically receives it.

Guest authorization is explicitly allowlisted.

---

## 124.1 Guest Identity Model

The platform recognizes:

```text
player
coach
parent
admin
```

as authenticated application roles.

Guest is different.

```text
GUEST
=
temporary unauthenticated access subject
```

Guest does not represent a persisted application role.

A Guest may have:

```text
guest_session
guest_identity
temporary_training_data
```

but does not have an authenticated application account.

Therefore:

```text
Guest ≠ Player
Guest ≠ temporary Player role
Guest ≠ low-privilege Admin
```

---

## 124.2 Canonical Guest Capability Set

The canonical Guest capability set is:

```text
training.read
training.start
training.attempt
support.create
accounts.migrate_guest
```

No other capability is granted to Guests unless this document is explicitly updated.

In particular, Guest does **not** receive the complete Player capability set.

---

## 124.3 Capability Scope

Guest capabilities have narrower object scope than their authenticated equivalents.

For example:

```text
training.read
```

for a Player means:

```text
read authorized training data belonging to the authenticated Player
```

while for a Guest it means:

```text
read temporary training data belonging to the current Guest session
```

Therefore:

```text
same capability
+
different subject
+
different object scope
=
different authorization result
```

Capabilities do not eliminate object-level authorization.

---

# 125. Guest Capability Definitions

## 125.1 `training.read`

Guest access:

```text
ALLOW
```

only for:

* the current guest training session
* the current guest's temporary attempts
* the current guest's temporary progress
* other temporary training state explicitly associated with the current guest identity

Guest access is denied for:

* another Guest's data
* registered Player history
* Coach data
* Parent data
* platform analytics
* administrative analytics
* private training data belonging to any other identity

The server derives the Guest identity from the validated guest session.

The client cannot establish ownership by submitting a guest ID.

---

## 125.2 `training.start`

Guest access:

```text
ALLOW
```

only when:

```text
valid guest session
AND
exercise is published
AND
exercise is enabled
AND
exercise is available to guests
AND
guest is within applicable abuse/rate limits
```

The server creates and owns the authoritative training session.

The Guest cannot choose authoritative:

```text
session owner
session start time
session expiration
score
rating
```

---

## 125.3 `training.attempt`

Guest access:

```text
ALLOW
```

only for an active training session belonging to the current Guest.

The server determines:

* correctness
* score
* timing
* attempt result
* progression
* any temporary gamification state

The Guest cannot directly set:

```text
score
correctness
rating
rating_delta
XP
achievement
elapsed_time
```

as authoritative values.

---

## 125.4 `support.create`

Guest access:

```text
ALLOW
```

for creating a support/contact request.

It must be protected by appropriate abuse controls.

Guest support access does not grant:

```text
support.read
support.respond
support.close
support.manage
```

A Guest may only read the status of a support request if a future explicit capability and secure ownership mechanism are introduced.

---

## 125.5 `accounts.migrate_guest`

This is the only account-related capability granted to a Guest.

It allows the current Guest's temporary training data to be migrated into an authenticated Player account.

Required conditions:

```text
valid guest session
AND
authenticated target account
AND
guest session belongs to requester
AND
target account is active
AND
guest data has not already been migrated
```

The operation must be:

* ownership-checked
* idempotent
* replay-resistant
* transactionally safe
* protected against cross-guest access

---

# 126. Guest Capabilities Explicitly Not Granted

The following canonical capabilities are **not** granted to Guests:

```text
profile.read
profile.write
profile.read_public
profile.manage_external_identities
profile.manage_privacy

training.manage_session

history.read
history.read_related
history.delete

ratings.read
ratings.read_related

gamification.read
gamification.read_related

analytics.read
analytics.read_related
analytics.read_platform
analytics.read_exercise
analytics.read_puzzle

leaderboards.read
leaderboards.manage

relationships.read
relationships.create
relationships.accept
relationships.manage
relationships.revoke

users.read
users.read_private
users.manage
users.suspend
users.reactivate
users.delete

roles.read
roles.assign
roles.revoke

exercises.read
exercises.create
exercises.update
exercises.enable
exercises.disable
exercises.delete

puzzles.read
puzzles.create
puzzles.update
puzzles.validate
puzzles.review
puzzles.approve
puzzles.publish
puzzles.retire

generators.read
generators.create
generators.update
generators.run
generators.cancel
generators.delete

support.read_own
support.read
support.respond
support.close
support.manage

audit.read
audit.export

system.jobs
system.maintenance
system.recalculate
```

### Important distinction

`exercises.read` is not granted to Guests as a capability.

Public exercise discovery is treated as a **public resource**, not as an authenticated capability.

Therefore:

```text
public exercise catalog
=
public access

private/exercise-management data
=
requires explicit authorization
```

This avoids creating unnecessary authenticated capabilities for genuinely public resources.

---

# 127. Guest Capability Matrix

| Canonical Capability     | Guest | Scope                                        |
| ------------------------ | ----: | -------------------------------------------- |
| `training.read`          | ALLOW | Own temporary training data                  |
| `training.start`         | ALLOW | Public guest-eligible exercises              |
| `training.attempt`       | ALLOW | Own active session                           |
| `support.create`         | ALLOW | Create own support request                   |
| `accounts.migrate_guest` | ALLOW | Migrate own guest data                       |
| `profile.*`              |  DENY | Guest has no profile                         |
| `history.*`              |  DENY | Temporary training data uses `training.read` |
| `ratings.*`              |  DENY | No persistent guest rating                   |
| `gamification.*`         |  DENY | No persistent guest gamification             |
| `analytics.*`            |  DENY | No private analytics                         |
| `leaderboards.*`         |  DENY | Public leaderboard is public resource access |
| `relationships.*`        |  DENY | Requires authenticated account               |
| `users.*`                |  DENY | Administrative                               |
| `roles.*`                |  DENY | Administrative                               |
| `exercises.*`            |  DENY | Management capabilities                      |
| `puzzles.*`              |  DENY | Content management                           |
| `generators.*`           |  DENY | Administrative                               |
| `support.read_*`         |  DENY | No authenticated support identity            |
| `support.respond`        |  DENY | Administrative                               |
| `support.close`          |  DENY | Administrative                               |
| `support.manage`         |  DENY | Administrative                               |
| `audit.*`                |  DENY | Administrative                               |
| `system.*`               |  DENY | Internal                                     |

---

# 128. Guest vs Player Capability Comparison

The Guest/Player boundary is intentionally explicit.

| Capability               |                 Guest |                                         Player |
| ------------------------ | --------------------: | ---------------------------------------------: |
| `training.read`          |         Own temporary |                                 Own persistent |
| `training.start`         | Public guest-eligible |                           Published/authorized |
| `training.attempt`       |     Own guest session |                      Own authenticated session |
| `profile.read`           |                  DENY |                                          ALLOW |
| `profile.write`          |                  DENY |                                          ALLOW |
| `history.read`           |                 DENY* |                                          ALLOW |
| `ratings.read`           |                  DENY |                                          ALLOW |
| `gamification.read`      |                  DENY |                                          ALLOW |
| `analytics.read`         |                  DENY |                                          ALLOW |
| `leaderboards.read`      |  Public resource only |           Public resource + own permitted data |
| `support.create`         |                 ALLOW |                                          ALLOW |
| `accounts.migrate_guest` |                 ALLOW |                                           DENY |
| `relationships.*`        |                  DENY | DENY unless applicable relationship capability |
| `admin capabilities`     |                  DENY |                                           DENY |

`*` Guest temporary training data is accessed through the narrower `training.read` scope rather than authenticated historical-data access.

---

# 129. Public Access Is Not a Guest Capability

The platform must distinguish:

```text
PUBLIC
```

from:

```text
GUEST
```

Public access requires no Guest identity.

Examples:

```text
GET /api/v1/exercises
GET /api/v1/exercises/{id}
GET /api/v1/leaderboards/public
```

may be public when the resource itself is configured as public.

Guest-specific authorization becomes relevant when the operation depends on temporary identity, such as:

```text
start training
submit answer
read temporary progress
migrate guest data
```

This distinction prevents unnecessary coupling between public browsing and Guest identity.

---

# 130. Guest Object Scope

For Guest-owned resources:

```text
authorized =
    capability_granted
    AND
    resource.guest_identity_id == current_guest_identity.id
```

The comparison must use the server-derived Guest identity.

This is invalid:

```python
if request.guest_identity_id == resource.guest_identity_id:
    allow()
```

because the request value is attacker-controlled.

---

# 131. Guest Session Requirements

Guest capabilities require a valid Guest session.

The session must have:

* server-generated identity
* expiration
* abuse controls
* revocation capability
* ownership binding

If the Guest session is:

```text
expired
revoked
invalid
malformed
unknown
```

then all Guest-specific capabilities must be denied.

---

# 132. Guest Rating Policy

Guests do not have a persistent MicroChess rating.

Therefore:

```text
ratings.read
=
DENY
```

for Guests.

Temporary training performance may still be calculated for:

* immediate feedback
* temporary score
* session progression

but this must not be represented as a persistent Player rating.

If a future product decision introduces provisional Guest ratings, it must be added explicitly to the rating specification and this capability policy.

---

# 133. Guest Gamification Policy

Guests do not have persistent gamification state.

Therefore:

```text
gamification.read
=
DENY
```

Temporary UI values may exist, such as:

```text
current score
temporary progress
temporary streak display
```

but these are training/session state, not persistent gamification records.

If Guest data is migrated into an account, the migration rules must explicitly define which temporary facts become persistent.

---

# 134. Guest Leaderboard Policy

Guests do not receive:

```text
leaderboards.read
```

as an identity capability.

A public leaderboard may still be visible to Guests because it is a public resource.

Therefore:

```text
Public leaderboard
=
public access

Private leaderboard data
=
DENY
```

This distinction must be preserved in API and UI implementation.

---

# 135. Guest Account Migration

The migration flow is:

```text
Guest
  │
  │ training
  ▼
Temporary guest data
  │
  │ authenticate/create Player account
  ▼
accounts.migrate_guest
  │
  ▼
Player
  │
  ├── persistent history
  ├── persistent ratings where defined
  └── persistent gamification where defined
```

Migration changes the ownership context of eligible data.

It does not grant the Guest arbitrary access to the target account.

---

# 136. Guest Capability Resolution

Authorization should conceptually resolve as:

```text
Subject
  ↓
Is authenticated?
  ├─ Yes → resolve application role
  └─ No
       ↓
       Is valid Guest session?
       ├─ No → public-resource rules only
       └─ Yes → Guest capability policy
```

For Guest:

```text
Guest
  ↓
explicit canonical capabilities
  ↓
object scope
  ↓
resource state
  ↓
business rules
  ↓
ALLOW / DENY
```

---

# 137. New Capability Default

When a new canonical capability is introduced:

```text
new capability
       ↓
Guest access?
       ↓
NO
```

unless the Guest policy is explicitly updated.

This is mandatory.

A new Player capability must never automatically become a Guest capability.

This is a direct application of deny-by-default: new functionality should remain inaccessible until explicitly authorized.

---

# 138. Forbidden Guest Capability Aliases

Do not introduce:

```text
guest.training_start
guest.training_attempt
guest.training_read
guest.support
guest.migrate
```

as alternative capability identifiers.

The canonical identifiers are:

```text
training.start
training.attempt
training.read
support.create
accounts.migrate_guest
```

The fact that a capability is granted to a Guest is authorization metadata, not part of the capability name.

---

# 139. Canonical Authorization Model

The final model is:

```text
                    ┌──────────────┐
                    │    Subject   │
                    └──────┬───────┘
                           │
             ┌─────────────┴─────────────┐
             │                           │
       Authenticated                  Guest
             │                           │
        Application Role          Guest Policy
             │                           │
             └─────────────┬─────────────┘
                           │
                    Canonical Capability
                           │
                    Object / Scope Check
                           │
                  Relationship / State
                           │
                     Business Rules
                           │
                     ALLOW / DENY
```

Therefore:

```text
Guest is not a separate capability vocabulary.
Guest is a subject with a deliberately restricted capability assignment.
```

---

# 140. Final Guest Security Rule

The canonical Guest rule is:

> **Guests may use the canonical training and support capabilities required for temporary learning, and may migrate their own temporary data into an authenticated account. They receive no other capability unless explicitly granted by this policy.**

The canonical Guest capability set is therefore exactly:

```text
training.read
training.start
training.attempt
support.create
accounts.migrate_guest
```

Everything else is denied by default.

This vocabulary must remain aligned with the canonical role/capability registry and must be used consistently across:

* backend authorization
* API contracts
* database policy
* frontend guards
* tests
* audit logs
* documentation
* future platform phases
