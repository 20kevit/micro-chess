# MicroChess User Management

## 1. Purpose

Admin user management provides controlled management of accounts, roles, status, and access.

All operations must follow the canonical capability vocabulary in `SECURITY.md`.

---

## 2. User List

Admins with `users.read` may view users with:

* search by username/display name
* filter by role
* filter by account status
* registration date
* last activity
* pagination
* sorting

The list must expose only fields permitted by the viewer's capabilities.

---

## 3. User Details

An authorized admin may view a user's permitted account and platform information, including:

* account identity
* profile information
* roles
* account status
* registration date
* last activity
* training summary
* rating summary
* relevant relationships
* support history where authorized

Sensitive fields must require `users.read_private`.

---

## 4. Account Status

The platform must distinguish at least:

```text
ACTIVE
SUSPENDED
DELETED
```

Suspension prevents normal authenticated use while preserving historical records.

Deletion must follow the retention/privacy rules defined in `SECURITY.md` and must not silently destroy historical facts required for system integrity.

---

## 5. Role Management

Role assignment and removal require:

```text
roles.assign
roles.revoke
```

Only the canonical roles are valid:

```text
PLAYER
COACH
PARENT
ADMIN
```

`GUEST` is not a persisted role.

Role changes must:

* be server-authorized
* validate the target account
* prevent invalid role states
* be auditable
* take effect consistently across active sessions

Role names must not be used as a substitute for capability checks.

---

## 6. Suspension and Reactivation

Suspension requires:

```text
users.suspend
```

Reactivation requires:

```text
users.reactivate
```

A suspension should:

* prevent new authenticated actions
* invalidate or restrict active sessions as defined by authentication policy
* preserve historical data
* record the action in the audit trail

Reactivation restores normal account access subject to all other authorization rules.

---

## 7. Self-Protection

The system must prevent an administrator from accidentally removing the last viable administrative access path.

At minimum:

* an admin cannot remove the final `ADMIN` role without another valid admin remaining
* privileged role changes require explicit confirmation
* privileged changes are audited

The implementation must avoid creating an irreversible administrative lockout.

---

## 8. Bulk Operations

Bulk user operations may be supported for safe, reversible actions such as:

* status filtering
* role-based filtering
* export where authorized

Bulk destructive or privileged changes require stronger safeguards and must not bypass per-user authorization and audit requirements.

---

## 9. Privacy

Admin visibility is capability-based, not automatically unlimited.

The system must distinguish:

```text
users.read
users.read_private
```

Private profile, authentication, security, and other sensitive information must not be exposed merely because the viewer is inside the admin UI.

Secrets such as password hashes, session tokens, reset tokens, and authentication secrets must never be returned.

---

## 10. Audit

The following actions should produce audit records:

* role assignment/removal
* suspension/reactivation
* deletion
* privileged account changes
* access to sensitive administrative data where required by policy

Audit records must identify actor, action, target, timestamp, and relevant context.

---

## 11. Security Rules

User management MUST:

* enforce authorization server-side
* use least privilege
* validate all target IDs
* prevent mass-assignment vulnerabilities
* prevent privilege escalation
* never trust frontend role/capability state
* preserve historical training integrity

These rules follow the platform's canonical security model.

---

## 12. Definition of Done

User management is complete when:

* users can be safely searched and inspected
* roles can be assigned/revoked through canonical capabilities
* account status can be managed
* privileged operations are audited
* sensitive fields are protected
* historical data remains intact
* authorization is enforced at the API/domain boundary
* meaningful authorization tests cover success and denial cases
