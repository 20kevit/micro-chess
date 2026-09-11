# MicroChess Gamification

## 1. Purpose

Gamification should encourage meaningful chess training without replacing learning quality.

Core elements:

* XP
* levels
* streaks
* daily/weekly goals
* achievements
* badges
* personal records
* exercise mastery
* leaderboards

---

## 2. Server Authority

All persistent gamification state is server-authoritative.

The client MUST NOT determine or submit authoritative:

* XP
* level
* streak
* achievement completion
* leaderboard score
* rewards

These are derived from validated training events.

---

## 3. XP

XP may be awarded for meaningful activities such as:

* completing valid attempts
* completing sessions
* achieving training goals
* reaching milestones

XP rules should be configurable rather than hard-coded throughout the application.

Repeated low-value actions MUST NOT allow trivial XP farming.

---

## 4. Levels

Levels are derived from accumulated XP according to a configurable progression rule.

The system should store enough data to reconstruct:

```text
total XP
current level
XP events
```

Level changes should be deterministic and server-calculated.

---

## 5. Streaks and Goals

The system should support:

* daily streaks
* daily goals
* weekly goals
* active-day tracking

A streak must be calculated from actual qualifying training activity.

The exact definition of a qualifying activity must be explicit and configurable.

---

## 6. Achievements

Achievements are rule-based milestones.

Examples:

* first completed exercise
* first perfect session
* exercise milestones
* rating milestones
* streak milestones
* personal records

Achievement definitions should be data/configuration driven where practical.

Achievements must be awarded idempotently.

---

## 7. Exercise Mastery

Each exercise may have a mastery state derived from training data.

Possible states include:

```text
Not Started
Learning
Practicing
Proficient
Mastered
```

The exact thresholds should remain configurable.

Mastery is separate from rating.

---

## 8. Leaderboards

Leaderboards must have explicit scope and eligibility.

Possible scopes:

* exercise
* time period
* global
* friends/groups in the future

Leaderboard calculations must use server-validated data.

Do not expose private player information beyond the configured public leaderboard fields.

---

## 9. Anti-Abuse

Gamification must resist:

* duplicate submissions
* replayed attempts
* automated farming
* impossible session activity
* manipulated client timestamps
* unauthorized score/XP changes

Gamification events should reference their source training event where appropriate.

Authorization and business rules must be enforced server-side; UI restrictions are not security controls.

---

## 10. History

Important gamification changes should be traceable through immutable events.

At minimum, the system should be able to determine:

```text
event
source
amount/change
timestamp
player
```

This supports debugging, analytics, support, and administrative correction.

---

## 11. Guest Policy

Guests do not have persistent gamification state.

Temporary session feedback may exist, but it is not persistent XP, achievements, streaks, or levels.

When Guest data is migrated, only explicitly eligible training facts may contribute to the authenticated account's gamification.

---

## 12. Definition of Done

Gamification is complete when:

* rewards are server-authoritative
* XP cannot be trivially farmed
* achievements are idempotent
* streaks use real training activity
* mastery is separate from rating
* leaderboards have explicit scope
* important changes are traceable
* Guest gamification remains temporary
* relevant rules are configurable rather than scattered across UI code
