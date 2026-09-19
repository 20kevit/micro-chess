"""Assessment sessions (P6).

An assessment is a bounded evaluation session owned by exactly one
student. It is deliberately NOT a practice mode with a new name:

* practice attempts carry no assessment context (``attempt.assessment_id``
  stays NULL for them);
* assessment attempts are ordinary attempts (same validators, same
  scoring, same rating/XP eligibility by mode) that additionally point
  at the assessment session they belong to, so all attempts of one
  evaluation are queryable via ``attempt.assessment_id``;
* the session itself has an explicit lifecycle
  (``active -> completed | cancelled``) that never touches history:
  completing/cancelling never edits attempts, ratings, XP, evidence,
  or skill state.

Separation guarantees (no new thresholds or product rules here):

* direct coach work and system suggestions are never mixed: this module
  only records sessions created by a coach (under an ACTIVE coach
  relationship) or by the student themselves. System recommendations
  live in ``adaptive_recommendations`` and are never written here.
* a future recommender can defer to direct work by checking for an
  active direct assignment/assessment first; the ``source`` column on
  assignments and the creator/assignment links here are the stable
  hooks for that override. Recommendation itself stays unimplemented.

No router exists on purpose: this phase models the session and the
attempt link only. Creation/closure happen through the service layer
(coach tooling / future flows call it directly).
"""

from app.modules.assessments.models import (
    ASSESSMENT_ACTIVE,
    ASSESSMENT_CANCELLED,
    ASSESSMENT_COMPLETED,
    ASSESSMENT_STATUSES,
    Assessment,
)
from app.modules.assessments.service import (
    cancel_assessment,
    complete_assessment,
    create_assessment,
    get_assessment,
    list_created_by,
    list_for_student,
    resolve_for_attempt,
)

__all__ = [
    "ASSESSMENT_ACTIVE",
    "ASSESSMENT_CANCELLED",
    "ASSESSMENT_COMPLETED",
    "ASSESSMENT_STATUSES",
    "Assessment",
    "cancel_assessment",
    "complete_assessment",
    "create_assessment",
    "get_assessment",
    "list_created_by",
    "list_for_student",
    "resolve_for_attempt",
]
