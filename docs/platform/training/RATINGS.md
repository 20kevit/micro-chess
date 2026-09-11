# MicroChess Ratings

## 1. Purpose

MicroChess uses a separate rating for each exercise.

A player's rating in one exercise MUST NOT directly change their rating in another exercise.

The rating system measures performance within MicroChess training, not official chess strength.

---

## 2. Rating Scope

Each rating belongs to:

```text
player + exercise
```

Therefore a player may have:

```text
Piece Recognition: 1520
Pin: 1370
Mental Calculation: 1640
```

There is no requirement for a single global MicroChess rating.

---

## 3. Rating Record

A rating record should support at least:

* player
* exercise
* current rating
* games/attempts counted
* provisional state
* uncertainty/development state
* created timestamp
* updated timestamp

The exact database schema belongs to `DATA_MODEL.md`.

---

## 4. Rating History

Every rating change MUST produce an immutable rating event containing enough information to reconstruct the change.

At minimum:

```text
rating_before
rating_change
rating_after
source attempt/session
timestamp
```

Historical rating events MUST NOT be silently overwritten when the current rating changes.

---

## 5. Rating Updates

Rating updates are server-authoritative.

The client MUST NOT submit:

* rating
* rating change
* expected score
* provisional status
* rating event

as authoritative values.

The server calculates and persists them after validating the attempt.

---

## 6. Provisional Ratings

New exercise ratings are provisional until enough valid training data exists.

The exact provisional threshold may be configured by the rating implementation.

The system should retain enough information to later support:

* confidence/uncertainty
* rating stabilization
* recalculation
* future Glicko-compatible behavior

Do not implement Glicko unless explicitly required by a later phase.

---

## 7. Attempt Eligibility

Not every interaction must necessarily affect rating.

The rating service must receive an explicit decision about whether an attempt is:

```text
rated
unrated
```

Practice/Speed behavior follows the exercise specification.

Existing exercise rules remain authoritative.

---

## 8. Rating Integrity

Rating changes MUST be based only on validated server-side results.

Invalid, duplicated, unauthorized, or replayed submissions MUST NOT create additional rating changes.

Rating updates and their corresponding attempt records should be committed atomically.

---

## 9. Administration

Administrators may eventually need:

```text
ratings.read
ratings.recalculate
ratings.correct
```

The latter two are administrative capabilities and MUST NOT be granted to normal Players.

Manual corrections MUST be auditable.

---

## 10. External Ratings

FIDE, Lichess, and Chess.com ratings are external identity/profile data.

They MUST NOT be mixed with MicroChess exercise ratings.

External ratings may be used for:

* player profile
* initial-level estimation
* analytics/context

but do not directly overwrite MicroChess ratings.

---

## 11. Analytics

The rating system must provide data required for:

* current rating
* rating change
* rating history
* exercise comparisons
* time-period comparisons
* player progress analytics

Analytics should consume rating history rather than modify it.

---

## 12. Future Compatibility

The rating architecture should allow future improvements such as:

* better uncertainty modeling
* Glicko-compatible calculations
* exercise-specific calibration
* adaptive difficulty

without changing the public meaning of historical rating events.

Do not over-engineer these features before they are needed.

---

## 13. Definition of Done

Rating implementation is complete when:

* ratings are isolated per exercise
* server calculates all rating changes
* rating history is preserved
* duplicate/replayed attempts cannot create duplicate changes
* provisional state is supported
* admin corrections are auditable
* external chess ratings remain separate
* relevant rating tests pass
