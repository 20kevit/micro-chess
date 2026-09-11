# MicroChess Platform — Security

## 1. Document Status

**Status:** Accepted
**Document Type:** Target Security Specification
**Scope:** Authentication, authorization, privacy, training integrity, abuse prevention, and security requirements

This document defines the **target security model** for MicroChess.

It does not describe every mechanism currently implemented in the repository.

Before changing security-sensitive code, the agent MUST inspect the existing implementation and preserve secure mechanisms that already work.

---

# 2. Security Authority

Security requirements are governed by:

1. accepted ADRs
2. `MASTER_PLAN.md`
3. this document
4. the most specific applicable domain specification
5. `API_CONTRACTS.md`
6. active phase specification
7. repository implementation

Where two accepted documents conflict, the conflict must be identified rather than guessed around.

This document defines security requirements.

It does not replace:

* API contracts
* data-model definitions
* authentication implementation details
* UI requirements
* current implementation evidence

---

# 3. Core Security Principles

MicroChess follows these principles:

1. Server authority
2. Least privilege
3. Deny by default
4. Explicit authorization
5. Object-level authorization
6. Secure defaults
7. Minimal data collection
8. Minimal data exposure
9. Privacy by design
10. Defense in depth
11. Auditability
12. Fail safely
13. Validate all untrusted input
14. Never trust client-calculated business state
15. Prefer simple security mechanisms over unnecessary infrastructure

Security mechanisms must be proportionate to actual product requirements.

Do not introduce a complex policy engine, security service, or distributed security infrastructure without demonstrated need.

---

# 4. Browser Trust Boundary

The browser is untrusted.

Anything received from the browser may be modified, replayed, reordered, or fabricated.

The server MUST NOT trust client-provided values for authoritative state, including:

```text
user_id
role
is_admin
ownership
score
correctness
rating
rating_delta
XP
achievement state
session state
elapsed time
server timestamps
content lifecycle state
puzzle solution
exercise result
```

The server must derive authoritative values from:

* authenticated identity
* server-controlled session state
* authorized resources
* domain rules
* authoritative persistence

---

# 5. Threat Model

Relevant threats include:

* account takeover
* brute force
* credential stuffing
* password spraying
* session theft
* session fixation
* privilege escalation
* IDOR/BOLA
* unauthorized administrative access
* API manipulation
* cheating
* score/rating/XP manipulation
* guest abuse
* guest migration abuse
* replay attacks
* spam
* automated account creation
* analytics scraping
* privacy leakage
* minor-safety violations
* malicious file uploads
* XSS
* CSRF where applicable
* SQL injection
* command injection
* SSRF where applicable
* denial of service
* generator abuse
* support abuse
* sensitive-data exposure

The implementation should prioritize threats that are actually reachable in the deployed architecture.

---

# 6. Authentication and Authorization

Authentication answers:

> Who is this identity?

Authorization answers:

> Is this identity allowed to perform this operation on this resource?

Successful authentication does not imply unrestricted access.

Examples:

```text
PLAYER ≠ ADMIN
COACH ≠ OWNER OF EVERY STUDENT
PARENT ≠ ADMIN
```

Authentication and authorization must remain separate concerns.

---

# 7. Canonical Roles

The canonical persisted roles are:

```text
PLAYER
COACH
PARENT
ADMIN
```

Role names must be represented consistently across:

* database
* API
* application layer
* frontend authorization state
* documentation

Guest is **not** a persisted role.

Guest is a temporary identity/session state.

---

# 8. Registration

Initial registration requires only:

```text
username
password
```

Do not require at initial registration:

* email
* phone
* real name
* FIDE ID
* Lichess identity
* Chess.com identity

This is intentional data minimization.

Additional profile information may be introduced later through explicit product requirements.

---

# 9. Username Security

Usernames must have:

* minimum length
* maximum length
* allowed character rules
* normalization rules
* uniqueness rules
* case-handling rules

These rules must be defined once and reused consistently.

The system must not permit multiple accounts that are indistinguishable solely because of inconsistent normalization.

The exact rules should be centralized rather than duplicated across routes.

---

# 10. Password Storage

