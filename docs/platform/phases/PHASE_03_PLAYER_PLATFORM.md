# Phase 03 — Player Platform

## 1. Goal

Build the authenticated player experience around the existing exercises while preserving the current exercise architecture.

---

## 2. Scope

Implement:

* player dashboard
* exercise discovery
* exercise catalog/status
* exercise detail/start flow
* player progress
* attempt/session history
* exercise-specific ratings
* basic profile experience
* player-level analytics
* training session infrastructure

The detailed domain rules are defined in the corresponding platform documents.

---

## 3. Dashboard

The player dashboard should provide useful, actionable information such as:

* current training activity
* recently practiced exercises
* exercise progress
* ratings
* streak
* XP/progress
* achievements where available
* recommended next activity when infrastructure supports it

The dashboard must not become a raw analytics dump.

---

## 4. Exercise Integration

Existing exercises remain the authoritative implementation of exercise-specific gameplay.

The platform layer should provide common infrastructure for:

```text id="t5p0ah"
catalog
→ start session
→ deliver content
→ submit attempt
→ calculate result
→ persist history
→ update rating
→ update gamification
```

Exercise-specific validation remains inside the exercise/domain implementation.

---

## 5. History

Every meaningful player training interaction should produce reliable history according to:

```text id="v1a6w9"
docs/platform/training/ATTEMPTS_AND_HISTORY.md
```

History must remain usable even if an exercise is later disabled.

---

## 6. Ratings

Each exercise has an independent player rating.

Rating updates must follow:

```text id="i6q8cv"
docs/platform/training/RATINGS.md
```

The player must be able to view current ratings and appropriate rating history.

---

## 7. Progress and Analytics

Player-facing progress should expose meaningful information such as:

* accuracy
* attempts
* practice time
* active days
* exercise progress
* rating changes
* response time
* streak
* XP
* mastery

Time ranges should support the platform analytics conventions.

---

## 8. Navigation

Player mobile navigation should follow the canonical UX specification:

```text id="e0qg9j"
Home
Exercises
Progress
Profile
```

Active exercise screens should minimize navigation and prioritize the training task.

---

## 9. Privacy

Players may access their own private data according to their capabilities.

Related-user access, public profile data, leaderboards, and privacy controls must follow `SECURITY.md`.

---

## 10. Compatibility

The implementation MUST preserve:

* current exercise gameplay
* existing exercise-specific rules
* current scoring behavior
* responsive exercise viewport behavior
* existing puzzle datasets
* existing regression tests

Do not rewrite working exercises to fit the platform unless required by an identified architectural boundary.

---

## 11. Testing

Test:

* dashboard data
* exercise discovery/start
* session lifecycle
* attempt persistence
* rating integration
* history
* player authorization
* privacy
* responsive player flows
* existing exercise regression

---

## 12. Definition of Done

Phase 03 is complete when:

* authenticated players have a coherent platform experience
* exercises are integrated without rewriting their domain logic
* attempts and sessions are persisted reliably
* exercise ratings work independently
* player progress is visible
* history and analytics are useful
* privacy and authorization are enforced
* existing exercises remain functional
