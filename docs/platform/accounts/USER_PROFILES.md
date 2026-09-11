# User Profiles

## 1. Purpose

The profile represents information about a registered user that is useful for identity, personalization, training, relationships, and privacy-aware presentation.

Profile data is separate from authentication credentials.

---

## 2. Core Profile

A profile may contain:

* username
* display name
* avatar
* bio
* optional personal information
* privacy preferences
* creation/update timestamps

Username is an account identifier and must follow the platform's canonical uniqueness and validation rules.

Display name is user-facing and may be changed independently where allowed.

---

## 3. External Chess Identities

Chess identities belong to the user's profile domain.

Supported identity types:

```text
FIDE
LICHESS
CHESS_COM
```

Each identity may contain:

* provider
* username or identifier
* optional rating
* verification state
* timestamps

External ratings are informational and must **never** be treated as the user's MicroChess exercise rating.

Self-reported values are unverified unless the platform later implements provider verification.

---

## 4. Profile Privacy

Profile fields must have explicit visibility rules.

At minimum distinguish:

* private fields
* authenticated-user-visible fields
* public profile fields

Users must be able to control supported privacy settings.

Private information must not become visible merely because another user has a relationship with the player.

Coach and Parent access remains subject to capability, relationship, object authorization, and privacy rules.

---

## 5. Profile Editing

Users may update their own editable profile fields through authorized profile operations.

The server must:

* validate all fields
* enforce length and format limits
* normalize values where required
* reject unauthorized fields
* prevent mass assignment of roles, ratings, account status, or security fields

Sensitive account changes must use dedicated workflows rather than ordinary profile updates.

---

## 6. Avatar and Media

Avatar uploads must:

* validate file type and size
* reject unsafe content
* use controlled storage
* avoid executable/static-path exposure
* enforce ownership and authorization

The platform must not require an avatar.

---

## 7. Chess Profile UX

Do not create a separate "Chess Profile" domain or duplicate profile page.

FIDE, Lichess, and Chess.com identities are sections of the normal user profile.

MicroChess-specific training data remains separate:

```text
Profile
├── External Chess Identities
├── Exercise Ratings
├── Training History
├── Gamification
└── Relationships
```

---

## 8. Related Access

Coach and Parent views may expose appropriate profile information only when:

1. the viewer has the required capability
2. the relationship is active
3. object-level authorization succeeds
4. privacy rules permit access

Relationship access must never expose authentication or security data.

---

## 9. Deletion and Retention

Deleting an account must follow the platform's retention and privacy policy.

Historical training data may require anonymization or controlled retention rather than immediate physical deletion when needed for platform integrity.

Profile deletion must not corrupt historical rating, attempt, analytics, or audit records.

---

## 10. Definition of Done

Profiles are complete when:

* registered users have editable profiles
* public/private visibility is enforced
* external chess identities are supported
* external ratings remain separate from MicroChess ratings
* avatar handling is secure
* unauthorized field updates are rejected
* Coach/Parent access respects relationship and privacy rules
* profile APIs do not expose authentication secrets
* backend authorization and validation tests pass
* frontend typecheck/build/tests pass