Passwords must never be stored in plaintext.

Use a mature password-hashing implementation.

Acceptable technologies include established password-hashing algorithms such as:

* Argon2id
* bcrypt
* another appropriately supported password-hashing implementation

Do not implement password hashing manually.

Password hashes must never be returned through the API.

Passwords must never be written to logs.

---

# 11. Password Policy

The password policy should provide reasonable protection without unnecessary usability barriers.

It must define:

* minimum length
* maximum length
* handling of long passwords
* invalid input behavior

The system must never silently truncate passwords.

Exact password policy should be centralized and tested.

---

# 12. Login Security

Authentication endpoints must resist:

* brute force
* credential stuffing
* password spraying
* automated login abuse
* username enumeration

Login failures should use generic responses.

Do not reveal whether:

```text
username does not exist
```

versus:

```text
password is incorrect
```

unless a deliberate product/security decision explicitly requires different behavior.

---

# 13. Authentication Rate Limiting

Rate limiting should apply to high-risk authentication operations where applicable:

* registration
* login
* password changes
* password recovery
* account recovery

Thresholds should be configurable.

Do not scatter arbitrary hard-coded limits through route handlers.

---

# 14. Session Security

Sessions must use unpredictable server-validated identifiers or an equivalent secure mechanism.

Sessions must support:

* expiration
* invalidation
* logout
* fixation protection
* secure transport

Where cookies are used, production authentication cookies should use appropriate attributes such as:

```text
Secure
HttpOnly
SameSite
```

The exact `SameSite` policy depends on deployment architecture.

---

# 15. Session Lifetime

Authenticated sessions should support appropriate:

```text
idle timeout
absolute timeout
```

where useful.

Durations should be centralized/configurable.

Do not duplicate timeout constants across unrelated routes.

---

# 16. Logout

Logout must invalidate the relevant authenticated session.

It must not:

* delete another session
* revoke another user's credentials
* leave an invalidated credential usable

Future multi-device session management may support:

* current session
* individual session
* all sessions

but is not required unless explicitly in scope.

---

# 17. HTTPS

Production authentication and authenticated traffic must use HTTPS.

Sensitive data must not be transmitted over plaintext HTTP.

Deployment should redirect HTTP to HTTPS where appropriate.

The application must not assume transport security merely because the development environment uses localhost.

---

# 18. Sensitive Account Operations

Sensitive future operations may require re-authentication.

Examples:

* password change
* password recovery
* adding authentication factors
* changing critical credentials
* high-risk account changes
* destructive administrative actions

Do not implement complex re-authentication flows before the product requires them.

---

# 19. Future Authentication

The architecture should remain reasonably extensible for:

* password reset
* email verification
* MFA
* passkeys
* OAuth/OIDC
* social login
* account recovery

These are future capabilities.

They are not current implementation requirements unless activated by the roadmap.

---

# 20. Authorization Model

Authorization uses:

```text
Identity
+
Capability
+
Object authorization
+
Relationship
+
Resource state
+
Privacy rules
```

as applicable.

Role alone is insufficient for sensitive resource access.

---

# 21. Deny by Default

Access must be denied unless explicitly authorized.

Every protected operation must define its authorization requirement.

Do not rely on a broad rule such as:

```text
if user is not admin:
    deny
```

for only some endpoints.

Authorization must be deliberate for each protected capability.

---

# 22. Capability Model

The platform should use canonical capabilities rather than scattering role checks throughout the codebase.

Examples:

```text
users.read
users.manage
exercises.read
exercises.manage
puzzles.read
puzzles.create
puzzles.manage
puzzles.review
puzzles.publish
generators.run
analytics.view
audit.view
support.manage
relationships.manage
```

The final capability registry belongs to the authorization implementation/domain specification.

This document does not create a second permission registry.

The initial implementation may map capabilities to roles.

Do not introduce a complex policy engine unless justified.

---

# 23. Object-Level Authorization

Every resource request must check access to the **specific object**.

Example:

```text
GET /api/v1/me/training/attempts/123
```

must verify that attempt `123` belongs to the current identity.

The following is never sufficient:

```text
current_user.role == PLAYER
```

