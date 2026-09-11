# Phase 02 — Accounts & Identity

## 1. Goal

Introduce persistent user accounts, authentication, profiles, roles, and guest-to-account migration without breaking existing guest training or exercises.

---

## 2. Scope

Implement:

* registration
* login/logout
* authenticated sessions
* account identity
* user profile
* external chess identities
* canonical roles
* authorization capabilities
* guest sessions
* guest → account migration

Registration requires only:

```text
username
password
```

Additional profile information is optional after registration.

---

## 3. Roles

The only persisted roles are:

```text
PLAYER
COACH
PARENT
ADMIN
```

`GUEST` is a temporary access subject, not a persisted role.

Capabilities and role mappings must follow `SECURITY.md`.

---

## 4. Profiles

Player profiles may contain:

* username
* display name
* avatar
* bio
* optional personal information
* privacy settings
* FIDE identity/rating
* Lichess identity/rating
* Chess.com identity/rating

External chess ratings are separate from MicroChess exercise ratings.

Self-reported external identities must be clearly distinguishable from verified data.

---

## 5. Guest Migration

Existing guest infrastructure must remain usable.

A guest may migrate to a registered account through:

```text
accounts.migrate_guest
```

Migration must be:

* atomic
* idempotent
* replay-resistant
* auditable
* limited to the correct guest identity

Only data explicitly defined as migratable may be transferred.

---

## 6. Authentication Security

Authentication must follow `SECURITY.md`.

At minimum:

* secure password hashing
* session invalidation on logout
* protection against brute-force attempts
* secure session identifiers
* account-status checks
* server-side authentication state

Future password recovery, email verification, MFA, passkeys, and social login must be designed as extensions rather than blocking the initial account system.

---

## 7. Authorization

Every protected operation must evaluate:

```text
authentication
+
account status
+
capability
+
object/relationship authorization
+
business rules
```

Frontend role checks are UX only.

---

## 8. Compatibility

Account implementation must preserve:

* existing exercise behavior
* guest training
* current exercise scoring
* existing puzzle delivery
* current responsive exercise UX

Do not rewrite exercise implementations merely to introduce accounts.

---

## 9. Testing

Meaningful tests must cover:

* registration
* duplicate usernames
* login/logout
* invalid credentials
* suspended accounts
* session invalidation
* role/capability authorization
* guest access
* guest migration
* migration replay protection
* profile privacy
* external identity separation
* existing exercise regression

---

## 10. Definition of Done

Phase 02 is complete when:

* users can safely register and authenticate
* persistent profiles exist
* canonical roles/capabilities are enforced
* guest sessions remain functional
* guest data can safely migrate to accounts
* external chess identities remain separate from internal ratings
* protected APIs enforce server-side authorization
* security and regression tests pass
