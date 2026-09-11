"""Audit primitive for security-relevant actions.

Phase 1 provides the call boundary only: structured, secret-free log
records. Persisted audit rows land with the administration foundation
(Phase 6), which is the first phase with sensitive administrative
actions. Never pass passwords, tokens, or personal data here.
"""

import logging
from typing import Any

from app.core.logging import request_id_var

audit_logger = logging.getLogger("microchess.audit")


def audit_event(
    *,
    action: str,
    actor: Any | None = None,
    target_type: str | None = None,
    target_id: Any | None = None,
    result: str = "ok",
    extra: dict | None = None,
) -> None:
    audit_logger.info(
        "audit action=%s actor=%s target=%s:%s result=%s request_id=%s extra=%s",
        action,
        actor,
        target_type,
        target_id,
        result,
        request_id_var.get(),
        extra or {},
    )
