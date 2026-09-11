# Authentication

## 1. Purpose

Authentication establishes the identity of registered users and provides temporary identity for guests.

Authorization is separate and is defined by the platform capability and role system.

---

## 2. Registration

Initial registration requires only:

* unique username
* password

Do not require profile information or chess identities during registration.

Optional profile and external chess identity information may be added later.

Registration must:

* normalize/validate username according to canonical rules
* securely hash the password
* reject duplicate usernames
* create the default `player` role
* create required profile/account records
* create an auditable account event where applicable

---

## 3. Login

Login must:

1. validate credentials server-side
2. reject inactive/suspended/deleted accounts
3. establish an authenticated session
4. return only safe account information

Never expose:

* password hashes
* authentication secrets
* session internals
* security tokens not intended for the client

Authentication errors should not unnecessarily reveal whether a username exists.

---

## 4. Password Security

Passwords must:

* never be stored in plaintext
* use a modern password hashing algorithm supported by the backend
* never appear in logs
* never be returned through API responses

Password policy should balance security with child-friendly usability.

Future password reset/change flows must use separate secure workflows and must not weaken normal authentication.

---

## 5. Sessions

Sessions must have:

* server-generated identifiers/tokens
* expiration
* revocation support
* secure transport
* appropriate cookie/security attributes when cookie-based
* protection against session fixation

Logout must invalidate the authenticated session.

Changing sensitive authentication state should invalidate or rotate relevant sessions where appropriate.

---

## 6. Guest Authentication

Guests receive a temporary server-generated identity.

Guest access is intentionally narrower than authenticated Player access.

Canonical guest capabilities are:

```text
training.read
training.start
training.attempt
support.create
accounts.migrate_guest
```

Guest sessions must support:

* expiration
* revocation
* abuse controls
* temporary training history
* safe migration to a registered account

Guest is **not** a persisted role.

---

## 7. Guest Migration

Guest → registered account migration must be:

* explicit
* atomic
* idempotent
* replay-resistant
* auditable

The migration must preserve only data that the platform explicitly defines as migratable.

It must never overwrite an existing account's unrelated data.

A repeated migration request must not duplicate attempts, ratings, XP, achievements, or relationships.

---

## 8. Account Status

Authentication must respect account status:

```text
ACTIVE
SUSPENDED
DELETED
```

Only eligible active accounts may authenticate normally.

Suspension immediately blocks normal authenticated access.

Deleted accounts must follow the platform's deletion/retention policy.

---

## 9. Rate Limiting and Abuse Protection

Authentication endpoints should support protection against:

* repeated failed logins
* registration abuse
* guest-session abuse
* credential stuffing
* automated account creation

Limits must be configurable and must not be hard-coded into business logic.

---

## 10. Future Authentication

The architecture should allow later addition of:

* email verification
* password reset
* MFA
* passkeys
* social login

These are extensions to authentication, not reasons to complicate the initial implementation.

---

## 11. Definition of Done

Authentication is complete when:

* registration works securely
* login/logout work correctly
* sessions are secure and revocable
* account status is enforced
* guest sessions work
* guest migration is safe
* authentication endpoints are rate-limited appropriately
* sensitive authentication data never leaks
* authorization remains separate from authentication
* backend tests cover success, failure, expiration, revocation, and abuse cases
* frontend typecheck/build/tests pass
