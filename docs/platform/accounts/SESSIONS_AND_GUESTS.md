# MicroChess — Sessions and Guests

## 1. Purpose

This document defines:

* authenticated session behavior
* temporary guest identity
* guest-owned training state
* guest lifecycle
* guest-to-account migration

Authentication rules are defined in `AUTHENTICATION.md`.

Security and authorization rules are defined in `SECURITY.md`.

The logical data model is defined in `DATA_MODEL.md`.

---

## 2. Authenticated Sessions

An authenticated session represents an active login for a registered user.

Sessions must support:

* secure creation
* expiration
* logout/revocation
* fixation protection
* server-side identity validation
* rotation where required by security-sensitive changes

The client cannot establish identity or role by submitting IDs or role values.

### Active role per session

A user may hold several persisted roles, but each authenticated session
carries exactly one active role:

* single-role accounts: the session's active role is that role
* multi-role accounts: the role is selected at login (from the account's
  own assigned set, only after successful authentication) or switched
  later through an authenticated role-switch operation

The active role selects which role-based capability set applies to the
session; object-level checks (relationships, ownership, privacy) still
apply unchanged. The active role is resolved server-side on every
request and is never trusted from the client: a requested role outside
the account's assigned set is rejected, and a session whose active role
is no longer assigned authorizes as nothing (fail closed) until the
client re-authenticates. Role selection/switching never grants, revokes,
or otherwise modifies the account's assigned roles.

---

## 3. Guest Identity

A guest is a temporary server-controlled identity.

Guest is **not** a persisted role.

A guest session must have:

```text id="bmsx8c"
Created
  ↓
Active
  ↓
Expired / Revoked
```

Expired or revoked sessions cannot authorize further guest operations.

---

## 4. Guest Scope

Guest access is intentionally narrower than registered-user access.

A guest may use supported training functionality without registration.

Guest access must not provide:

* persistent account roles
* administrative access
* unrestricted profile access
* Coach/Parent capabilities
* access to another user's or guest's data

The exact capability mapping is owned by `ROLES_AND_PERMISSIONS.md` and `SECURITY.md`.

---

## 5. Guest Training State

Guest activity may temporarily include:

* training sessions
* attempts
* progress
* scores
* exercise-specific rating state
* gamification state

Guest state must remain isolated from other guests.

When a guest session is migrated, only explicitly migratable state is transferred to the registered account.

---

## 6. Guest Ownership

Guest-owned records must be associated with the server-controlled guest session.

The client must never establish ownership by submitting an arbitrary guest identifier.

Every guest operation must verify:

1. valid guest session
2. active/non-expired state
3. required capability
4. resource ownership/scope
5. domain rules

---

## 7. Guest Rating

Guest exercise ratings may exist temporarily while the guest trains.

They must remain clearly distinguishable from registered-player ratings.

On migration, eligible guest rating state and history may be transferred according to the rating domain rules.

The client cannot directly set or modify guest ratings.

---

## 8. Guest Migration

Migration is an explicit operation that transfers eligible guest state to an authenticated registered account.

Migration must be:

* ownership-checked
* atomic where required
* idempotent
* replay-safe
* non-destructive to existing account data
* auditable where required

The server determines the source guest session and destination account.

The client must not submit arbitrary source/destination ownership identifiers.

---

## 9. Migration Scope

Only explicitly migratable data may be transferred.

Potential examples:

* training sessions
* attempts
* progress
* ratings
* rating history
* XP
* achievements
* mastery

The exact migration set belongs to the relevant domain specifications.

Unrelated account data must not be overwritten.

---

## 10. Abuse and Retention

Guest access requires proportionate abuse protection, such as:

* rate limiting
* expiration
* bounded temporary storage
* server-generated identifiers
* endpoint-specific limits

Do not add CAPTCHA or equivalent friction without evidence that it is necessary.

Expired guest data must follow the platform retention policy.

---

## 11. Privacy

Guest data is private by default.

Do not expose guest identifiers unnecessarily.

Stale client state must not keep expired or revoked guest sessions usable.

---

## 12. Completion Criteria

For an active implementation phase, the applicable session/guest capability is complete when:

* authenticated sessions work securely
* guest sessions are server-controlled and isolated
* expiration/revocation works
* guest ownership is enforced server-side
* migration is safe and replay-resistant where implemented
* relevant positive and negative tests pass
* no unnecessary authentication/session infrastructure is introduced
