# Phase 07 — Content & Generators

## 1. Goal

Build a controlled content-management system for creating, validating, reviewing, generating, publishing, and retiring exercise content.

---

## 2. Scope

Implement:

* puzzle/content records
* content lifecycle
* validation
* review and approval
* publication/retirement
* generator registry
* generation jobs
* generator configuration/versioning
* deduplication
* candidate inspection
* content audit history

Detailed rules are defined in:

```text
docs/platform/admin/PUZZLE_MANAGEMENT.md
docs/platform/admin/GENERATORS.md
```

---

## 3. Content Lifecycle

Production content must follow the defined lifecycle:

```text
Draft
→ Created/Generated
→ Validated
→ Reviewed
→ Approved
→ Published
→ Active
→ Retired
```

Lifecycle transitions are server-enforced.

---

## 4. Validation

Validation must be exercise-aware.

Depending on the exercise, it may verify:

* structural validity
* legal chess state/moves
* required answers
* exercise-specific invariants
* metadata
* duplicate content
* answer-leakage risks
* difficulty constraints

Invalid content cannot become production-active.

---

## 5. Generators

Generators create candidates only.

A generation job must preserve:

* generator identity
* generator version
* configuration
* target exercise
* requested quantity
* execution status
* validation results

Generation success does not imply production readiness.

---

## 6. Difficulty

Admins may define target rating/difficulty parameters.

These are generation targets, not guarantees.

The platform should preserve both:

```text
declared/target difficulty
observed difficulty
```

Observed difficulty is derived from real player performance.

---

## 7. Deduplication

Generated content must be checked for duplicate or materially equivalent content where the exercise requires it.

The deduplication strategy may differ between exercises.

Rejected candidates should remain traceable for generator evaluation and debugging.

---

## 8. Publishing

Only content that has passed all required validation and approval gates may become active.

Publishing must not:

* modify historical attempts
* rewrite previous answers
* bypass review
* expose unpublished content to players

Retirement is preferred over deletion for production content.

---

## 9. Versioning

Generator versions and significant production-content changes must be traceable.

Historical attempts must continue referencing the content/version that was actually presented to the player.

---

## 10. Security and Authorization

Content operations require the canonical capabilities:

```text
puzzles.*
generators.*
```

The frontend must never be the security boundary.

Answers and unpublished content must remain inaccessible to normal players.

---

## 11. Testing

Test:

* lifecycle transitions
* validation failures
* approval/publication rules
* retirement
* generator jobs
* cancellation/failure
* deduplication
* authorization
* answer protection
* historical-content integrity

---

## 12. Definition of Done

Phase 07 is complete when:

* content has a controlled lifecycle
* validation is enforced
* approval precedes production use
* generators produce traceable candidates
* generator versions/configuration are preserved
* duplicate content is controlled
* production history remains stable
* answers remain protected
* meaningful content/generator tests pass
