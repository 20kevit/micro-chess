# Phase 06 — Administration

## 1. Goal

Introduce a secure administrative platform for managing users, exercises, content, generators, support, and operational visibility.

---

## 2. Scope

Implement:

* admin dashboard
* user management
* role management
* exercise management
* puzzle management
* generator management
* support management
* audit visibility
* administrative analytics

Detailed rules are defined in:

```text
docs/platform/admin/
```

---

## 3. Authorization

Every administrative operation must use the canonical capabilities defined in `SECURITY.md`.

Admin role alone must not replace operation-level authorization.

At minimum, enforce:

```text
authenticated
+
active account
+
required capability
+
object/resource authorization
+
business rules
```

---

## 4. User Management

Admins should be able to:

* search and inspect users
* manage account status
* assign/revoke roles
* inspect permitted private information
* perform approved account operations

Sensitive authentication data must never be exposed.

---

## 5. Exercise and Content Management

Admins can manage:

* exercise availability
* exercise configuration
* puzzle lifecycle
* validation
* review
* approval
* publication
* retirement

Historical training data must remain intact when content is disabled or retired.

---

## 6. Generators

Admins can configure and execute content generators.

Generation must remain separate from publication:

```text
Generate
→ Validate
→ Review
→ Approve
→ Publish
```

Generators must never bypass content safety gates.

---

## 7. Support and Audit

Support workflows must be available to authorized administrators.

Important administrative actions must produce audit records.

Audit information should support investigation without exposing unnecessary sensitive data.

---

## 8. Analytics

Admins may access:

* platform analytics
* exercise analytics
* puzzle analytics
* operational metrics

Analytics is read-only and must not become an uncontrolled mechanism for changing training, rating, or gamification data.

---

## 9. Safety

Administrative workflows must protect against:

* privilege escalation
* mass assignment
* unauthorized object access
* accidental destructive operations
* historical-data corruption
* bypassing content lifecycle
* client-controlled authorization

Destructive operations require explicit safeguards.

---

## 10. Testing

Test:

* every administrative capability
* allowed/denied role access
* object-level authorization
* lifecycle transitions
* privileged operations
* audit creation
* destructive-operation safeguards
* historical-data preservation

---

## 11. Definition of Done

Phase 06 is complete when:

* all core admin domains are manageable
* canonical capabilities are enforced
* sensitive data is protected
* content lifecycle is enforced
* generators cannot bypass publication gates
* important actions are auditable
* administrative analytics is read-only
* meaningful authorization and regression tests pass
