# Phase 08 — Analytics

## 1. Goal

Build reliable, privacy-aware analytics from validated platform history so players, coaches, parents, and admins can understand progress and platform usage.

---

## 2. Scope

Implement:

* player analytics
* exercise analytics
* puzzle analytics
* platform analytics
* time-range filtering
* period comparisons
* rating/progress trends
* training activity metrics
* analytics aggregation/caching where useful

Detailed rules are defined in:

```text id="q2k8sm"
docs/platform/training/ANALYTICS.md
```

---

## 3. Source of Truth

Analytics must be derived from authoritative records:

* attempts
* sessions
* rating events
* gamification events
* relationships
* content metadata

Analytics must never become the primary source of truth.

Derived data must be reproducible from authoritative history.

---

## 4. Time Ranges

Support:

```text id="7j3p9c"
7 days
30 days
90 days
All time
Custom range
```

Where meaningful, support comparison with a previous equivalent period.

All date filtering must be server-side and timezone-aware.

---

## 5. Player Analytics

Player analytics should expose actionable metrics such as:

* attempts
* accuracy
* practice time
* active days
* sessions
* response time
* exercise progress
* rating changes
* XP
* streaks
* mastery

The UI should emphasize trends and useful conclusions rather than displaying raw event data.

---

## 6. Exercise Analytics

Admins may inspect:

* total attempts
* unique players
* accuracy
* completion
* response time
* rating distribution
* rating changes
* difficulty/performance trends
* activity over time

Exercise analytics must distinguish meaningful activity from invalid/replayed submissions.

---

## 7. Puzzle Analytics

Where sufficient data exists, track:

* attempts
* unique players
* accuracy
* response time
* repeated failures
* performance by difficulty
* content usage

Puzzle analytics may later help identify content that is too easy, too difficult, ambiguous, or otherwise problematic.

---

## 8. Platform Analytics

Platform-level analytics may include:

* active users
* new registrations
* sessions
* attempts
* accuracy
* retention/activity
* exercise usage
* rating distribution
* support volume

Access requires the appropriate administrative capability.

---

## 9. Related-User Analytics

Coach and Parent analytics are restricted by:

```text id="e2j8vl"
capability
+
active relationship
+
object authorization
+
privacy policy
```

A relationship must never provide unrestricted platform analytics.

---

## 10. Performance

Start with database-backed queries and indexed aggregations.

Caching or materialized summaries may be introduced when justified by measured performance.

Do not introduce a separate analytics warehouse, event broker, or distributed analytics infrastructure prematurely.

---

## 11. Privacy

Analytics responses must expose only the minimum data necessary for the viewer's role and scope.

Child/student analytics must respect relationship and privacy policies.

Public analytics must never expose private user information.

---

## 12. Future Adaptive Training

Analytics must preserve enough reliable data to later support adaptive training, including:

* weak exercises
* repeated mistakes
* declining performance
* response-time patterns
* consistency
* mastery
* rating progression

Phase 08 does not require implementing adaptive recommendations.

---

## 13. Testing

Test:

* metric correctness
* date-range boundaries
* period comparison
* empty periods
* timezone behavior
* player privacy
* coach/parent scoping
* admin authorization
* invalid/replayed activity exclusion
* aggregation consistency

---

## 14. Definition of Done

Phase 08 is complete when:

* analytics are derived from authoritative history
* required player/exercise/puzzle/platform metrics work
* time ranges and comparisons are reliable
* related-user access is properly scoped
* privacy rules are enforced
* analytics queries perform acceptably
* derived data can be recalculated
* meaningful analytics tests pass
