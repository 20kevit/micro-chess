"""Skill mastery domain (P4).

Read-only derivation only: Evidence -> Skill State -> Mastery.
No new tables, no writes, no P2/P3 changes.
"""

from app.modules.mastery import service  # noqa: F401

__all__ = ["service"]
