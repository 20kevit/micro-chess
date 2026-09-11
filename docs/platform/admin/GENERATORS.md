# MicroChess Puzzle Generators

## 1. Purpose

Generators create candidate puzzles for exercises.

A generator is a **content production tool**, not a production publishing mechanism.

Generated content must pass the normal validation, review, approval, and publication lifecycle defined in `PUZZLE_MANAGEMENT.md`.

---

## 2. Generator Definition

Each generator should have:

* stable identifier
* target exercise
* supported configuration
* difficulty/rating target
* generation constraints
* validation rules
* version
* status
* creation/update metadata

Generator configuration must be explicit and reproducible.

---

## 3. Generator Registry

Generators should be registered through a central registry rather than discovered through scattered special cases.

The registry should allow the system to determine:

* available generators
* supported exercises
* configuration schema
* generator version
* validation requirements

Adding a generator must not require changing unrelated generator implementations.

---

## 4. Generation Jobs

A generation request creates a job with:

```text id="0lqg2f"
generator
exercise
configuration
requested quantity
requester
status
timestamps
result summary
```

Useful job states:

```text id="q6p4vs"
QUEUED
RUNNING
COMPLETED
FAILED
CANCELLED
```

Long-running generation must not block normal API requests.

---

## 5. Difficulty and Rating Targets

Admins may specify target difficulty/rating ranges.

A target is a **generation objective**, not a guaranteed result.

The generator should record:

* requested target
* actual generated characteristics
* validation results
* observed performance later, when available

Difficulty calibration is ultimately informed by real player data.

---

## 6. Candidate Content

Generated puzzles initially remain candidates.

They must not become player-visible merely because generation succeeded.

Typical flow:

```text id="1v7f2k"
Generate
→ Validate
→ Review
→ Approve
→ Publish
→ Active
```

---

## 7. Validation

Every generator must use the exercise's required validation rules.

Validation should detect, where applicable:

* invalid content
* illegal chess positions/moves
* missing required fields
* duplicate puzzles
* violated exercise constraints
* answer leakage
* unsupported difficulty/configuration

Invalid candidates must remain excluded from production.

---

## 8. Deduplication

Generators should avoid creating duplicate or materially equivalent puzzles.

Deduplication strategy must be exercise-specific where necessary.

The system should retain enough metadata to explain why a candidate was accepted or rejected.

---

## 9. Preview and Inspection

Admins should be able to inspect generated candidates before approval.

Preview must use the same essential content representation as production while ensuring unpublished answers or sensitive metadata are not exposed to unauthorized users.

---

## 10. Cancellation and Failure

Admins with `generators.cancel` may cancel eligible jobs.

Failed jobs must preserve:

* failure status
* relevant error information
* configuration
* generator version
* execution timestamps
* generated-result summary where available

A failed job must not partially publish content.

---

## 11. Versioning and Reproducibility

Generator version and configuration must be recorded with each generation job.

When practical, generation should be reproducible from:

```text id="p4x8cb"
generator version
+
configuration
+
controlled input/source
```

Changing generator logic must not silently rewrite previously generated content.

---

## 12. Admin Capabilities

Generator operations use:

```text id="8c2x1p"
generators.read
generators.create
generators.update
generators.run
generators.cancel
generators.delete
```

Every operation is authorized server-side.

---

## 13. Safety Rules

Generators MUST NOT:

* automatically publish content
* bypass validation
* bypass review/approval
* modify historical attempts
* expose production answers to players
* overwrite existing production content without an explicit versioning strategy

---

## 14. Audit

Record at minimum:

* generator configuration changes
* generation requests
* job cancellation
* job completion/failure
* generated content counts
* validation results
* publication decisions

---

## 15. Definition of Done

Generators are complete when:

* generators have a central registry
* jobs are tracked independently
* configuration and generator versions are recorded
* generated content remains non-production until approved
* validation and deduplication are enforced
* failed/cancelled jobs are safe
* generation is auditable
* meaningful tests cover authorization, lifecycle, failure, and reproducibility
