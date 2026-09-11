# Admin Analytics

## 1. Purpose

Admin Analytics provides trusted, read-only visibility into platform usage, training performance, content performance, and operational health.

It must consume authoritative platform data and must not modify training history, ratings, or gamification state.

---

## 2. Access

Admin analytics requires:

* authenticated active account
* `ADMIN` role
* appropriate analytics capability

Canonical capabilities:

```text
analytics.read_platform
analytics.read_exercise
analytics.read_puzzle
```

Authorization must be enforced server-side.

Analytics endpoints must not become an alternative path to private user data.

---

## 3. Platform Metrics

Provide aggregated metrics such as:

* total users
* new registrations
* active users
* active days
* training sessions
* attempts
* accuracy
* practice time
* exercise usage
* rating distribution
* XP/activity
* retention/activity trends
* support volume

Support standard ranges:

```text
7d
30d
90d
all
custom
```

Where meaningful, provide comparison with the previous equivalent period.

---

## 4. Exercise Analytics

For each exercise, provide:

* attempts
* unique players
* sessions
* accuracy
* completion/progression
* average response time
* rating distribution
* rating progression
* difficulty/performance relationship
* usage trend
* failure trend
* active/inactive status

This information should help administrators identify:

* exercises that are too easy or difficult
* exercises with poor engagement
* unusual performance patterns
* content requiring review

---

## 5. Puzzle Analytics

For individual puzzles or puzzle groups:

* attempts
* unique players
* accuracy
* response time
* repeated failures
* performance by rating/difficulty
* usage frequency
* recent performance trend

Puzzle analytics must never expose hidden answers to unauthorized clients.

---

## 6. Data Rules

Raw attempts, sessions, rating events, and gamification events remain the source of truth.

Derived analytics may be:

* calculated on demand
* cached
* materialized

But derived values must be reproducible from authoritative data.

Analytics must not silently rewrite historical records.

---

## 7. Privacy

Admin access does not mean unrestricted access to every field.

Do not expose:

* password hashes
* authentication tokens
* session secrets
* unnecessary private profile information
* unrelated sensitive data

Prefer aggregated results when individual-level data is unnecessary.

All sensitive administrative access should be auditable.

---

## 8. Performance

Start with database-backed queries and appropriate indexes.

Use aggregation, caching, or materialized summaries only where measurements justify them.

Do not introduce a separate analytics warehouse, event broker, or external analytics platform merely for anticipated scale.

Large queries must support pagination, bounded date ranges, or server-side aggregation.

---

## 9. Implementation Rules

* Analytics are read-only.
* Domain rules remain outside routes.
* Routes must remain thin.
* Authorization is server-side.
* Historical data is never mutated by analytics.
* Metrics must have explicit definitions.
* Time zones and date boundaries must be handled consistently.
* Empty datasets must return valid zero/empty results rather than errors.
* Important metrics require tests against known data.

---

## 10. Definition of Done

Admin Analytics is complete when:

* platform analytics are available
* exercise analytics are available
* puzzle analytics are available
* date ranges and comparisons work where supported
* authorization is enforced
* privacy boundaries are enforced
* analytics cannot mutate source data
* performance is acceptable for the expected dataset
* backend tests cover metric correctness and authorization
* frontend tests/typecheck/build pass
* existing exercise behavior remains intact
* implementation state is updated with evidence
