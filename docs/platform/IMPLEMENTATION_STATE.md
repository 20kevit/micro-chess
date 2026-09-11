# MicroChess Platform Implementation State

## 1. Purpose

This document records the actual implementation state of the platform.

It must describe **repository reality**, not planned functionality.

The implementation agent MUST inspect the repository before updating this file.

---

## 2. Status Vocabulary

Use only:

```text
NOT_STARTED
IN_PROGRESS
PARTIAL
IMPLEMENTED
VERIFIED
BLOCKED
```

`IMPLEMENTED` means code exists.

`VERIFIED` means the implementation has also been meaningfully tested.

---

## 3. Platform Areas

Track at minimum:

| Area                         | Status |
| ---------------------------- | ------ |
| Foundation                   | TBD    |
| Accounts & Identity          | TBD    |
| Player Platform              | TBD    |
| Ratings                      | TBD    |
| Gamification                 | TBD    |
| Administration               | TBD    |
| Content & Generators         | TBD    |
| Analytics                    | TBD    |
| Relationships                | TBD    |
| Adaptive Training Foundation | TBD    |
| Support & Notifications      | TBD    |

`TBD` values must be replaced only after repository inspection.

---

## 4. Exercise Compatibility

Existing exercises must be tracked separately from platform work.

The implementation agent must verify that platform changes preserve:

* existing exercise behavior
* exercise-specific validation
* scoring
* puzzle delivery
* responsive exercise UX
* existing tests

A platform phase must not be marked `VERIFIED` if it introduces unexplained exercise regressions.

---

## 5. Evidence

Every non-trivial status should have concise evidence, such as:

* relevant source files
* implemented API/module
* migration
* test result
* frontend build/typecheck result

Do not claim completion from documentation alone.

---

## 6. Known Gaps

Record known gaps explicitly:

```text
Area
Current limitation
Impact
Required follow-up
```

Do not hide incomplete work by marking a parent phase complete.

---

## 7. Testing State

Track at least:

* backend tests
* frontend tests
* typecheck
* build
* migration verification
* important integration/e2e checks

A green test suite does not automatically prove a feature is complete.

---

## 8. Update Rules

Update this document when:

* a platform phase changes state
* a major implementation milestone is completed
* a blocker is discovered
* verification changes
* an important architectural gap is resolved

Keep entries concise.

Do not turn this file into a development diary.

---

## 9. Agent Rule

Before implementing any phase, the agent MUST:

1. inspect the repository
2. compare actual state with this document
3. treat code as current-state evidence
4. implement only missing work
5. run meaningful verification
6. update this document with evidence

The agent must never assume that a phase is incomplete merely because its documentation exists, or complete merely because its documentation describes the desired state.
