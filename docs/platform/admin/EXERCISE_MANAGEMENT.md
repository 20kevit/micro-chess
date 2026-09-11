# MicroChess Exercise Management

## 1. Purpose

Exercise management allows authorized admins to control the platform's exercise catalog without breaking existing training history or exercise-specific architecture.

The canonical exercise implementation remains defined by the existing exercise documentation and codebase.

---

## 2. Exercise Record

An exercise should expose, as applicable:

* stable identifier
* internal name
* localized title/description
* status
* supported modes
* rating configuration
* scoring configuration
* ordering/category metadata
* implementation availability
* creation/update timestamps

The exact fields must follow the existing repository model where one already exists.

---

## 3. Exercise Status

At minimum:

```text
ENABLED
DISABLED
```

Disabled exercises:

* remain visible to admins
* remain represented in historical data
* cannot start new training sessions
* must not invalidate existing attempts or ratings

Disabling an exercise is preferred over deletion when historical data exists.

---

## 4. Admin Capabilities

Exercise management follows:

```text
exercises.read
exercises.create
exercises.update
exercises.enable
exercises.disable
exercises.delete
```

Each operation requires its corresponding capability.

---

## 5. Creating an Exercise

Creating an exercise must validate:

* unique stable identifier
* required metadata
* supported modes
* valid configuration
* implementation availability
* compatibility with the exercise architecture

An exercise must not become available to players merely because an admin record was created.

---

## 6. Updating an Exercise

Admins may update configurable metadata and supported configuration.

Changes must not silently alter the meaning of historical attempts.

If a configuration change can affect scoring, rating, validation, or historical interpretation, it must be versioned or otherwise preserved according to the domain design.

---

## 7. Enable / Disable

Enabling an exercise requires explicit authorization.

Before enabling, the system should verify that the exercise is actually usable:

* implementation exists
* required configuration is valid
* required content is available
* required validation has passed

The frontend must never be the only mechanism preventing access to disabled exercises.

---

## 8. Deletion

Deletion is exceptional.

If an exercise has historical sessions, attempts, ratings, analytics, or content references, hard deletion should normally be prohibited.

Prefer:

```text
disable
→ retain historical data
```

If deletion is ever allowed, dependency checks and an explicit destructive workflow are required.

---

## 9. Player Visibility

Player-facing exercise availability must be derived from server-side state.

The client must not assume that an exercise is playable simply because it appears in the catalog.

The server determines whether the player may:

* view
* start
* attempt

an exercise.

---

## 10. Compatibility

Exercise management must preserve existing exercise-specific contracts.

An admin configuration change must not require rewriting an exercise implementation unless explicitly intended and documented.

New exercise types should follow the existing exercise architecture rather than introducing a parallel execution model.

---

## 11. Analytics and History

Disabling or modifying an exercise must not erase:

* attempts
* sessions
* rating history
* gamification events
* analytics facts

Historical records must remain interpretable after the exercise changes state.

---

## 12. Audit

Audit at minimum:

* creation
* configuration changes
* enable/disable
* deletion attempts
* destructive operations

Audit records should identify actor, action, target, timestamp, and relevant context.

---

## 13. Definition of Done

Exercise management is complete when:

* admins can safely inspect exercises
* lifecycle operations use canonical capabilities
* disabled exercises cannot start new sessions
* historical data remains intact
* destructive deletion is protected
* configuration changes cannot silently corrupt history
* server-side authorization is enforced
* meaningful tests cover lifecycle and authorization
