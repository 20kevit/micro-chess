# MicroChess Parent–Student Relationships

## 1. Purpose

Parent–Student relationships provide guardians with controlled visibility into a child's MicroChess activity and progress.

The relationship layer is separate from authentication and RBAC.

---

## 2. Relationship Model

A relationship should record:

* parent
* student
* status
* creation time
* acceptance/confirmation time where required
* revocation time
* guardian/consent metadata when applicable

Recommended states:

```text
PENDING
ACTIVE
REVOKED
```

For minors, the platform must follow the consent and privacy rules defined in `SECURITY.md`.

---

## 3. Creating a Relationship

Relationship creation requires:

```text
relationships.create
```

for flows where the parent initiates the relationship.

The system must validate:

* authenticated accounts
* valid parent/student roles
* duplicate relationship prevention
* account status
* relationship state
* applicable child/guardian policy

A relationship must never grant unrestricted access to the child's account.

---

## 4. Acceptance and Confirmation

Where student or guardian confirmation is required, the relationship remains `PENDING` until the required confirmation is completed.

Operations must be idempotent.

The implementation must not assume that merely knowing a student's username is sufficient proof of guardianship.

---

## 5. Parent Access

An active parent relationship may provide access to appropriate child information such as:

* training activity
* exercise progress
* ratings
* analytics
* achievements
* streaks
* mastery
* relevant assignments
* progress summaries

Access remains subject to:

```text
capability
+
active relationship
+
object authorization
+
privacy/guardian policy
```

A parent relationship alone is never sufficient authorization.

---

## 6. Sensitive Information

Parents must not automatically receive:

* password
* password hash
* session tokens
* authentication secrets
* unrelated private information
* internal security data

The platform should expose only information necessary for legitimate parental oversight.

---

## 7. Multiple Children

A parent may have multiple active child relationships.

Each child must remain an independently authorized object.

The parent must never gain access to one child merely because another child is linked to the same parent.

---

## 8. Coach Interaction

A child may simultaneously have:

* a parent relationship
* one or more coach relationships

These relationships are independent.

Parent access must not grant coach-management capabilities, and coach access must not grant parental capabilities.

---

## 9. Revocation

Revocation requires:

```text
relationships.revoke
```

After revocation:

* new child-data access is denied
* relationship-scoped operations are denied
* historical training data remains intact
* revoked access cannot be bypassed through cached client state or old relationship identifiers

---

## 10. Privacy and Child Safety

MicroChess is child-first.

For minors:

* minimize collected personal information
* keep child data private by default
* do not expose private child information through public profiles/leaderboards
* separate educational progress from unrelated personal data
* preserve guardian/privacy controls
* avoid collecting information that is not necessary for the product

---

## 11. Audit

Record important relationship operations:

* creation/invitation
* acceptance/confirmation
* access-policy changes
* revocation
* privileged relationship changes

Audit records should identify actor, relationship, action, and timestamp.

---

## 12. Definition of Done

Parent–Student infrastructure is complete when:

* parent relationships have explicit lifecycle states
* guardianship is not inferred from usernames alone
* access requires an active relationship and appropriate capability
* multiple children remain independently isolated
* coach and parent permissions remain separate
* revocation removes relationship-scoped access
* child privacy rules are enforced server-side
* relationship operations are auditable
* authorization tests cover allowed, unrelated, pending, and revoked cases
