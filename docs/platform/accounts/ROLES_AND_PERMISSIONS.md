# MicroChess — Roles and Permissions

## 1. Purpose

MicroChess uses:

* canonical roles
* capabilities
* object-level authorization

Roles describe an identity's responsibilities.

Capabilities describe permitted actions.

Authorization is always enforced server-side.

Detailed security rules belong to `SECURITY.md`.

Authentication behavior belongs to `AUTHENTICATION.md`.

---

## 2. Canonical Roles

The only persisted roles are:

```text
PLAYER
COACH
PARENT
ADMIN
```

`GUEST` is not a persisted role.

Guest access follows the separate guest capability policy defined by the authentication/security specifications.

A user may have more than one persisted role.

---

## 3. Capability Model

Capabilities use:

```text
<resource>.<action>
```

Examples:

```text
profile.read
training.start
history.read
ratings.read
users.manage
puzzles.publish
generators.run
analytics.view
```

The application must maintain **one canonical capability registry**.

Do not create role-specific aliases such as:

```text
coach.read_students
admin.manage_users
```

Relationship and object access must be evaluated separately from the capability itself.

---

## 4. Baseline Role Scope

### PLAYER

A player may, subject to ownership and privacy rules:

* manage their profile
* manage permitted external chess identities
* train
* submit attempts
* view their history
* view their ratings
* view their gamification
* view their analytics
* use permitted leaderboards
* create and view their own support requests

### COACH

A coach has the applicable Player capabilities plus capabilities for authorized students, such as:

* read permitted student history
* read permitted student ratings
* read permitted student gamification
* read permitted student analytics
* manage permitted coach/student relationships
* manage permitted assignments

An active Coach–Student relationship is still required.

### PARENT

A parent has the applicable Player capabilities plus permitted child-related read access, such as:

* read permitted history
* read permitted ratings
* read permitted gamification
* read permitted analytics
* manage permitted parent/student relationships

A parent does not automatically receive coach assignment-management capabilities.

An active Parent–Student relationship is still required.

### ADMIN

An administrator has the capabilities required for authorized platform operations, including where applicable:

* users
* roles
* exercises
* puzzles
* generators
* analytics
* support
* audit

Administrative capability does not bypass domain validation, object authorization, privacy, or business rules.

---

## 5. Authorization Decision

Role/capability alone does not authorize access.

The final decision may depend on:

```text
authentication
+
account status
+
capability
+
ownership or relationship
+
resource state
+
privacy
+
business rules
```

The detailed security semantics are defined in `SECURITY.md`.

---

## 6. Object-Level Authorization

Examples:

* A player may access their own training history.
* A coach may access a student's permitted data only through an active relationship.
* A parent may access a child's permitted data only through an active relationship.
* An administrator may manage users within their authorized scope.
* A capability does not grant unrestricted access to every object.

Object-level authorization is a backend concern.

Frontend permission checks are UX only.

---

## 7. Role Assignment

Only authorized administrative operations may assign or revoke roles.

Role changes must:

* use one of the canonical roles
* be authorized
* be auditable
* respect self-protection rules
* preserve historical training data

Role assignment must not silently grant unrelated capabilities outside the canonical mapping.

---

## 8. Capability Mapping

The initial implementation may map roles to capabilities statically.

A dedicated permission-management subsystem is **not required** unless an active product requirement needs it.

Do not introduce a policy engine merely to represent the role/capability relationship.

---

## 9. Frontend Rule

The frontend may hide or disable controls based on known permissions.

This is only a UX optimization.

Every protected API operation must independently enforce authorization on the server.

---

## 10. Source of Truth

This document owns:

* canonical persisted roles
* role-level capability scope
* role/capability terminology

`SECURITY.md` owns the detailed authorization and security model.

`API_CONTRACTS.md` owns API-level enforcement requirements.

`AUTHENTICATION.md` owns identity/session establishment.

No other document should redefine the canonical roles.

---

## 11. Completion Criteria

This capability is complete when the active phase has:

* canonical roles implemented
* one canonical capability registry
* explicit role-to-capability mapping
* object-level authorization
* relationship boundaries for Coach/Parent
* protected role changes
* backend enforcement on protected operations
* relevant authorization tests, including negative cases
