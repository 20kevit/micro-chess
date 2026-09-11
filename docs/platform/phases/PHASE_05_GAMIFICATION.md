# Phase 05 — Gamification

## 1. Goal

Introduce a meaningful gamification system that encourages consistent chess-skill practice without rewarding low-value activity or undermining learning.

---

## 2. Scope

Implement:

* XP
* levels
* streaks
* daily/weekly goals
* achievements
* badges
* personal records
* exercise mastery
* leaderboards
* gamification history/events

Detailed rules are defined in:

```text
docs/platform/training/GAMIFICATION.md
```

---

## 3. XP and Levels

XP is awarded for meaningful, validated training activity.

The server determines:

* whether an activity qualifies
* XP amount
* applicable limits
* resulting total

Levels are derived from accumulated XP.

Clients must never submit XP or level values.

---

## 4. Streaks and Goals

Streaks are based on qualifying activity, not merely opening the application.

Daily/weekly goals should be configurable and should avoid encouraging excessive or unhealthy repetition.

Missing a goal must not corrupt historical training data.

---

## 5. Achievements and Badges

Achievements should be:

* rule-based
* deterministic
* idempotent
* server-authoritative

The same achievement must not be granted repeatedly unless explicitly designed as repeatable.

Achievement rules should be configurable without embedding large amounts of logic in UI components.

---

## 6. Exercise Mastery

Mastery is independent from rating.

A suggested progression is:

```text
Not Started
→ Learning
→ Practicing
→ Proficient
→ Mastered
```

Mastery should consider meaningful performance and consistency rather than a single successful attempt.

---

## 7. Leaderboards

Leaderboards must have explicit:

* scope
* ranking metric
* time period
* eligibility rules
* privacy behavior

Possible scopes include exercise, platform, weekly, monthly, or all-time.

Users who should not appear publicly must be excluded according to privacy rules.

---

## 8. Anti-Abuse

Gamification must resist:

* duplicate submissions
* replayed attempts
* fabricated timestamps
* client-controlled scores
* repeated low-value actions
* unauthorized reward generation

All meaningful gamification changes should have an auditable event trail.

---

## 9. Guest Users

Guest activity may support temporary XP/progress where useful.

Guest gamification must not create persistent rewards until the guest has an account or explicitly defined migration behavior applies.

---

## 10. Testing

Test:

* XP calculation
* level progression
* streak behavior
* goal completion
* achievement idempotency
* mastery transitions
* leaderboard eligibility
* privacy
* duplicate/replay protection
* guest behavior

---

## 11. Definition of Done

Phase 05 is complete when:

* gamification is server-authoritative
* meaningful activity produces predictable rewards
* XP and levels are consistent
* achievements are idempotent
* mastery remains separate from rating
* leaderboards respect scope and privacy
* anti-abuse protections exist
* gamification history is auditable
* meaningful tests pass
