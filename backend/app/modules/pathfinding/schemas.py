"""Pathfinding step schemas (single-move assistance, not attempts)."""

from pydantic import BaseModel, Field


class StepIn(BaseModel):
    puzzle_id: int
    # Current board position (server recomputes everything from it).
    fen: str
    # Current square of the selected piece.
    selected_at: str = ""
    from_square: str = Field(default="", alias="from")
    to_square: str = Field(default="", alias="to")
    promotion: str = "q"

    model_config = {"populate_by_name": True}


class StepOut(BaseModel):
    ok: bool
    # Updated position (unchanged input when the step is rejected).
    fen: str
    selected_at: str
    reached: bool
    captured: str | None = None
    message_key: str = ""
