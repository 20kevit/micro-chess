"""Generator job persistence (Phase 07).

A generation job (``GeneratorRun``) is an operational historical
record: generator identity + version, target exercise, validated
configuration snapshot, requested quantity, execution status, and
the validation summary. Rows are append-only; failed jobs keep
their error, configuration, and version for debugging.

Only portable SQLAlchemy column types are used (SQLite dev +
future PostgreSQL).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Canonical job states (see docs/platform/admin/GENERATORS.md).
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

JOB_STATUSES = (
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_CANCELLED,
)

TERMINAL_STATUSES = frozenset({STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class GeneratorRun(Base):
    __tablename__ = "generator_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stable generator identifier from the central code registry.
    generator_code: Mapped[str] = mapped_column(String(100), index=True)
    generator_version: Mapped[str] = mapped_column(String(20))
    exercise_slug: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_QUEUED, index=True)
    requested_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_count: Mapped[int] = mapped_column(Integer, default=0)
    validated_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    # Reproducibility input: same code + version + seed + config replays
    # the same candidate sequence (dedup against live content may still
    # skip already-existing candidates; see service docs).
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Generation objectives (not guarantees; actual characteristics are
    # recorded per candidate / in the result summary).
    target_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Validated configuration snapshot (whitelisted keys only; never
    # executable code or secrets).
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Result summary: accepted puzzle ids + rejected-candidate reasons.
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(String(1000), default="")
    requested_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
