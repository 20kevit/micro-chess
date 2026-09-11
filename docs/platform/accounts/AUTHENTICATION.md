# MicroChess — Authentication

## 1. Document Status

**Status:** Accepted
**Document Type:** Authentication Domain Specification
**Scope:** Registration, login, sessions, guest identity, guest migration, account status, and authentication security

This document defines authentication behavior for MicroChess.

It does not define the complete authorization model.

Authorization requirements are defined in:

* `SECURITY.md`
* `ROLES_AND_PERMISSIONS.md`

API transport contracts are defined in:

* `API_CONTRACTS.md`

The logical data model is defined in:

* `DATA_MODEL.md`

This document describes the **target behavior**.

The repository remains the source of truth for current implementation.

---

# 2. Authentication vs Authorization

Authentication answers:

> Who is making the request?

Authorization answers:

> What is this identity allowed to do?

These concerns MUST remain separate.

Authentication establishes identity.

Authorization determines:

* role
* capability
* ownership
* relationship
* resource access

A successful login does not grant unrestricted access.

---

# 3. Registered Identity

A registered MicroChess identity is represented by a persistent user account.

Initial registration requires only:

```text
username
password
```

The initial registration flow must not require:

* email
* phone
* real name
* FIDE identity
* Lichess identity
* Chess.com identity

Additional information may be added later through explicit product capabilities.

---

# 4. Registration

Registration should conceptually follow:

```text
Submit registration
       ↓
Validate username
       ↓
Check uniqueness
       ↓
Validate password
       ↓
Hash password
       ↓
Create user
       ↓
Assign PLAYER role
       ↓
Create required account/profile state
       ↓
Establish authenticated session
```

The exact transaction boundary follows the implementation architecture.

Registration must be atomic with respect to the account state that must exist for a newly registered user to authenticate safely.

---

# 5. Username Rules

Usernames must have one canonical validation policy.

The policy should define:

* minimum length
* maximum length
* allowed characters
* normalization
* case handling
* uniqueness

The same rules must be used consistently across:

* registration
* login
* profile lookup
* public profile URLs
* administrative user search

The database must enforce uniqueness.

Do not rely only on application-level duplicate checks.

---

# 6. Username Normalization

Username normalization must be deterministic.

The system must not allow two accounts that are effectively identical under the canonical normalization rules.

The normalized representation may be stored separately from the display representation when useful.

Do not introduce multiple competing normalization rules.

---

# 7. Password Validation

Passwords must be validated server-side.

The password policy must define:

* minimum length
* maximum accepted length
* handling of unusually long input
* invalid input behavior

The system must never silently truncate passwords.

The policy should provide strong security without imposing unnecessary friction on the child-first product.

---

# 8. Password Storage

Passwords must:

* never be stored in plaintext
* use a mature password-hashing algorithm
* never appear in application logs
* never appear in API responses
* never be stored in frontend state as persistent credentials

The implementation must use a well-tested password-hashing library.

Do not implement cryptographic password hashing manually.

---

# 9. Login

Login conceptually follows:

```text
Credentials
    ↓
Validate request
    ↓
Find account
    ↓
Verify password
    ↓
Check account status
    ↓
Create/reuse authenticated session
    ↓
Return safe account information
```

Credential verification is server-side.

The client must never receive:

* password hash
* password verification material
* internal authentication state
* session internals not required by the client

---

# 10. Authentication Failure Behavior

Authentication failures should use safe, consistent responses.

Do not unnecessarily reveal whether:

* the username exists
* the account is nearly valid
* another authentication factor exists
* an internal account state was reached

The exact user-facing error message should balance usability and enumeration resistance.

---

# 11. Account Status

Authentication must respect account status.

Canonical conceptual states:

```text
ACTIVE
SUSPENDED
DELETED
```

Only eligible active accounts may authenticate normally.

A suspended account must not gain normal authenticated access.

Deleted-account behavior must follow the platform's retention/deletion policy.

The exact database representation may differ from these conceptual states.

---

# 12. Authenticated Sessions

