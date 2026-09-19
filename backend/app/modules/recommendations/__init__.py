"""Recommendation domain (P7).

Read-only deterministic selection only: Direct Coach Assignment ->
Recommendation Engine -> Exercise / Puzzle. No new tables, no writes,
no P1-P6 changes.
"""

from app.modules.recommendations import service  # noqa: F401

__all__ = ["service"]
