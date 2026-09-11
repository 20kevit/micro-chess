# MicroChess Analytics

## 1. Purpose

Analytics turns validated training history into useful progress information.

Analytics is read-only and MUST NOT become a source of truth.

Raw training history, attempts, rating events, and gamification events remain authoritative.

---

## 2. Core Metrics

Player analytics should support:

* attempts
* accuracy
* practice time
* active days
* sessions
* response time
* exercise completion/progress
* current rating
* rating change
* XP
* streak
* exercise mastery

Metrics must be calculated consistently from stored historical data.

---

## 3. Time Ranges

Player and admin analytics should support:

```text
7 days
30 days
90 days
all time
custom range
```

Where useful, users should be able to compare two periods.

Examples:

```text
last 7 days vs previous 7 days
this month vs previous month
```

---

## 4. Player Analytics

Players can access analytics for their own data.

The dashboard should prioritize actionable information:

```text
What improved?
What needs practice?
How consistently am I training?
Which exercises are strongest/weakest?
```

Do not overwhelm players with raw statistics.

---

## 5. Exercise Analytics

Exercise-level analytics should support:

* total attempts
* unique players
* accuracy
* completion
* average response time
* rating distribution/change
* difficulty/performance trends
* active usage

These metrics help evaluate exercise quality and difficulty.

---

## 6. Puzzle Analytics

Where puzzle-level tracking exists, analytics may include:

* attempts
* accuracy
* response time
* failure rate
* repeated failures
* performance by difficulty/content metadata

Puzzle analytics should help identify problematic or overly easy content.

---

## 7. Platform Analytics

Admins may access aggregated platform metrics such as:

* active users
* new users
* training sessions
* attempts
* accuracy
* retention/activity
* exercise usage
* rating distribution
* support volume

Platform analytics must not expose private user data unnecessarily.

---

## 8. Coach and Parent Analytics

Coach/Parent analytics are limited to users they are authorized to access.

Authorization requires:

```text
capability
+
valid relationship
+
object-level access
+
privacy rules
```

A relationship alone does not grant unrestricted analytics access.

---

## 9. Derived Data

Derived analytics may be cached or materialized for performance.

However:

```text
raw history
    >
derived analytics
```

If derived data conflicts with authoritative history, it must be recalculated.

Analytics jobs must therefore be reproducible.

---

## 10. Data Quality

Analytics must handle:

* missing optional data
* deleted users
* migrated Guest data
* corrected administrative records
* duplicate/replayed attempts
* incomplete sessions

Invalid or unauthorized events must not enter analytics.

---

## 11. Performance

Analytics queries must not unnecessarily scan the entire history table for every request.

Use appropriate:

* indexes
* aggregation queries
* cached/materialized summaries
* periodic recalculation

Do not introduce a separate analytics infrastructure unless actual scale requires it.

---

## 12. Privacy

Analytics responses must respect the same authorization and privacy rules as the underlying data.

Never expose another player's:

* private profile data
* detailed history
* private analytics

without explicit authorization.

---

## 13. Future Adaptive Training

Analytics must retain enough structured data to later support recommendations based on:

* weak exercises
* declining performance
* repeated mistakes
* response time
* training consistency
* mastery
* rating progression

Recommendation logic is a future layer and is not part of the initial analytics implementation.

---

## 14. Definition of Done

Analytics is complete when:

* core metrics are reproducible from authoritative data
* time-range filtering works
* period comparison works where applicable
* Player/Coach/Parent/Admin scopes are enforced
* exercise and puzzle analytics are available where required
* derived data can be recalculated
* analytics cannot modify training facts
* queries remain performant at expected platform scale
