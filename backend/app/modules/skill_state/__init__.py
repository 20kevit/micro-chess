"""Skill state domain (P3).

Read-only aggregation only. Skill levels are derived from stored
evidence — no new tables, no writes, no P2 changes.
"""

from app.modules.skill_state import service  # noqa: F401

__all__ = ["service"]
