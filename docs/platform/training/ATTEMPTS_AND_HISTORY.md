# MicroChess Attempts & History

## 1. Purpose

Every meaningful training interaction should produce reliable historical data.

History is the source for:

* player progress
* rating history
* analytics
* achievements
* recommendations
* admin reporting

Historical records must represent what actually happened, not what the client claims happened.

---

## 2. Attempt

An attempt represents one submitted answer/action within a training session.

An attempt should record at least:

* player or guest identity
* session
* exercise
* puzzle/content identifier
* mode
* correctness/result
* score
* response time when applicable
* timestamp
* relevant difficulty/content metadata
* rating before/change/after when rated
* XP change when applicable

The exact schema is defined by `DATA_MODEL.md`.

---

## 3. Session

A training session groups related attempts.

A session should track:

* owner
* exercise
* mode
* start time
* end time
* status
* attempt count
* aggregate result where applicable

The server owns session timing and lifecycle.

---

## 4. Immutable History

Completed attempts and rating events are historical facts.

They MUST NOT be silently edited to change what happened.

If an administrative correction is necessary:

* preserve the original record
* record the correction
* record who performed it
* record when it happened
* preserve an audit trail

---

## 5. Duplicate and Replay Protection

Submitting the same logical attempt multiple times MUST NOT create multiple historical events.

The server must use appropriate:

* session validation
* attempt/session state
* idempotency protection
* unique constraints where appropriate

Replay protection is especially important for:

* rating changes
* XP
* achievements
* timed sessions

---

## 6. Guest History

Guest attempts may be stored as temporary training history.

They belong exclusively to the Guest identity that created them.

Guest history:

* is not another user's history
* does not automatically create persistent ratings
* may be migrated into an authenticated account
* must not become accessible to other users

Guest migration must preserve ownership and prevent duplicate migration.

---

## 7. Player History

Authenticated Players may access their own permitted history.

History views may provide:

* recent attempts
* session summaries
* exercise performance
* correctness
* score
* response time
* rating changes
* XP
* progress over time

Detailed analytics should use the underlying historical records rather than duplicating facts unnecessarily.

---

## 8. Related-User History

Coach/Parent access to another user's history requires:

```text
capability
+
valid relationship
+
object-level authorization
+
applicable privacy rules
```

Having a relationship alone is not sufficient.

---

## 9. Data Integrity

The server MUST determine:

* correctness
* score
* timing
* rating changes
* XP
* achievement eligibility

The client may submit an answer and necessary interaction data, but cannot submit authoritative results.

---

## 10. Retention and Deletion

Historical training data should remain available long enough to support:

* progress tracking
* rating history
* analytics
* auditing

Deletion rules must respect:

* privacy requirements
* account deletion policy
* audit requirements
* dependencies between historical records

Deleting a Player must not accidentally corrupt aggregate or audit data.

---

## 11. Analytics Boundary

History stores raw facts.

Analytics derives metrics such as:

* accuracy
* attempts
* practice time
* active days
* streaks
* rating progression
* exercise performance

Do not store every derived metric as an independent source of truth.

---

## 12. Definition of Done

The history system is complete when:

* every relevant attempt is reliably recorded
* server-authoritative results are stored
* sessions are traceable
* duplicate/replayed submissions are protected
* rating/XP changes can be traced to their source
* Guest ownership is enforced
* historical facts are not silently rewritten
* Coach/Parent access is relationship- and object-authorized
* analytics can reconstruct required player progress
