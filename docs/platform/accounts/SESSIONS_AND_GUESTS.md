# Sessions and Guests

## 1. Purpose

This document defines authenticated sessions and temporary guest identity.

Guest access must be useful without requiring registration, while remaining isolated from persistent account data.

---

## 2. Authenticated Sessions

An authenticated session represents a registered user's active login.

The system must support:

* secure session creation
* expiration
* logout/revocation
* session rotation where security-sensitive changes require it
* protection against session fixation
* server-side validation on protected requests

The client must never be trusted to declare its own user identity or role.

---

## 3. Guest Sessions

A guest session creates a temporary server-controlled identity.

Guest sessions may access only the canonical guest capabilities:

```text
training.read
training.start
training.attempt
support.create
accounts.migrate_guest
```

Guest sessions must not receive:

* persistent account roles
* persistent player ratings
* unrestricted profile access
* Coach/Parent relationships
* administrative access

---

## 4. Guest Training Data

Guest activity may temporarily contain:

* sessions
* attempts
* exercise progress
* temporary scoring
* temporary gamification state

Guest data must remain isolated from other guests.

Guest rating is not persistent by default.

The server must be able to distinguish guest activity from registered-player activity in all relevant records.

---

## 5. Guest Lifecycle

A guest session should have:

```text id="m3u9fx"
Created
   ↓
Active
   ↓
Expired / Revoked
```

Expiration and revocation must prevent further training operations.

Cleanup of expired guest data must follow the platform's retention policy.

---

## 6. Guest → Account Migration

Migration is an explicit authenticated operation.

Requirements:

* guest identity must be valid
* target account must be authenticated/created through the supported flow
* migration must be atomic
* migration must be idempotent
* replay must not duplicate data
* ownership must be reassigned safely
* migration must be auditable

Only explicitly migratable data may be transferred.

Existing account data must never be overwritten accidentally.

---

## 7. Abuse Protection

Guest infrastructure must account for higher abuse risk because registration is not required.

Use appropriate controls such as:

* request/session rate limits
* expiration
* server-generated identifiers
* suspicious activity detection
* bounded temporary storage
* endpoint-specific limits

Do not introduce CAPTCHA or similar friction unless abuse levels justify it.

---

## 8. Authorization

Guest status is not sufficient authorization.

Every guest request must still pass:

1. valid session
2. active/non-expired session
3. required guest capability
4. object ownership/scope
5. business rules

A guest must never gain Player, Coach, Parent, or Admin capabilities through client-controlled fields.

---

## 9. Privacy

Guest data must not be publicly exposed merely because it exists.

Do not expose guest identifiers unnecessarily.

Expired or revoked guest sessions must not remain usable through stale client state.

---

## 10. Definition of Done

Sessions and guests are complete when:

* registered sessions are secure and revocable
* guest sessions are server-generated and isolated
* guest capabilities are explicitly enforced
* guest training works without registration
* guest data cannot access another guest's data
* expiration/revocation works
* guest migration is atomic and replay-safe
* cleanup/retention is defined
* abuse controls exist
* authentication and authorization tests cover positive and negative cases
* frontend typecheck/build/tests pass
