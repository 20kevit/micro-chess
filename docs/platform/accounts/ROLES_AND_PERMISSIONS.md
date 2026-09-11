# Roles and Permissions

## 1. Purpose

The platform uses role-based access control combined with capability checks and object-level authorization.

Roles identify the user's responsibility. Capabilities define what actions are allowed.

Authorization is always enforced server-side.

---

## 2. Canonical Roles

Persist only these roles:

```text id="1b7y8t"
player
coach
parent
admin
```

`GUEST` is not a persisted role.

Guest access uses the explicitly defined guest capability policy.

---

## 3. Capability Model

Capabilities use the canonical format:

```text id="8q4f6v"
<resource>.<action>
```

Examples:

```text id="x8c2kr"
profile.read
training.start
history.read
ratings.read
users.manage
puzzles.publish
generators.run
```

Capabilities must come from the canonical capability registry.

Do not create aliases or role-specific capability names such as `coach.read_students`.

---

## 4. Baseline Role Capabilities

### Player

A Player can:

* manage their own profile
* manage permitted external chess identities
* train
* submit attempts
* view their history
* view their ratings
* view their gamification
* view their analytics
* use permitted leaderboards
* create and view their own support requests

### Coach

Coach includes Player capabilities plus permitted student-related capabilities:

* read related history
* read related ratings
* read related gamification
* read related analytics
* manage permitted relationships
* manage permitted student assignments

Access still requires an active Coach–Student relationship.

### Parent

Parent includes Player capabilities plus permitted child-related read capabilities:

* read related history
* read related ratings
* read related gamification
* read related analytics
* read permitted relationships

Parent does not automatically receive Coach assignment-management capabilities.

Access still requires an active Parent–Student relationship.

### Admin

Admin receives the administrative capabilities required to manage:

* users
* roles
* exercises
* puzzles
* generators
* platform/exercise/puzzle analytics
* support
* audit
* system operations

Admin access remains subject to object and business-rule checks.

---

## 5. Authorization Decision

A successful role/capability check is not sufficient by itself.

The final decision must consider:

1. authentication state
2. account status
3. capability
4. object ownership or relationship
5. resource state
6. privacy rules
7. business rules

Conceptually:

```text id="h6u8jj"
Allow =
    authenticated
    AND active_account
    AND required_capability
    AND object_access
    AND privacy_allows
    AND business_rules_allow
```

Guest requests follow the separate guest capability policy.

---

## 6. Object-Level Authorization

Examples:

* Player can read their own history.
* Coach can read a student's history only through an active relationship.
* Parent can read a child's permitted progress only through an active relationship.
* Admin may manage users, but sensitive fields remain restricted.
* A capability never grants access to every object automatically.

Object authorization must be implemented in the application/domain authorization layer, not trusted to the frontend.

---

## 7. Role Assignment

Only authorized administrative operations may assign or revoke roles.

Allowed persisted role IDs are exactly:

```text id="2t6j0e"
player
coach
parent
admin
```

Role changes must:

* validate the target role
* be auditable
* enforce self-protection rules
* not modify historical training records
* not silently grant unrelated capabilities

---

## 8. Frontend Rules

The frontend may hide or disable UI based on known permissions, but this is only a UX optimization.

It must never be treated as authorization.

Every protected API operation must independently enforce authorization on the server.

---

## 9. Definition of Done

Roles and permissions are complete when:

* canonical roles are implemented
* capabilities come from one registry
* role-to-capability mappings are explicit
* object-level authorization exists
* Coach/Parent relationship boundaries are enforced
* role changes are protected and audited
* frontend permission checks do not replace backend checks
* unauthorized requests return the correct authorization response
* backend authorization tests cover every role
* security-sensitive capability boundaries have negative tests
