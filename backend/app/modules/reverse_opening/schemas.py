"""Step schemas (single-move assistance, not attempts)."""

from pydantic import BaseModel, Field


class StepIn(BaseModel):
    puzzle_id: int
    # Current reconstruction position (server replays history from it).
    fen: str
    # UCI moves already accepted in this reconstruction, in order.
    moves: list[str] = []
    from_square: str = Field(default="", alias="from")
    to_square: str = Field(default="", alias="to")
    promotion: str | None = None

    model_config = {"populate_by_name": True}


class StepOut(BaseModel):
    ok: bool
    # Updated position and history (unchanged input when rejected).
    fen: str
    moves: list[str] = []
    # Canonical SAN of the played move (empty when rejected).
    san: str = ""
    captured: str | None = None
    # True when the history still matches the canonical opening line.
    # Feedback only; final grading compares positions, not lines.
    on_track: bool = True
    message_key: str = ""
