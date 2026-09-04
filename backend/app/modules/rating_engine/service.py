"""Rating engine placeholder.

Design intent (not yet implemented):
- Rating is independent per exercise/skill (no global rating yet).
- Future: Glicko-2 style with rating, deviation (uncertainty), volatility.
- Easy puzzles give little on solve / lose more on fail; hard puzzles inverse.
- Practice attempts never touch rating; only rated attempts do.
- Puzzle ratings can drift based on actual user performance.

This stub keeps the call boundary stable so the real algorithm
can land without changing submit_attempt() callers.
"""


def preview_rating_delta(*, score: float) -> float | None:
    # Intentionally returns None: rating not implemented yet.
    # Returning None keeps rating_delta nullable in Attempt rows.
    _ = score
    return None
