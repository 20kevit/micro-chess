# Phase 09 — Relationships

## 1. Goal

Introduce the relationship layer required for Coach–Student and Parent–Student workflows while preserving strict privacy and object-level authorization.

---

## 2. Scope

Implement:

* Coach–Student relationships
* Parent–Student relationships
* relationship lifecycle
* invitations/acceptance where required
* relationship-scoped access
* assignments foundation
* groups/classes foundation
* relationship audit history

Detailed rules are defined in:

```text id="q4m7fz"
docs/platform/relationships/COACH_STUDENT.md
docs/platform/relationships/PARENT_STUDENT.md
```

---

## 3. Relationship Lifecycle

Relationships should use explicit states:

```text id="f2k8ad"
PENDING
→ ACTIVE
→ REVOKED
```

State transitions must be server-authorized and auditable.

---

## 4. Authorization

A relationship is **not** itself permission.

Related-user access requires:

```text id="c6y1pk"
capability
+
active relationship
+
object authorization
+
privacy/business rules
```

A coach or parent must never gain unrestricted access to a related user's account.

---

## 5. Coach–Student

Coaches may receive authorized access to:

* training progress
* exercise performance
* ratings
* relevant analytics
* assignments
* appropriate notes

Coach access must remain limited to students with an active relationship.

---

## 6. Parent–Student

Parents may receive appropriate visibility into a child's:

* training activity
* progress
* ratings
* achievements
* analytics
* mastery

Child privacy and guardian policies remain authoritative.

Multiple children must remain independently isolated.

---

## 7. Assignments

The relationship layer should support future assignments such as:

* exercise
* exercise set
* training objective
* deadline
* coach note

Assignments must not modify historical training records.

---

## 8. Groups and Classes

The foundation should allow future:

* coach groups
* classes
* multiple coaches
* multiple students
* group assignments

Group membership must never replace object-level authorization.

---

## 9. Revocation

Revoking a relationship must immediately prevent new relationship-scoped access.

It must not:

* delete historical training data
* delete the relationship's audit trail
* invalidate unrelated account permissions

---

## 10. Security

The implementation must prevent:

* access to unrelated students
* access through revoked relationships
* privilege escalation
* IDOR/object-reference attacks
* parent/coach permission mixing
* exposure of authentication/security data

---

## 11. Testing

Test:

* relationship creation
* duplicate prevention
* pending state
* acceptance
* active access
* unrelated-user denial
* revoked access
* multiple-child isolation
* coach/parent capability separation
* assignment authorization

---

## 12. Definition of Done

Phase 09 is complete when:

* both relationship types work safely
* lifecycle states are enforced
* related-user access is properly scoped
* parent and coach permissions remain separate
* assignments have a stable foundation
* revocation removes relationship-scoped access
* privacy and authorization tests pass