Object-level authorization is mandatory for resource-specific operations.

---

# 24. IDOR/BOLA Protection

Do not assume that knowledge of an identifier grants access.

Protect identifiers used for:

* users
* attempts
* sessions
* puzzles
* files
* relationships
* support tickets
* generator runs
* administrative resources

Unauthorized access must be rejected even when the resource ID is valid.

For sensitive resources, `404` may be preferable to `403` when exposing existence would leak information.

---

# 25. Admin Security

Administrative capabilities are high risk.

Admin operations require:

1. authenticated identity
2. appropriate administrative capability
3. object-level authorization where relevant
4. validation of the requested state transition
5. audit logging for sensitive changes

Frontend admin routes are not security controls.

A malicious client must not gain administrative access by manipulating:

```text
is_admin
role
local storage
route paths
request payloads
query parameters
```

---

# 26. Administrative Self-Protection

The platform should prevent an administrator from accidentally or maliciously destroying the ability to administer the system.

Examples include:

* removing the final administrative capability
* self-deletion during a protected operation
* invalid privilege transitions

Exact safeguards belong to the admin domain.

---

# 27. Relationship Authorization

Coach/student and parent/student access requires:

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

Role alone does not grant access to all related users.

---

# 28. Relationship Revocation

Relationships use explicit lifecycle states.

Canonical relationship states:

```text
PENDING
ACTIVE
REVOKED
```

When a relationship becomes revoked:

```text
relationship = REVOKED
```

ordinary access that depended solely on that relationship must stop.

Historical records may remain available according to privacy and retention rules.

---

# 29. Guest Identity

Guest is a temporary identity, not a role.

Guest sessions must use server-controlled identity.

The client must not establish ownership through a supplied identifier such as:

```text
guest_user_id
```

A guest identifier is an identifier, not an authorization credential.

---

# 30. Guest Capabilities

Guest access must be limited to explicitly allowed functionality.

Guests must not access:

* admin functions
* unrelated users
* private player profiles
* privileged analytics
* privileged administration data
* another guest's training history

Guest access must expire.

---

# 31. Guest Abuse Protection

Guest functionality is especially vulnerable to:

* automated session creation
* scraping
* reward farming
* replay
* data accumulation
* denial-of-service behavior

Apply proportionate controls such as:

* rate limiting
* session expiration
* bounded history
* anti-replay protection
* server-side ownership checks

Do not introduce CAPTCHA or third-party anti-abuse systems unless actual abuse or deployment requirements justify them.

---

# 32. Guest Migration Security

Guest migration is security-sensitive.

It must verify:

1. the guest session belongs to the requester
2. the guest session is valid
3. the destination account is authenticated
4. the migration has not already completed
5. guest data is not already assigned elsewhere
6. historical records are not duplicated
7. rewards are not duplicated
8. the operation is atomic where required

The client must never specify arbitrary ownership identifiers.

---

# 33. Guest Migration Idempotency

A repeated migration request must not duplicate:

* attempts
* rating events
* XP
* achievements
* streak activity
* historical sessions

A retry should return the existing migration outcome where appropriate.

---

# 34. Training Integrity

The server is authoritative for:

* answer correctness
* score
* timing
* rating
* rating delta
* XP
* achievements
* mastery
* session state
* puzzle validity

The client may provide the player's answer.

It may not decide the result.

---

# 35. Question Instance Security

Training attempts should be bound to server-issued question instances.

Conceptually:

```text
Exercise Content
    ↓
Question Instance
    ↓
Attempt
```

The question instance binds the concrete question to:

* session
* exercise
* content
* delivery context

The server must verify that the submitted question instance:

* exists
* belongs to the current session
* belongs to the current identity
* is valid for the exercise/mode
* is still usable
* has not already become terminal where repeat submission is forbidden

---

# 36. Hidden Answer Protection

Hidden puzzle/exercise answers must never be exposed to the browser before submission.

This includes:

* JSON fields
* HTML attributes
* JavaScript variables
* embedded page data
* metadata
* source maps
* preloaded APIs

Client-side hiding is not security.

If the browser receives the answer, the answer must be considered compromised.

---

# 37. Exercise Validation

