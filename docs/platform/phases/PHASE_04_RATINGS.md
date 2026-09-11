# Phase 04 — Ratings

## 1. Goal

Introduce reliable, independent player ratings for each exercise.

Ratings must become a measurable representation of exercise performance without coupling exercises to one global chess rating.

---

## 2. Scope

Implement:

* per-exercise rating
* provisional state
* rating history
* rating events
* rated/unrated attempts
* atomic rating updates
* duplicate/replay protection
* player rating views
* rating analytics foundation

Detailed rules are defined in:

```text id="r8j3qk"
docs/platform/training/RATINGS.md
```

---

## 3. Rating Independence

Each exercise has its own rating.

For example:

```text id="4tqz2m"
Piece Recognition → rating A
Pin              → rating B
Mental Calculation → rating C
```

A player's performance in one exercise must not directly change another exercise's rating.

---

## 4. Rating Updates

A valid rated attempt may produce:

```text id="j8s1kp"
rating_before
rating_change
rating_after
```

The update must be performed server-side and atomically with the corresponding attempt result.

The client must never submit the final rating change.

---

## 5. Provisional Ratings

New exercise ratings begin as provisional.

The system should retain enough information to support future uncertainty/development calculations.

Do not implement a complex Glicko-style system unless the current requirements actually need it.

The data model should remain compatible with a future upgrade.

---

## 6. Rating Events

Every rating change creates an immutable event containing enough information to reconstruct the change.

At minimum:

* player
* exercise
* source attempt
* rating before
* change
* rating after
* timestamp
* source/context

---

## 7. Rated vs Unrated

The system must explicitly determine whether an attempt is rated.

Examples of potentially unrated activity:

* practice mode
* administrative/test activity
* invalid/replayed submission
* future explicitly defined cases

The client must not be able to force an attempt to be rated.

---

## 8. External Ratings

FIDE, Lichess, and Chess.com ratings remain separate from MicroChess exercise ratings.

External ratings may help estimate initial difficulty/training level later, but they must never silently modify MicroChess ratings.

---

## 9. Integrity

The rating system must prevent:

* duplicate submission
* replayed attempts
* client-controlled rating changes
* unauthorized rating modification
* inconsistent attempt/rating state

Administrative corrections or recalculations must use explicit privileged operations and remain auditable.

---

## 10. Testing

Test:

* first rated attempt
* provisional rating
* rating increase/decrease
* multiple exercises independently
* unrated attempts
* duplicate/replayed attempts
* atomic failure scenarios
* unauthorized modification
* rating history consistency

---

## 11. Definition of Done

Phase 04 is complete when:

* every supported exercise can maintain an independent rating
* rating changes are server-authoritative
* rating history is immutable
* rated/unrated behavior is explicit
* duplicate submissions cannot corrupt ratings
* external ratings remain separate
* meaningful rating and authorization tests pass
