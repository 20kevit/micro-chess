# Phase 01 — Foundation

## 1. Goal

Prepare the existing MicroChess application for platform-level development without breaking existing exercises or architecture.

This phase establishes the technical foundation required by later phases.

---

## 2. Scope

The implementation should establish or verify:

* stable backend/frontend module boundaries
* database migration strategy
* configuration/environment handling
* API versioning foundation
* authentication/session infrastructure foundation
* centralized authorization capability registry
* consistent error handling
* server-side validation patterns
* audit/event infrastructure foundation
* testing conventions
* basic observability/logging

Existing exercise functionality must continue working.

---

## 3. Data Foundation

The database must support future platform domains without prematurely implementing every feature.

Foundation work may include:

* migration infrastructure
* shared timestamps/identifiers
* account identity foundation
* session/guest foundation
* audit/event primitives where justified

Do not create speculative tables merely because they may be useful later.

---

## 4. Security Foundation

Implement the minimum infrastructure required for later secure development:

* password hashing
* authenticated sessions
* guest sessions
* centralized capability definitions
* server-side authorization
* secure configuration/secrets handling
* request validation
* rate-limit integration points

Detailed security rules remain defined in:

```text
docs/platform/SECURITY.md
```

---

## 5. API Foundation

All new platform APIs use:

```text
/api/v1
```

API routes must remain thin.

Business rules belong in the appropriate application/domain layer.

Responses and errors should follow the conventions in:

```text
docs/platform/API_CONTRACTS.md
```

---

## 6. Frontend Foundation

Establish reusable infrastructure for:

* authentication state
* API communication
* authorization-aware UI
* routing
* loading/error states
* responsive layout
* Persian RTL
* board LTR behavior

Do not duplicate authorization logic as a security mechanism in the frontend.

---

## 7. Compatibility

Foundation changes MUST preserve:

* existing exercise behavior
* existing puzzle behavior
* existing chess logic
* current responsive exercise UX
* existing tests

Existing code is evidence of current behavior and must be inspected before modification.

---

## 8. Testing

Tests must cover the foundation itself and regression protection for existing exercises.

At minimum:

* authentication/session basics
* authorization decisions
* migration behavior
* API error handling
* database migrations
* existing exercise regression tests

Tests must verify behavior, not merely increase coverage numbers.

---

## 9. Definition of Done

Phase 01 is complete when:

* platform foundation is usable by later phases
* existing exercises remain functional
* security/authorization infrastructure is centralized
* API conventions are established
* database migrations are reliable
* meaningful tests pass
* no speculative architecture has been introduced
* implementation documentation reflects the actual repository state