Exercise correctness must be validated server-side.

The server must own exercise-specific validation rules.

For chess exercises, this may include:

* board state validation
* legal moves
* selected squares
* move sequences
* chess-rule checks
* solution correctness

The client may provide a candidate answer only.

---

# 38. Speed Mode Security

The client may display a local countdown.

The server determines:

* session start
* deadline
* expiration
* whether the submission was on time
* authoritative duration

The client must not be able to submit a fabricated elapsed time and thereby bypass a deadline.

---

# 39. Replay Protection

State-changing operations that create authoritative consequences must protect against replay.

Examples:

* attempt submission
* guest migration
* publishing content
* retiring content
* generator runs
* sensitive administrative actions
* reward-producing operations

Use:

* idempotency keys
* unique constraints
* transaction boundaries
* explicit state machines

where appropriate.

---

# 40. Attempt Idempotency

Attempt submission must be idempotent.

The server should bind idempotency to:

* authenticated/guest identity
* operation
* request context

A repeated request must not produce a second:

* attempt
* rating change
* XP award
* achievement change

The same idempotency key must not be reusable across unrelated operations.

---

# 41. Transaction Integrity

When an authoritative operation changes multiple facts that must remain consistent, use an appropriate transaction boundary.

For a successful attempt, core authoritative state may include:

```text
attempt
rating event
rating state
XP reward
achievement state
streak state
```

The system must define which of these are transactionally atomic.

Derived analytics need not be part of the same transaction when they can safely be recalculated from authoritative records.

The user must never receive a success response for an operation whose core authoritative state failed to commit.

---

# 42. Rating Security

Ratings are server-owned.

A client may not directly set:

```json
{
  "rating": 2500
}
```

or:

```json
{
  "rating_delta": 100
}
```

Rating changes originate from authoritative application logic.

Historical rating events are not editable by ordinary clients.

Administrative correction, if ever required, must use an explicit controlled and auditable workflow.

---

# 43. Gamification Security

The client may not directly award itself:

* XP
* achievements
* badges
* streaks
* mastery
* challenge completion

Forbidden patterns include:

```text
POST /api/v1/me/xp
POST /api/v1/me/achievements/unlock
```

where the client selects the authoritative result.

Gamification state must result from legitimate server-side activity.

---

# 44. Anti-Abuse Gamification

Gamification must avoid rewarding meaningless or repeated automated activity.

The server may limit qualifying activity based on:

* duplicate attempts
* impossible timing
* repeated replay
* session state
* suspicious request volume
* domain-specific qualification rules

Anti-abuse rules should be simple and evidence-driven.

Do not build a generic fraud platform prematurely.

---

# 45. Content Security

Generated or user-created content must never bypass validation.

Content lifecycle:

```text
DRAFT
→ CREATED / GENERATED
→ VALIDATED
→ REVIEWED
→ APPROVED
→ PUBLISHED
→ ACTIVE
→ RETIRED
```

Generated content is never automatically trusted as production content.

Lifecycle transitions must be authorized and validated.

---

# 46. Generator Security

Generators may consume significant CPU, memory, or storage.

Generator execution must therefore be:

* authenticated
* authorized
* bounded
* observable
* protected against duplicate execution when necessary

Do not expose arbitrary executable code/configuration through untrusted API input.

Target rating/difficulty values are generation objectives, not security guarantees.

---

# 47. File Security

If the product handles uploads, uploaded files must be treated as untrusted.

Security controls should include:

* allowed file types
* size limits
* safe filenames
* server-controlled storage paths
* authorization before access
* content validation where appropriate
* no direct filesystem path access
* no execution from upload directories

Do not expose private uploads as unrestricted static files.

Private media access must go through authorized server-controlled mechanisms.

---

# 48. File Name and Path Safety

Never use a client-supplied filename directly as a filesystem path.

Never allow:

```text
../
absolute paths
filesystem traversal
```

to affect storage location.

Prefer generated storage identifiers.

The original filename, when retained, is metadata rather than a storage path.

---

# 49. Input Validation

All client input is untrusted.

Validate:

* type
* structure
* allowed values
* length
* size
* range
* format
* state transitions
* ownership
* authorization
* business rules

