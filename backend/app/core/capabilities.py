"""Centralized authorization: canonical roles and capabilities.

This is the single capability registry (see docs/platform/SECURITY.md
section 22). Route handlers must express authorization as capabilities
via require_capability(), never as scattered role comparisons.

Deny by default: anything not explicitly granted is denied.

Phase 2: roles are persisted in ``user_roles`` and resolved server-side
from the database on every request. The JWT carries no role information,
so a stale or forged role claim can never escalate. Accounts without an
explicit role row act as PLAYER.
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
    EXERCISES_CREATE = "exercises.create"
    EXERCISES_UPDATE = "exercises.update"
    EXERCISES_ENABLE = "exercises.enable"
    EXERCISES_DISABLE = "exercises.disable"
    EXERCISES_DELETE = "exercises.delete"
    PUZZLES_READ = "puzzles.read"
    PUZZLES_CREATE = "puzzles.create"
    PUZZLES_MANAGE = "puzzles.manage"
    PUZZLES_UPDATE = "puzzles.update"
    PUZZLES_VALIDATE = "puzzles.validate"
    PUZZLES_REVIEW = "puzzles.review"
    PUZZLES_APPROVE = "puzzles.approve"
    PUZZLES_PUBLISH = "puzzles.publish"
    PUZZLES_RETIRE = "puzzles.retire"
    ATTEMPTS_SUBMIT = "attempts.submit"
    USERS_READ = "users.read"
    USERS_READ_PRIVATE = "users.read_private"
    USERS_MANAGE = "users.manage"
    USERS_SUSPEND = "users.suspend"
    USERS_REACTIVATE = "users.reactivate"
    ROLES_ASSIGN = "roles.assign"
    ROLES_REVOKE = "roles.revoke"
    ADMIN_OVERVIEW = "admin.overview"
    GENERATORS_READ = "generators.read"
    GENERATORS_RUN = "generators.run"
    GENERATORS_CANCEL = "generators.cancel"
    ANALYTICS_VIEW = "analytics.view"
    ANALYTICS_READ_PLATFORM = "analytics.read_platform"
    ANALYTICS_READ_EXERCISE = "analytics.read_exercise"
    ANALYTICS_READ_PUZZLE = "analytics.read_puzzle"
    AUDIT_VIEW = "audit.view"
    SUPPORT_MANAGE = "support.manage"
    RELATIONSHIPS_MANAGE = "relationships.manage"
    GUEST_MIGRATE = "accounts.migrate_guest"


_PLAYER_CAPABILITIES = frozenset(
    {
        Capability.EXERCISES_READ,
        Capability.PUZZLES_READ,
        Capability.ATTEMPTS_SUBMIT,
        Capability.USERS_READ,
        Capability.GUEST_MIGRATE,
    }
)

ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.PLAYER: _PLAYER_CAPABILITIES,
    # Coach/parent keep full player access. Student-scoped capabilities
    # arrive with the relationship model (Phase 9); granting broader
    # object access now would bypass the required active-relationship
    # check, so these roles intentionally map to the player set.
    Role.COACH: _PLAYER_CAPABILITIES,
    Role.PARENT: _PLAYER_CAPABILITIES,
    # Platform operations (user/role/content management) land in later
    # phases; ADMIN already carries their capabilities so those endpoints
    # are authorized correctly when introduced. No admin endpoint exists
    # yet, so this grants nothing reachable today.
    Role.ADMIN: frozenset(Capability),
}


def roles_for_user(user) -> list[Role]:
    """Persisted roles for an account, resolved server-side from the DB.

    Unknown role codes are ignored (fail closed); accounts with no role
    row act as PLAYER.
    """
    codes: list[str] = []
    try:
        rows = getattr(user, "roles", None) or []
        codes = [getattr(row, "role", "") for row in rows]
    except Exception:
        codes = []
    valid = {Role(code) for code in codes if code in Role._value2member_map_}
    # Deterministic canonical order (PLAYER first = primary role).
    ordered = [role for role in Role if role in valid]
    return ordered or [Role.PLAYER]


def role_for_user(user) -> Role:
    """Primary role (first persisted row, else PLAYER)."""
    return roles_for_user(user)[0]


def capabilities_for_roles(roles: list[Role]) -> frozenset[Capability]:
    granted: set[Capability] = set()
    for role in roles:
        granted |= set(ROLE_CAPABILITIES.get(role, frozenset()))
    return frozenset(granted)


def has_capability(role: Role, capability: Capability) -> bool:
    return capability in ROLE_CAPABILITIES.get(role, frozenset())


def ensure_capability(user, capability: Capability):
    """Manual check for handlers that need per-field authorization.

    Raises 401 when unauthenticated, 403 when the identity lacks the
    capability. Prefer require_capability() for single-capability routes.
    """
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth_required")
    if capability not in capabilities_for_roles(roles_for_user(user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


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
        if capability not in capabilities_for_roles(roles_for_user(user)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return _check
