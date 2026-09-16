"""Mistake + evidence domain (P2).

Pipeline::

    Validator -> Attempt Result -> Mistake Classification -> Evidence

``taxonomy.py`` holds the canonical vocabulary (from
``docs/MISTAKE_TAXONOMY.md`` + ``docs/SKILL_TAXONOMY.md``):
:classify.py`` turns a validation into mistake drafts,
``service.py`` persists them as :class:`models.Evidence` rows.

P2 stores evidence only. Skill/level aggregation (P3), mastery (P4),
and recommendation/assessment (P6/P7) consume these rows later.
"""

from app.modules.evidence import classify, service, taxonomy  # noqa: F401

__all__ = ["classify", "service", "taxonomy"]
