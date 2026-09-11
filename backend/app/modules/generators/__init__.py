"""Content generators (Phase 07).

Generators are controlled content producers, not publishing
mechanisms: every job produces validated candidates that still
require human review, approval, and publication. See
docs/platform/admin/GENERATORS.md.
"""

from app.modules.generators import registry, service  # noqa: F401
from app.modules.generators.models import GeneratorRun  # noqa: F401

__all__ = ["GeneratorRun", "registry", "service"]
