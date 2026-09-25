# MicroChess Puzzle Management

## 1. Purpose

Puzzle management controls the creation, validation, review, publication, activation, and retirement of training content.

Puzzle management must preserve content integrity and historical training data.

---

## 2. Puzzle Lifecycle

Every managed puzzle follows an explicit lifecycle:

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

Transitions are server-enforced. An admin must not be able to bypass required lifecycle gates through the UI or API.

---

## 3. Puzzle Sources

A puzzle may originate from:

* manual creation
* an existing repository/content source
* a generator
* an imported dataset

The source must be recorded when relevant.

Generated or imported content is never automatically considered production-ready.

---

## 4. Validation

Validation verifies technical correctness and exercise-specific requirements.

Depending on the exercise, validation may check:

* valid puzzle structure
* valid chess position
* legal moves/answers
* required metadata
* exercise-specific invariants
* duplicate content
* supported difficulty/rating constraints

A failed validation must prevent progression to the next required lifecycle stage.

---

## 5. Review and Approval

Validation does not automatically equal approval.

Review confirms that the puzzle is suitable for actual learners, including:

* correctness
* clarity
* appropriate difficulty
* exercise compatibility
* absence of answer leakage
* appropriate metadata

Approval must be an explicit administrative action.

---

## 6. Publishing

Publishing makes approved content eligible for production use.

Publishing must verify that all required gates have passed.

A published puzzle must have a stable identity so historical attempts can continue referencing the same content.

---

## 7. Active and Retired Content

Only `Active` puzzles may normally be delivered to players.

Retiring a puzzle:

* prevents new delivery
* preserves historical attempts
* preserves analytics
* preserves rating history
* keeps audit/history references valid

Retirement is preferred over hard deletion.

---

## 8. Puzzle Editing

Once a puzzle has participated in production training, changes that alter its meaning should not silently rewrite historical interpretation.

For significant changes, prefer:

```text
create new version/content record
```

rather than mutating the historical production artifact.

---

## 9. Admin Capabilities

Operations follow the canonical capabilities:

```text
puzzles.read
puzzles.create
puzzles.update
puzzles.validate
puzzles.review
puzzles.approve
puzzles.publish
puzzles.retire
```

Authorization is checked server-side for every operation.

---

## 10. Difficulty

A puzzle may have:

* declared/target difficulty
* observed difficulty derived from real performance

Declared difficulty is configuration.

Observed difficulty is analytical data and should not be manually overwritten without an explicit administrative correction process.

---

## 11. Answer Security

Puzzle answers must never be exposed through:

* catalog endpoints
* normal player APIs
* frontend source data
* analytics responses
* browser-visible metadata

The server remains authoritative for validation.

---

## 12. Bulk Operations

Bulk validation, review, publishing, or retirement may be supported.

Bulk operations must:

* apply the same lifecycle gates as individual operations
* report partial failures clearly
* remain auditable
* never bypass validation

---

## 13. Audit

Audit at minimum:

* creation
* source/import/generation
* validation results
* review
* approval
* publication
* retirement
* significant edits

Audit data should identify actor, action, target, timestamp, and relevant result/context.

---

## 14. Phase 13 operator controls

The Admin library is a server-filtered table with exercise, lifecycle,
difficulty, source, search, rating, sorting, pagination, and bulk-action
controls. Rows show a server-derived attempt count; the frontend does
not infer usage from player-visible data.

The puzzle editor is contract-driven. It renders the registered
exercise's answer fields and position fields, supports the board editor
where the contract requires a board, and keeps FEN-derived answers
read-only. `source_reference`, hint data, and position metadata are
persisted through the Admin API and included in audit history when
changed.

A draft may be hard-deleted only when all of the following are true:

```text
source = manual
status = draft
not published and not archived
no generator run
no lifecycle history
no validation/review rows
no attempts
```

Every other puzzle is retained and handled through the normal lifecycle.
The delete endpoint records an audit event and never exposes the answer
to player-facing routes.

---

## 15. Definition of Done

Puzzle management is complete when:

* lifecycle transitions are server-enforced
* validation precedes approval/publication
* only approved content can become production-active
* retired content cannot be newly delivered
* historical references remain valid
* answers remain protected
* significant changes preserve historical meaning
* all privileged operations are auditable
* authorization and lifecycle tests cover both allowed and denied transitions