An authenticated session must be:

* server-controlled
* unpredictable
* expirable
* revocable
* protected against fixation
* transported securely

The exact session mechanism is an implementation decision.

The browser must never be able to forge an authenticated identity by supplying an arbitrary user ID.

---

# 13. Session Ownership

A session is associated with exactly one authenticated identity.

The server derives the current identity from the authenticated session.

Client-provided values such as:

```text
user_id
role
is_admin
```

must not establish authentication.

---

# 14. Session Expiration

Authenticated sessions should support appropriate expiration.

The implementation may use:

* idle expiration
* absolute expiration
* both

Durations should be centrally configurable.

Do not scatter session timeout constants throughout route handlers.

---

# 15. Session Revocation

Sessions must support revocation.

At minimum:

* logout invalidates the current session
* account suspension prevents normal authenticated use
* security-sensitive state changes may require session invalidation or rotation

Future multi-session management may allow:

* current-session logout
* individual-session revocation
* revoke-all-sessions

but these are not required until explicitly scoped.

---

# 16. Session Fixation Protection

Authentication must prevent session fixation.

When the authentication architecture requires a session identifier to change at login, the session must be rotated rather than continuing an attacker-known pre-authentication identity.

The exact mechanism belongs to the session implementation.

---

# 17. Cookie-Based Sessions

When authentication uses cookies, production cookies should use appropriate security attributes, including as applicable:

```text
Secure
HttpOnly
SameSite
```

The exact `SameSite` value depends on the deployment architecture.

Cookie configuration must be centralized.

---

# 18. HTTPS

Production authenticated traffic must use HTTPS.

Authentication credentials and session credentials must never be intentionally transmitted over plaintext HTTP.

The development environment may use localhost without TLS where appropriate.

Production deployment configuration is outside this document but must satisfy the security requirement.

---

# 19. Logout

Logout:

```text
POST /api/v1/auth/logout
```

must invalidate the current authenticated session.

After successful logout, the invalidated credential must not remain usable.

Logout must not affect another user's session.

---

# 20. Current Authenticated Identity

The platform may expose:

```text
GET /api/v1/me
```

to retrieve the current authenticated identity.

The response may include:

* user ID
* username
* roles
* safe account information
* profile information where applicable

It must not include sensitive authentication material.

---

# 21. Authentication Context

The application should establish an explicit authentication context containing the current identity/session information needed by downstream authorization.

Conceptually:

```text
Request
   ↓
Authentication
   ↓
Authenticated Identity
   ↓
Authorization
   ↓
Application Use Case
```

Business logic must not repeatedly reconstruct authentication state from raw request data.

---

# 22. Guest Identity

Guest is a temporary identity/session state.

Guest is **not** a persisted role.

Guest access must be established through a server-controlled guest session.

The browser must not be able to claim ownership by submitting an arbitrary guest identifier.

Conceptually:

```text
Guest Session
    ↓
Temporary Identity
    ↓
Training
    ↓
Optional Migration
    ↓
Registered User
```

---

# 23. Guest Session Creation

Guest sessions should be created through a dedicated server operation when guest access is required.

Conceptually:

```text
POST /api/v1/guest/session
```

The server creates the guest identity/session.

The response must expose only the information required for the client to continue using the guest experience.

The client must never receive unrestricted ownership authority.

---

# 24. Guest Authentication Scope

Guest capabilities are narrower than registered-player capabilities.

Guest functionality may include:

* starting supported exercises
* submitting supported attempts
* viewing the guest's own temporary training state
* creating support requests where supported
* migrating guest data to a registered account

Guest must not gain:

* administrative access
* another user's private data
* unrestricted analytics
* privileged content-management access
* privileged relationship access

The exact capability mapping belongs to the authorization specification.

---

# 25. Guest Session Expiration

Guest sessions must have:

* creation time
* expiration
* revocation support where required
* abuse protection

Expired guest sessions must no longer authorize normal guest operations.

Expiration must not accidentally grant access to another guest's data.

---

# 26. Guest Session Security

