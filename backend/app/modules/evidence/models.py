"""Evidence persistence model (P2).

``Evidence`` is append-oriented history: one row per classified
observation from an attempt. Rows are never updated or deleted by
application flows — a later level/mastery/recommendation change must
never rewrite what the evidence meant when observed. Historical
context (mode, result, counts, snapshots) is copied into
``context_json`` so old rows stay interpretable even if the attempt's
surrounding metadata conventions change.

Idempotency: ``(attempt_id, evidence_key)`` is unique. Reprocessing
the same attempt returns the stored rows instead of inserting
duplicates (see ``service.generate_for_attempt``).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint("attempt_id", "evidence_key", name="uq_evidence_attempt_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Source attempt (Attempt -> Evidence traceability). Evidence rows
    # are written in the same transaction as their attempt: a rolled
    # back attempt can never leave orphan evidence behind.
    attempt_id: Mapped[int] = mapped_column(Integer, ForeignKey("attempts.id"), index=True)
    # Owner mirror (exactly one set, like Attempt): lets repeat detection
    # run one indexed query without joining attempts every submission.
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    guest_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("guest_sessions.id"), nullable=True, index=True
    )
    exercise_slug: Mapped[str] = mapped_column(String(100), index=True)
    puzzle_id: Mapped[int] = mapped_column(Integer, ForeignKey("puzzles.id"), index=True)
    # Event origin. P2 only produces "attempt" (validator-direct); the
    # column stays so assessment/review/recomputation sources can attach
    # later without a redesign. Never fabricated.
    source: Mapped[str] = mapped_column(String(20), default="attempt")
    # Canonical skill reference (SKILL_TAXONOMY.md skill_key). NULL only
    # for rows that carry no skill claim (no-response effort signals,
    # invalid-content outcomes). Formal Skill state arrives in P3.
    skill_key: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    # "primary" | "secondary" | "none". Secondary rows must never carry
    # the same weight as primary rows (P3 guardrail).
    skill_role: Mapped[str] = mapped_column(String(10), default="primary")
    # Core mistake key (taxonomy.CORE_MISTAKES) or None for clean
    # positive demonstrations and content-side neutral outcomes.
    mistake_core: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    # Exercise-specific mistake key (taxonomy.SPECIFIC_TO_CORE) or None
    # when only the core claim is observable.
    mistake_specific: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # "positive" | "negative" | "neutral".
    direction: Mapped[str] = mapped_column(String(10), index=True)
    # Ordinals, never scores: "weak" | "direct" | "strong".
    strength: Mapped[str] = mapped_column(String(10))
    # Ordinals, never scores: "high" | "medium" | "low".
    confidence: Mapped[str] = mapped_column(String(10))
    # Frozen observation context: mode, result, hint/duration/count
    # snapshots, mistake elements, puzzle snapshots. Small by design;
    # full validator detail lives on Attempt.validation_detail.
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Deterministic idempotency key within the attempt, e.g.
    # "neg:missed-capture:primary:capture-finding".
    evidence_key: Mapped[str] = mapped_column(String(120))
    # When the event was observed (attempt submission time, not insert
    # time): trend math in later phases depends on this.
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
