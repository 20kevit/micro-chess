"""Puzzle model. One concrete question/task within an exercise.

Phase 07 content lifecycle: the canonical lifecycle state lives on
``Puzzle.status`` (draft -> validated -> reviewed -> approved ->
published -> retired). The legacy ``is_published``/``is_archived``
booleans are kept in sync as the player-visibility projection so all
existing player queries keep working unchanged:

* player-visible  <=>  status == "published" (is_published True,
  is_archived False)
* retired         <=>  is_archived True (history preserved)

Lifecycle history (``PuzzleStatusHistory``), validation records
(``PuzzleValidation``), and human reviews (``PuzzleReview``) are
append-only facts owned by the content domain.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Canonical Phase 07 lifecycle states (stored on Puzzle.status).
STATUS_DRAFT = "draft"
STATUS_VALIDATED = "validated"
STATUS_REVIEWED = "reviewed"
STATUS_APPROVED = "approved"
STATUS_PUBLISHED = "published"
STATUS_RETIRED = "retired"

PUZZLE_STATUSES = (
    STATUS_DRAFT,
    STATUS_VALIDATED,
    STATUS_REVIEWED,
    STATUS_APPROVED,
    STATUS_PUBLISHED,
    STATUS_RETIRED,
)

# Puzzle origins. Generated/imported content is never auto-published.
SOURCE_MANUAL = "manual"
SOURCE_GENERATED = "generated"
SOURCE_IMPORTED = "imported"

PUZZLE_SOURCES = (SOURCE_MANUAL, SOURCE_GENERATED, SOURCE_IMPORTED)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _default_initial_status(context) -> str:
    """Derive the lifecycle entry state from explicitly-passed flags.

    Rows constructed directly as already-published (runtime exercise
    generators, content seeds) enter the lifecycle as ``published``;
    archived rows enter as ``retired``; everything else starts as a
    ``draft``. Admin-managed transitions always write ``status``
    explicitly, so this default only affects direct constructions.
    """
    try:
        params = context.get_current_parameters() or {}
    except Exception:
        params = {}
    if params.get("is_archived"):
        return STATUS_RETIRED
    if params.get("is_published"):
        return STATUS_PUBLISHED
    return STATUS_DRAFT


class Puzzle(Base):
    __tablename__ = "puzzles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_slug: Mapped[str] = mapped_column(String(100), ForeignKey("exercises.slug"), index=True)
    # FEN/position payload when applicable; nullable for non-board exercises.
    fen: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Definitive answer. Immutable once published (enforced in service layer).
    answer_json: Mapped[dict] = mapped_column(JSON, default=dict)
    hint_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Question/instruction shown to the user (Persian).
    prompt_fa: Mapped[str] = mapped_column(String(500), default="")
    # Educational content shown after answering (solution/explanation).
    explanation: Mapped[str] = mapped_column(String(2000), default="")
    initial_rating: Mapped[float] = mapped_column(Float, default=1200.0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # --- Phase 07 content lifecycle -------------------------------------
    # Canonical lifecycle state. Player visibility is derived from it and
    # mirrored onto is_published/is_archived (see module docstring).
    status: Mapped[str] = mapped_column(String(20), default=_default_initial_status, index=True)
    # Content origin for provenance (manual/generated/imported).
    source: Mapped[str] = mapped_column(String(20), default=SOURCE_MANUAL)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Traceability to the generation job that produced this candidate.
    generator_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Declared/target difficulty (generation objective, not a guarantee).
    # Observed difficulty is derived from real attempts in Phase 8.
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Deduplication hash over canonical (exercise, fen, answer) content.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PuzzleStatusHistory(Base):
    """Append-only lifecycle transition log (one row per transition)."""

    __tablename__ = "puzzle_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    puzzle_id: Mapped[int] = mapped_column(Integer, ForeignKey("puzzles.id"), index=True)
    from_status: Mapped[str] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class PuzzleValidation(Base):
    """Append-only content-validation record (one row per validation run)."""

    __tablename__ = "puzzle_validations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    puzzle_id: Mapped[int] = mapped_column(Integer, ForeignKey("puzzles.id"), index=True)
    validator_version: Mapped[str] = mapped_column(String(20), default="1")
    status: Mapped[str] = mapped_column(String(10), default="fail")  # pass | fail
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    validated_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class PuzzleReview(Base):
    """Append-only human-review record (one row per review decision)."""

    __tablename__ = "puzzle_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    puzzle_id: Mapped[int] = mapped_column(Integer, ForeignKey("puzzles.id"), index=True)
    reviewer_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str] = mapped_column(String(20))  # approve | request_changes | reject
    notes: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
