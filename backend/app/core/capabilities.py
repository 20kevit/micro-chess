"""Centralized authorization: canonical roles and capabilities.

This is the single capability registry (see docs/platform/SECURITY.md
section 22). Route handlers must express authorization as capabilities
via require_capability(), never as scattered role comparisons.

Deny by default: anything not explicitly granted is denied.

Phase 1 note: the User model has no persisted role yet (roles land in
Phase 2), so every active account acts as PLAYER. Administrative
capabilities therefore deny everyone for now — fail closed by design.
"""

from enum import Enum

from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_user_optional


class Role(str, Enum):
    PLAYER = "PLAYER"
    COACH = "COACH"
    PARENT = "PARENT"
    ADMIN = "ADMIN"


class Capability(str, Enum):
    EXERCISES_READ = "exercises.read"
    EXERCISES_MANAGE = "exercises.manage"
    PUZZLES_READ = "puzzles.read"
    PUZZLES_CREATE = "puzzles.create"
    PUZZLES_MANAGE = "puzzles.manage"
    PUZZLES_REVIEW = "puzzles.review"
    PUZZLES_PUBLISH = "puzzles.publish"
    ATTEMPTS_SUBMIT = "attempts.submit"
    USERS_READ = "users.read"
    USERS_MANAGE = "users.manage"
    GENERATORS_RUN = "generators.run"
    ANALYTICS_VIEW = "analytics.view"
    AUDIT_VIEW = "audit.view"
    SUPPORT_MANAGE = "support.manage"
    RELATIONSHIPS_MANAGE = "relationships.manage"


ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.PLAYER: frozenset(
        {
            Capability.EXERCISES_READ,
            Capability.PUZZLES_READ,
            Capability.ATTEMPTS_SUBMIT,
            Capability.USERS_READ,
        }
    ),
    # Coach/parent/admin grants are defined in Phase 2 together with the
    # persisted role model. Until then these roles grant nothing: any
    # endpoint requiring their capabilities denies by default.
    Role.COACH: frozenset(),
    Role.PARENT: frozenset(),
    Role.ADMIN: frozenset(),
}


def role_for_user(user) -> Role:
    """Phase 1: every authenticated account acts as PLAYER.

    Role persistence (including ADMIN) arrives in Phase 2. This helper
    is the single place that mapping changes.
    """
    _ = user
    return Role.PLAYER


def has_capability(role: Role, capability: Capability) -> bool:
    return capability in ROLE_CAPABILITIES.get(role, frozenset())


def require_capability(capability: Capability, *, allow_anonymous: bool = False):
    """Dependency factory enforcing a capability server-side.

    401 when authentication is required but missing, 403 when the
    identity lacks the capability. Frontend guards are UX only.
    """

    def _check(user=Depends(get_current_user_optional)):
        if user is None:
            if allow_anonymous:
                return None
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth_required")
        if not has_capability(role_for_user(user), capability):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return _check
