# MicroChess — User Profiles

## 1. Purpose

A user profile contains non-authentication information used for:

* personalization
* player identity
* external chess identities
* privacy-aware presentation
* relationships

Authentication credentials and account security data do not belong to the profile.

`AUTHENTICATION.md` owns authentication behavior.
`SECURITY.md` owns security and privacy rules.
`DATA_MODEL.md` owns the logical data model.

---

## 2. Profile Data

A profile may contain:

* display name
* avatar
* bio
* optional personal information
* privacy preferences

The username belongs to the account identity and follows the canonical username rules defined by `AUTHENTICATION.md`.

Not all fields are required.

Do not collect personal information without a product requirement.

---

## 3. External Chess Identities

External chess identities are part of the player's profile.

Supported providers:

```text
FIDE
LICHESS
CHESS_COM
```

An external identity may contain:

* provider
* external username/identifier
* optional rating
* verification state

External ratings are informational and are always separate from MicroChess exercise ratings.

Self-reported ratings remain unverified unless an explicit verification mechanism exists.

---

## 4. Profile Privacy

Profile visibility must distinguish between information that is:

* private
* visible to authenticated users
* publicly visible

Only supported privacy settings should be exposed to users.

Relationship-based access does not bypass privacy restrictions.

Coach and Parent access follows the canonical authorization and relationship rules defined in `SECURITY.md`.

---

## 5. Profile Editing

Users may update only their own editable profile fields.

The server must validate all submitted fields.

Profile updates must not allow modification of:

* roles
* account status
* ratings
* security state
* authentication credentials
* other server-managed fields

Sensitive account operations must use their dedicated workflows.

Do not implement profile editing as unrestricted mass assignment.

---

## 6. Avatar and Profile Media

Avatars are optional.

When uploads are supported, they must use the platform's standard secure media handling:

* allowed file types
* size limits
* controlled storage
* ownership checks
* authorized access

Detailed file-security rules belong in `SECURITY.md`.

---

## 7. External Chess Identity Independence

Do not create a separate Chess Profile domain.

External identities are sections of the normal player profile.

Conceptually:

```text
Profile
├── External Chess Identities
├── Exercise Ratings
├── Training History
└── Gamification
```

These remain separate domains even when presented together in the UI.

---

## 8. Related-User Access

Coach and Parent views may expose profile information only when the canonical authorization rules permit it.

Profile access must never expose:

* passwords
* authentication credentials
* session secrets
* private security information

---

## 9. Account Deletion and Retention

Profile deletion must follow the platform's privacy and retention policy.

Deleting a profile must not casually corrupt historical:

* attempts
* ratings
* analytics
* audit records

Where historical integrity requires it, personal information may need to be anonymized rather than physically deleting the entire historical record.

Detailed retention behavior belongs in `DATA_MODEL.md` and `SECURITY.md`.

---

## 10. Product Rule

The profile exists to support player identity and personalization.

It must not become a container for unrelated:

* training logic
* ratings
* gamification logic
* analytics logic
* authorization logic

Those domains retain their own ownership and behavior.