Client-side validation is a UX convenience.

Server-side validation is mandatory.

---

# 50. SQL Injection

Database access must use the ORM/database parameterization mechanisms.

Never construct SQL with unsanitized client strings.

Search, filtering, sorting, pagination, and identifiers must use explicit allowlists where necessary.

---

# 51. Command Injection

Never pass untrusted client values directly into operating-system commands.

If subprocess execution becomes necessary:

* use fixed executable paths
* pass arguments as structured argument arrays
* validate arguments
* avoid shell interpretation
* run with least privilege

Do not introduce subprocess-based infrastructure without a real requirement.

---

# 52. SSRF

If the platform later retrieves external URLs, the server must validate:

* allowed schemes
* hostname
* redirects
* private/internal address ranges
* DNS rebinding risks
* response size
* timeout

Do not introduce generic arbitrary URL fetching.

External integrations should use explicit allowlists and adapters.

---

# 53. XSS

All user-controlled content must be safely handled.

Do not render untrusted HTML without sanitization.

Prefer:

* normal escaped text
* React's default escaping
* controlled rich-text sanitization when explicitly required

Do not add `dangerouslySetInnerHTML` or equivalent without a justified and reviewed use case.

---

# 54. CSRF

If browser authentication uses cookies, CSRF protection must be considered for state-changing requests.

The exact mechanism depends on:

* cookie/session architecture
* same-site deployment
* frontend/backend origin configuration

Do not assume that CORS alone is CSRF protection.

If bearer tokens are used in a non-cookie architecture, evaluate CSRF exposure separately.

---

# 55. CORS

CORS must be explicitly configured.

Do not use unrestricted production configuration such as:

```text
allow_origins = ["*"]
```

when authenticated browser credentials are involved.

Allowed origins should match the deployment architecture.

---

# 56. Security Headers

Production deployment should use appropriate HTTP security headers where applicable, including consideration of:

* Content-Security-Policy
* X-Content-Type-Options
* Referrer-Policy
* frame protections
* HSTS

Exact deployment configuration belongs to the deployment layer.

Application code should not duplicate deployment configuration unnecessarily.

---

# 57. Sensitive Data

Never expose:

* passwords
* password hashes
* session secrets
* reset tokens
* private keys
* internal credentials
* infrastructure secrets

through API responses.

Sensitive values must not appear in normal application logs.

---

# 58. Secrets Management

Secrets must come from the configured secret/environment mechanism.

Do not commit:

* passwords
* API keys
* access tokens
* database credentials
* encryption keys

to source control.

Never place secrets in frontend bundles.

---

# 59. Logging

Security-relevant actions should be logged or audited when appropriate.

Logs should help investigate:

* authentication failures
* suspicious activity
* privilege changes
* administrative actions
* sensitive lifecycle changes
* generator abuse

Logs must not contain:

* passwords
* session tokens
* sensitive credentials
* unnecessary personal information

---

# 60. Audit Records

Sensitive administrative state changes should produce audit records.

Examples:

* role changes
* account suspension
* privileged content publication
* content retirement
* generator execution where operationally relevant
* support actions involving private data

Audit records should preserve:

* actor
* action
* target
* timestamp
* relevant context
* result where appropriate

Historical audit records are not ordinary user-editable data.

---

# 61. Analytics Privacy

Analytics are derived from authoritative training history.

Access to analytics must still respect:

* identity
* capability
* ownership
* relationships
* privacy settings

Coach and parent analytics access must be scoped.

Private analytics must not become public merely because they appear in a shared dashboard query.

---

# 62. Leaderboard Privacy

Leaderboard participation and visibility must respect product privacy rules.

Do not expose private player information merely because ranking data exists.

Only fields intentionally selected for leaderboard visibility should be exposed.

---

# 63. Child and Teen Privacy

MicroChess is child-first.

Therefore:

* collect minimum necessary personal data
* avoid unnecessary identity information
* avoid exposing contact information
* carefully scope coach/parent access
* minimize public profile information
* minimize analytics exposure
* avoid accidental information disclosure through usernames or rankings