Guest credentials must be:

* unpredictable
* server-generated
* protected in transport
* scoped to the guest session

The client must not be trusted merely because it knows an internal guest-session identifier.

Where tokens are used, the implementation must follow the security requirements defined in `SECURITY.md`.

---

# 27. Guest Migration

Guest migration transfers explicitly defined temporary state from:

```text
Guest Session
```

to:

```text
Registered User
```

Migration may include:

* training sessions
* training attempts
* ratings
* rating history
* XP
* achievements
* mastery
* other explicitly migratable progress

Migration does not automatically include unrelated data.

---

# 28. Migration Requirements

Guest migration must be:

* explicit
* authenticated for the destination account
* ownership-checked
* atomic where required
* idempotent
* replay-resistant
* safe against duplicate rewards
* safe against accidental overwrite

The client must not provide arbitrary source or destination ownership identifiers as proof.

---

# 29. Migration Ownership

The server must derive the guest source identity from the authenticated guest session/credential.

The destination account must come from the currently authenticated registered identity.

The server must never accept:

```text
guest_user_id = arbitrary value
```

as sufficient proof of ownership.

---

# 30. Migration Idempotency

Repeated migration requests must not duplicate:

* attempts
* sessions
* rating events
* rating changes
* XP
* achievements
* mastery
* other historical consequences

A completed migration should be treated as a terminal operation.

The system may return the existing migration outcome when a valid retry is received.

---

# 31. Migration Transaction Integrity

When migration updates multiple related records, those updates must be protected by an appropriate transaction boundary.

At minimum, the migrated authoritative state must not end in a partially transferred condition.

The implementation must inspect actual database constraints and current schema before choosing the migration strategy.

---

# 32. Authentication and Authorization Boundary

Authentication establishes:

```text
identity
```

Authorization determines:

```text
capability
+
ownership
+
relationship
+
resource access
```

Do not place all authorization rules inside authentication code.

Do not use successful login as a substitute for authorization.

---

# 33. Roles

Canonical persisted roles are:

```text
PLAYER
COACH
PARENT
ADMIN
```

New account registration assigns:

```text
PLAYER
```

as the initial default role.

Additional roles may be assigned through authorized administrative workflows.

Guest is not a role.

---

# 34. Account Creation vs Profile Creation

Registration and profile data must remain conceptually separate.

Initial registration creates the account identity required for authentication.

Additional profile data may be created during registration when the product requires it, but registration must not require unnecessary personal information.

The exact persistence model follows `DATA_MODEL.md`.

---

# 35. External Chess Identity

Authentication does not depend on:

* FIDE identity
* Lichess identity
* Chess.com identity

These are optional external profile identities.

A user must be able to authenticate and train without linking any external chess account.

External identity verification is separate from authentication.

---

# 36. Future Password Recovery

A future password-recovery capability may include:

* recovery initiation
* expiring recovery token
* password replacement
* session invalidation
* abuse controls

The exact workflow must be specified before implementation.

Do not create password-recovery infrastructure merely because it is useful in theory.

---

# 37. Future Email Verification

Email verification is future functionality.

If introduced, it must not silently become a mandatory dependency of the existing username/password registration flow unless the product scope explicitly changes.

The architecture should allow adding email verification later without making email mandatory today.

---

# 38. Future MFA and Passkeys

Future authentication may include:

* MFA
* passkeys
* OAuth/OIDC
* social login

These are extensions.

They must not force unnecessary complexity into the initial authentication implementation.

Any such addition should receive its own specification or ADR when it materially changes the authentication architecture.

---

# 39. Rate Limiting

Authentication-related operations should be protected against abuse.

Relevant operations include:

* registration
* login
* guest-session creation
* future password recovery
* future credential changes

Rate limiting should be:

* server-side
* centrally configured
* measurable
* adjustable without changing business logic

Do not embed arbitrary rate-limit rules directly into domain code.

---

# 40. Enumeration Resistance

The authentication system should avoid unnecessarily revealing account existence through:

* login responses
* registration behavior
* recovery workflows
* account-state responses

