# Architecture Decision Records

## 1. Purpose

This directory contains important architectural decisions that should remain explicit and traceable.

An ADR records a decision that materially affects the platform and should not be silently reversed by a future implementation agent.

---

## 2. When to Create an ADR

Create an ADR when a decision affects:

* architecture
* data ownership
* security boundaries
* authorization
* persistence strategy
* API contracts
* major UX/platform behavior
* compatibility with existing exercises
* future extensibility

Do not create an ADR for ordinary implementation details.

---

## 3. ADR Structure

Each ADR should contain:

```text id="5w8h7r"
# ADR: <Title>

## Status
PROPOSED | ACCEPTED | SUPERSEDED | REJECTED

## Context
What problem or decision required consideration?

## Decision
What was decided?

## Consequences
What does this enable, restrict, or require?

## Alternatives
What important alternatives were considered?

## Implementation Notes
Only concrete constraints required for implementation.
```

Keep ADRs concise.

---

## 4. Status Rules

### PROPOSED

Under consideration and not authoritative.

### ACCEPTED

Current authoritative decision.

### SUPERSEDED

Replaced by a newer accepted ADR.

The newer ADR must be referenced.

### REJECTED

Considered but explicitly not selected.

---

## 5. Authority

Accepted ADRs are part of the platform specification.

If an implementation conflicts with an accepted ADR, the agent must:

1. identify the conflict
2. avoid silently overriding the decision
3. check whether a newer ADR supersedes it
4. stop only if the conflict cannot be resolved safely

A repository implementation that differs from an ADR is evidence of current state, not automatic justification for changing the ADR.

---

## 6. Decision Changes

Do not edit an accepted ADR to silently change its meaning.

When a decision genuinely changes:

1. create a new ADR
2. mark the old ADR `SUPERSEDED`
3. reference the new ADR
4. update affected platform documents

This preserves architectural history.

---

## 7. Agent Rules

Implementation agents must:

* read relevant ADRs before changing architecture
* treat `ACCEPTED` ADRs as authoritative
* never invent an ADR to justify an already-made implementation
* avoid creating unnecessary ADRs
* update affected documentation when a decision changes

The goal is a small, trustworthy decision history—not a documentation burden.