Do not add personal-data requirements simply because they may be useful later.

---

# 64. External Chess Identities

FIDE, Lichess, and Chess.com identities are separate from MicroChess identity and rating.

External ratings are not MicroChess ratings.

Initial external ratings may be self-reported.

Verification state must be server-controlled.

The client must never be able to submit:

```text
verified = true
```

as an authoritative operation.

---

# 65. API Security

All protected APIs must enforce backend authorization.

Frontend route guards do not provide security.

Sensitive API operations should use:

* authentication
* capability checks
* object authorization
* input validation
* replay protection
* rate limiting where appropriate

The API contract is defined in:

```text
API_CONTRACTS.md
```

This document provides the security constraints that API implementations must satisfy.

---

# 66. Error Safety

Error responses must not expose:

* stack traces
* SQL statements
* filesystem paths
* internal module structure
* secrets
* tokens
* sensitive data

Errors should be:

* safe
* useful
* machine-readable where required
* consistent with API contracts

---

# 67. Enumeration Resistance

Avoid unnecessary enumeration through:

* login responses
* private profile endpoints
* resource IDs
* support endpoints
* relationship endpoints
* guest endpoints

Where revealing the existence of a resource would create risk, use privacy-preserving response semantics.

---

# 68. Rate Limiting

Rate limiting should be applied proportionally to:

* authentication
* guest creation
* attempt submission
* support creation
* expensive analytics
* generator execution
* sensitive administrative actions

Do not put unrelated fixed limits into every route.

Rate limiting configuration should be centralized.

---

# 69. Denial of Service

The application should protect against unbounded resource consumption.

Relevant controls include:

* request body limits
* pagination
* bounded generator jobs
* bounded file uploads
* query limits
* timeouts
* rate limiting
* bounded analytics requests

Do not add distributed infrastructure solely for hypothetical DoS scenarios.

---

# 70. Analytics Query Safety

Analytics endpoints must not allow unbounded queries.

They should enforce:

* bounded date ranges where necessary
* indexed filters
* pagination
* sensible aggregation limits

The client must not be able to request arbitrary database expressions.

---

# 71. Support Abuse

Support endpoints should be protected against:

* spam
* automated ticket creation
* abusive message volume
* unauthorized ticket access

Support data is private by default.

A user may access only their own support records.

Admins require appropriate support capabilities.

---

# 72. Privacy by Default

When unsure whether data should be exposed, prefer the narrower scope.

A response should contain only the data required for its purpose.

Do not rely on clients to hide sensitive fields.

The server determines the response shape.

---

# 73. Data Retention

Data retention policies should distinguish:

```text
authoritative historical data
temporary guest data
derived analytics
audit data
support data
private media
```

Do not delete authoritative history merely because it is no longer displayed in the UI.

Guest retention may be shorter where product/security requirements justify it.

Exact retention rules belong to the relevant domain specifications.

---

# 74. Security and Historical Data

Historical attempts, ratings, and reward facts should be treated as authoritative records.

Ordinary clients cannot:

* edit
* delete
* rewrite
* recompute

historical facts.

Explicit administrative correction workflows, if introduced, must preserve an audit trail.

---

# 75. Security and Migrations

Database migrations involving security-sensitive data must:

* preserve account ownership
* preserve authorization semantics
* avoid accidental privilege escalation
* avoid dropping security-relevant history
* support rollback/recovery planning where appropriate

Never change role semantics through an ad hoc data migration without verifying all authorization paths.

---

# 76. Security Testing

Security-sensitive behavior requires automated tests.

At minimum, cover:

### Authentication

* registration
* duplicate username
* login
* invalid login
* logout
* session expiration
* protected endpoint rejection

### Authorization

* correct capability
* missing capability
* wrong role
* object ownership
* cross-user access
* relationship access
* revoked relationship

### Guest

* guest creation
* guest isolation
* guest expiration
* guest abuse controls
* guest migration
* migration replay
* wrong-owner migration

### Training

* forged score
* forged correctness
* forged rating
* forged XP
* wrong question instance
* wrong session
* duplicate attempt
* speed-mode replay

### Admin