Product usability may require some differentiated responses in specific situations.

Any deliberate exception should be explicit and security-reviewed.

---

# 41. Logging Rules

Authentication logs may include security-relevant operational information such as:

* authentication success/failure
* session lifecycle
* account-status changes
* suspicious activity indicators

Authentication logs must never contain:

* plaintext passwords
* password hashes
* session secrets
* bearer tokens
* recovery secrets
* unnecessary personal data

---

# 42. Security Events

Important authentication/security events may be represented for auditing or investigation.

Examples:

```text
ACCOUNT_REGISTERED
LOGIN_SUCCEEDED
LOGIN_FAILED
SESSION_CREATED
SESSION_REVOKED
ACCOUNT_SUSPENDED
ACCOUNT_REACTIVATED
GUEST_SESSION_CREATED
GUEST_MIGRATION_COMPLETED
```

These are security/audit concepts.

They do not require a generic event bus or event-sourcing architecture.

---

# 43. Authentication Error Safety

Authentication errors must not expose:

* stack traces
* database errors
* internal paths
* password verification details
* session internals
* infrastructure details

Use the common API error contract.

---

# 44. Authentication Testing

Authentication requires automated tests for:

### Registration

* valid registration
* duplicate username
* invalid username
* invalid password
* password storage
* default `PLAYER` role

### Login

* valid login
* invalid password
* unknown username
* suspended account
* deleted/ineligible account
* session creation

### Logout

* session invalidation
* repeated logout behavior

### Sessions

* expiration
* revocation
* fixation protection
* protected endpoint behavior

### Guest

* guest creation
* guest isolation
* expiration
* revocation
* authorized guest operations

### Migration

* successful migration
* wrong-owner migration rejection
* repeated migration
* duplicate prevention
* partial-failure safety

### Abuse

* rate-limit behavior
* suspicious repeated authentication attempts

---

# 45. Authentication Definition of Done

Authentication is complete for an active phase only when the applicable requirements are satisfied:

1. registration works securely
2. default role is canonical `PLAYER`
3. passwords are securely hashed
4. login works correctly
5. logout invalidates the session
6. account status is enforced
7. sessions expire appropriately
8. sessions can be revoked
9. guest sessions are isolated
10. guest migration is safe where implemented
11. authentication endpoints have appropriate abuse protection
12. sensitive authentication data never leaks
13. authentication remains separate from authorization
14. relevant automated tests pass
15. frontend/client integration works where applicable
16. API/OpenAPI behavior matches the contract
17. no unnecessary future authentication infrastructure has been introduced

---

# 46. Implementation Rules

Before changing authentication code, the implementation agent MUST inspect:

* current user model
* current password handling
* current session implementation
* FastAPI authentication dependencies
* existing frontend auth flow
* current migrations
* authentication tests
* environment/configuration

The agent MUST NOT replace a working authentication mechanism without evidence that the active requirement requires it.

The agent MUST prefer the smallest safe change.

---

# 47. Authentication and Existing Platform

Authentication must integrate with the existing MicroChess application rather than creating a parallel identity system.

The same authenticated identity must be usable by:

* player features
* training
* ratings
* gamification
* analytics
* administration
* relationships
* support

Each domain remains responsible for its own business data.

---

# 48. Final Authentication Invariants

The following are mandatory:

```text
Authentication establishes identity.

Authorization is separate.

PLAYER is the default registered role.

Guest is not a role.

The server owns identity and session state.

The browser cannot establish ownership by supplying IDs.

Passwords are never stored plaintext.

Authentication secrets never appear in normal API responses.

Sessions are secure, expirable, and revocable.

Suspended/ineligible accounts cannot authenticate normally.

Guest migration is explicit, safe, and idempotent.

Authentication does not depend on external chess identities.

Future authentication features must not unnecessarily complicate the initial system.
```

The authentication architecture should optimize for:

```text
Security
+
Simplicity
+
Reliable Sessions
+
Low Friction
+
Clear Separation from Authorization
+
Safe Future Extension
```
