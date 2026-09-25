# MicroChess Admin Overview

## 1. Purpose

The Admin area provides authorized administrators with centralized management and operational visibility.

Admin functionality is divided into:

* Users
* Roles
* Exercises
* Puzzles
* Generators
* Analytics
* Support
* Audit
* System operations

---

## 2. Authorization

Admin access requires:

```text
authenticated
+
active account
+
ADMIN role
+
required capability
```

The frontend MUST NOT be treated as an authorization boundary.

Every administrative operation must be authorized server-side.

---

## 3. Admin Dashboard

The dashboard should provide a concise operational overview:

* total users
* active users
* recent registrations
* training activity
* exercise usage
* content status
* generator jobs
* support items
* important system warnings

The dashboard is an overview, not the primary management interface.

---

## 4. User Management

Admins can manage users according to the canonical capabilities:

* view users
* view permitted private data
* assign/revoke roles
* suspend/reactivate accounts
* delete accounts where permitted

User management must preserve auditability.

Detailed behavior belongs in:

```text
docs/platform/admin/USER_MANAGEMENT.md
```

---

## 5. Exercise Management

Admins can manage exercise availability and configuration.

Core operations:

```text
read
create
update
enable
disable
delete
```

Deleting or disabling an exercise must not silently destroy historical training data.

Detailed rules belong in:

```text
docs/platform/admin/EXERCISE_MANAGEMENT.md
```

---

## 6. Puzzle Management

Admins manage the puzzle/content lifecycle:

```text
Draft
→ Created/Generated
→ Validated
→ Reviewed
→ Approved
→ Published
→ Active
→ Retired
```

Production content must pass the required validation/review gates.

Detailed rules belong in:

```text
docs/platform/admin/PUZZLE_MANAGEMENT.md
```

---

## 7. Generators

Generators create candidate content but do not automatically publish it.

Admins can:

* configure generators
* run generation jobs
* monitor jobs
* cancel jobs
* inspect generated content
* send candidates through validation/review

Detailed rules belong in:

```text
docs/platform/admin/GENERATORS.md
```

---

## 8. Analytics

Admins may access platform-level analytics and authorized exercise/puzzle analytics.

Analytics is read-only.

Administrative analytics MUST NOT become a mechanism for directly modifying training, rating, or gamification facts.

---

## 9. Support

Admins can manage support requests according to:

```text
support.read
support.respond
support.close
support.manage
```

Support actions should be auditable.

---

## 10. Audit

Sensitive administrative operations should produce audit records.

At minimum, audit data should identify:

* actor
* action
* target
* timestamp
* relevant result/context

Audit records must not be silently modified or deleted through normal admin workflows.

---

## 11. System Operations

System-level capabilities such as:

```text
system.jobs
system.maintenance
system.recalculate
```

are restricted to explicitly authorized administrators.

These operations must have stronger safeguards than ordinary CRUD operations.

---

## 12. Admin UX

The admin interface may be denser than the Player interface.

It should prioritize:

* search
* filtering
* tables
* clear status indicators
* bulk-safe workflows
* confirmation for destructive actions
* audit visibility
* responsive operation on tablet/mobile where practical

Destructive actions should require explicit confirmation.

---

## 13. Data Safety

Admin actions MUST NOT:

* bypass domain validation
* directly mutate historical facts without an approved correction path
* expose secrets
* expose unrelated private user data
* bypass content lifecycle rules
* trust client-provided authorization
* silently delete dependent historical data

---

## 14. Phase 13 Control Center

The production Admin surface uses a single RTL sidebar shell and keeps
Exercise detail as the primary content workspace. The library, review
queue, one-candidate generator, user detail, commercial views, analytics,
insights, support, system health, and audit views all consume the same
backend contracts and server-side totals.

The UI is an operator surface, not a second business layer:

* answer correctness, lifecycle gates, rating effects, and scoring stay
  backend-owned;
* list filters and audit date windows run on the server;
* a draft delete is offered only when the backend proves it is safe;
* user verification displays only masked status and channel labels;
* support reopen, quarantine, rejection, and other state changes require
  the corresponding capability and produce audit records.

Telegram verification is disabled by default in production. Its backend
implementation and channel contract remain available for an explicit
configuration change; Bale remains the default verification path.

---

## 15. Definition of Done

The Admin platform is complete when:

* every admin operation uses canonical capabilities
* object-level authorization is enforced
* sensitive actions are auditable
* content lifecycle is enforced
* historical training data is protected
* analytics remains read-only
* destructive operations are safeguarded
* detailed admin modules follow this shared policy
