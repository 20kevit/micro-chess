# MicroChess Coach–Student Relationships

## 1. Purpose

Coach–Student relationships allow coaches to monitor and support assigned players without granting unrestricted access to their accounts.

The relationship layer is separate from authentication and RBAC.

---

## 2. Relationship Model

A relationship should record:

* coach
* student/player
* status
* creation time
* acceptance time
* revocation time
* optional group/class context

Recommended states:

```text
PENDING
ACTIVE
REVOKED
```

A revoked relationship must not grant access to new data.

---

## 3. Creating a Relationship

Relationship creation requires:

```text
relationships.create
```

The system must validate:

* authenticated actor
* valid coach/student accounts
* permitted role combination
* duplicate relationship prevention
* account status
* relationship state

The relationship must not automatically grant access beyond the capabilities explicitly defined for coaches.

---

## 4. Acceptance

Student acceptance requires:

```text
relationships.accept
```

The system must not treat an invitation as an active relationship before acceptance unless a future explicitly approved policy says otherwise.

Acceptance should be idempotent.

---

## 5. Coach Access

An active coach relationship may allow access to permitted student information such as:

* training progress
* exercise performance
* rating history
* gamification progress
* relevant analytics
* assigned exercises
* coach notes

Access remains subject to:

```text
capability
+
active relationship
+
object authorization
+
privacy rules
```

A relationship alone is never sufficient authorization.

---

## 6. Student Privacy

Coaches must not automatically receive:

* authentication credentials
* session tokens
* private security data
* unrelated personal information
* information outside the relationship scope

Students should be able to understand what their coach can access.

---

## 7. Assignments

The relationship layer should support future coach assignments such as:

* exercise
* exercise set
* training goal
* deadline
* optional note

Assignments must reference stable exercise/content identities.

Completing or changing an assignment must not alter historical attempts.

---

## 8. Groups and Classes

Future groups/classes may contain multiple students and one or more coaches.

Group membership must not replace object-level authorization.

A coach's access to a group does not automatically grant access to every platform resource belonging to its members.

---

## 9. Revocation

Revocation requires:

```text
relationships.revoke
```

After revocation:

* new related-data access is denied
* new assignments are blocked
* historical student data remains intact
* existing access tokens/sessions must not bypass the revoked relationship

---

## 10. Audit

Record:

* invitation/creation
* acceptance
* assignment changes
* revocation
* privileged relationship changes

Audit records should identify actor, relationship, action, and timestamp.

---

## 11. Security Rules

Coach access must follow least privilege and layered authorization rather than relying on a single role check.

The implementation must prevent:

* coach → unrelated student access
* student → coach-only data access
* revoked relationship access
* privilege escalation through relationship APIs
* IDOR/object-reference attacks

---

## 12. Definition of Done

Coach–Student infrastructure is complete when:

* relationships have explicit lifecycle states
* invitations/acceptance are safe and idempotent
* coach access requires an active relationship
* object-level authorization is enforced
* revocation immediately removes related access
* assignments can build on the relationship model
* historical training data remains intact
* relationship operations are auditable
* authorization tests cover allowed, unrelated, pending, and revoked cases
