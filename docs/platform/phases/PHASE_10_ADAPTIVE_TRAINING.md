# Phase 10 — Adaptive Training Foundation

## 1. Goal

Prepare MicroChess for personalized training without prematurely introducing complex machine-learning infrastructure.

Adaptive training should use reliable learner and content data to recommend useful next activities. Research on adaptive learning emphasizes learner-state modeling, content characteristics, and recommendation strategy as core components.

---

## 2. Scope

Implement the foundation for:

* learner skill signals
* exercise strengths/weaknesses
* content difficulty signals
* recommendation candidates
* recommendation reasons
* adaptive exercise selection
* future spacing/remediation
* recommendation history

Do **not** require an ML model in this phase.

---

## 3. Learner Signals

Recommendations may use:

* exercise rating
* rating trend
* accuracy
* recent failures
* repeated mistakes
* response time
* practice frequency
* mastery
* consistency
* recent activity
* difficulty progression

The data must come from authoritative training history and analytics.

---

## 4. Content Signals

Content selection may consider:

* exercise
* difficulty
* observed performance
* content usage
* failure rate
* response time
* freshness/retirement state
* prerequisite relationships where applicable

Difficulty should be treated as an evolving signal rather than a permanently fixed truth.

---

## 5. Recommendation Strategy

The initial recommendation engine should be deterministic and explainable.

Possible strategies include:

```text id="f7k2mz"
weak skill
→ targeted practice

stable skill
→ appropriate difficulty progression

recent repeated failures
→ remediation/easier content

strong performance
→ controlled difficulty increase
```

Adaptive difficulty is a reasonable priority for future personalization, but recommendations should remain measurable and reversible rather than blindly optimizing engagement. Evidence on adaptive training suggests difficulty adaptation can be useful, while results vary by intervention and learner.

---

## 6. Recommendation Reasons

Every recommendation should have a machine-readable reason, for example:

```text id="8j5nq4"
WEAK_EXERCISE
RECENT_FAILURES
READY_FOR_HARDER
LOW_RECENT_ACTIVITY
MASTERY_REVIEW
```

The UI may convert these into child-friendly Persian explanations.

---

## 7. Safety and Quality

The recommendation system must avoid:

* repeatedly serving the same content
* exploiting gamification
* excessive difficulty jumps
* ignoring struggling learners
* recommending retired/unavailable content
* bypassing exercise eligibility
* treating predictions as facts

Recommendations must never override normal exercise authorization or content lifecycle rules.

---

## 8. Feedback Loop

Record recommendation outcomes where useful:

* recommendation shown
* accepted/started
* completed
* skipped
* result
* subsequent performance

This allows future evaluation of recommendation quality without modifying historical training facts.

---

## 9. Future Extensions

The architecture should allow later introduction of:

* adaptive spacing
* mastery-based sequencing
* more advanced learner models
* item-difficulty estimation
* contextual recommendation
* ML-based ranking

These should be introduced only when sufficient data and a measurable benefit justify the complexity.

---

## 10. Testing

Test:

* deterministic recommendations
* eligibility filtering
* difficulty boundaries
* repeated-content avoidance
* unavailable-content exclusion
* recommendation reasons
* privacy/authorization
* recommendation outcome recording

---

## 11. Definition of Done

Phase 10 is complete when:

* learner and content signals are available
* recommendations are explainable
* recommendations respect exercise/content rules
* adaptive selection is deterministic and testable
* recommendation outcomes are recorded
* no ML infrastructure is required
* the architecture can evolve toward more advanced personalization