* non-admin rejection
* capability enforcement
* target-object authorization
* protected state transitions
* audit behavior

### Content

* unauthorized publish
* unauthorized retire
* invalid lifecycle transition
* generator authorization

### Privacy

* private profile isolation
* private analytics isolation
* coach scope
* parent scope
* unrelated-user access

---

# 77. Security Verification

A phase involving security-sensitive changes is not complete until:

1. relevant automated tests pass
2. authorization is verified
3. object-level access is tested
4. replay/duplicate behavior is tested where relevant
5. sensitive responses are inspected
6. no secret is introduced
7. existing secure behavior is preserved
8. runtime behavior is checked where appropriate

---

# 78. Security and Development Workflow

Before modifying security-sensitive code, the agent must:

1. inspect existing authentication/session behavior
2. inspect authorization dependencies
3. inspect relevant models
4. inspect API routes
5. inspect frontend auth usage
6. inspect tests
7. identify the current security boundary
8. determine the minimum required change

The agent must not replace working security mechanisms merely because another implementation looks cleaner.

---

# 79. No Security-by-Abstraction

Do not create abstractions whose only purpose is to make the architecture look more secure.

Security should come from:

* explicit rules
* correct boundaries
* server authority
* least privilege
* tests
* controlled state transitions

A large policy engine is not automatically more secure.

---

# 80. No Speculative Security Infrastructure

Do not introduce:

* external IAM platforms
* service meshes
* distributed policy engines
* dedicated security microservices
* event-sourcing infrastructure
* security data warehouses

unless explicitly required.

The initial security model must remain understandable within the application.

---

# 81. Security Responsibility by Layer

Conceptually:

```text
Browser
    ↓
HTTP/API Boundary
    ↓
Authentication
    ↓
Authorization
    ↓
Application Use Case
    ↓
Domain Rules
    ↓
Persistence
```

Each layer has a role.

Security-critical decisions must not exist only in the frontend.

---

# 82. Security and Existing Exercises

The platform expansion must not weaken existing exercise protections.

Existing exercise systems must continue to enforce:

* server-side correctness
* controlled question delivery
* appropriate session authority
* hidden-answer protection
* proper history recording

New platform infrastructure must integrate with the existing exercise architecture rather than creating a parallel security model.

---

# 83. Security and API Evolution

When an API changes, review:

* authentication
* authorization
* ownership
* privacy
* replay protection
* validation
* error leakage

A seemingly harmless endpoint change can create an authorization bypass.

API contract changes must be security-reviewed when they alter resource access or state-changing behavior.

---

# 84. Security and Future Notifications

Notifications are not a canonical standalone roadmap phase.

If notifications are added later, they must follow:

* authorization
* recipient ownership
* privacy
* anti-spam controls
* rate limits where necessary

Do not introduce notification infrastructure merely because a future design may use notifications.

---

# 85. Security and Future Adaptive Training

Adaptive training must not expose private or unrelated-player information.

Future recommendation systems should use only data the current identity is authorized to influence or view.

Adaptive logic must not become an authorization bypass.

---

# 86. Security Completion Rule

A security requirement is complete only when:

```text
Requirement
    ↓
Implementation
    ↓
Authorization
    ↓
Validation
    ↓
Persistence safety
    ↓
Tests
    ↓
Runtime verification where relevant
    ↓
Documentation
```

A middleware check alone is not sufficient evidence of security completeness.

---

# 87. Final Security Rules

The following rules are non-negotiable:

```text
The browser is untrusted.

The server owns authoritative state.

Authentication is not authorization.

Role is not object authorization.

Guest is not a persisted role.

Every protected resource requires appropriate authorization.

Historical facts are protected from ordinary client mutation.

Attempt submission must be replay-safe.

Ratings and gamification are server-controlled.

Hidden answers never reach the client before submission.

Speed timing is server-authoritative.

Generated content is not automatically trusted.

Private data is not exposed by default.

Sensitive administrative actions are auditable.

Security mechanisms must remain simple enough to understand and test.
```

The security architecture should optimize for:

```text
Correctness
+
Least Privilege
+
Privacy
+
Server Authority
+
Testability
+
Low Unnecessary Complexity
```
