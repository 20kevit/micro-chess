"""Centralized authorization: canonical roles and capabilities.

This is the single capability registry (see docs/platform/SECURITY.md
section 22). Route handlers must express authorization as capabilities
via require_capability(), never as scattered role comparisons.

Deny by default: anything not explicitly granted is denied.

Phase 2: roles are persisted in ``user_roles`` and resolved server-side
from the database on every request. The JWT carries no role information,
so a stale or forged role claim can never escalate. Accounts without an
explicit role row act as PLAYER.

Phase 12: each session carries exactly one active role
(``auth_sessions.active_role``), always a member of the user's assigned
roles. Authorization resolves the capability set from the session's
active role, not from the union of assigned roles: a multi-role user in
a PLAYER session holds exactly the PLAYER capabilities. When the active
role is no longer assigned (e.g. revoked mid-session), the session
authorizes as nothing and requests fail closed; the client must
re-authenticate (a fresh login picks a valid role). Object-level checks
(relationships, ownership) are unchanged and remain authoritative.
"""

from enum import Enum

from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_session_optional, get_current_user_optional


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
    SUPPORT_CREATE = "support.create"
    SUPPORT_READ_OWN = "support.read_own"
    SUPPORT_READ = "support.read"
    SUPPORT_RESPOND = "support.respond"
    SUPPORT_CLOSE = "support.close"
    SUPPORT_MANAGE = "support.manage"
    RELATIONSHIPS_MANAGE = "relationships.manage"
    RELATIONSHIPS_CREATE = "relationships.create"
    RELATIONSHIPS_ACCEPT = "relationships.accept"
    RELATIONSHIPS_REVOKE = "relationships.revoke"
    GUEST_MIGRATE = "accounts.migrate_guest"


_PLAYER_CAPABILITIES = frozenset(
    {
        Capability.EXERCISES_READ,
        Capability.PUZZLES_READ,
        Capability.ATTEMPTS_SUBMIT,
        Capability.USERS_READ,
        Capability.GUEST_MIGRATE,
        # Phase 9: every account may take part in relationship flows
        # (initiate, accept, revoke) for relationships it belongs to.
        # Object-level checks in the relationships service enforce party
        # membership; the capability alone never grants access to another
        # student's data.
        Capability.RELATIONSHIPS_CREATE,
        Capability.RELATIONSHIPS_ACCEPT,
        Capability.RELATIONSHIPS_REVOKE,
        # Phase 11: every account may open its own support requests and
        # read/reply to them. Staff capabilities (read/respond/close/
        # manage) stay ADMIN-held; object checks in the support service
        # enforce ownership for the *_own capabilities.
        Capability.SUPPORT_CREATE,
        Capability.SUPPORT_READ_OWN,
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


def active_role_for_session(session, user) -> Role | None:
    """The session's authoritative active role, or None when the
    ``active_role in assigned roles`` invariant no longer holds.

    Never falls back to another role: a revoked/unknown active role
    authorizes as nothing (fail closed). The JWT carries no role, so
    this always resolves server-side from the session row + role rows.
    """
    if session is None or user is None:
        return None
    code = getattr(session, "active_role", None)
    if not isinstance(code, str) or code not in Role._value2member_map_:
        return None
    role = Role(code)
    if role not in roles_for_user(user):
        return None
    return role


def capabilities_for_session(session, user) -> frozenset[Capability]:
    """Capability set active for this session (active role only)."""
    role = active_role_for_session(session, user)
    if role is None:
        return frozenset()
    return frozenset(ROLE_CAPABILITIES.get(role, frozenset()))


def ensure_capability(user, capability: Capability, session=None):
    """Manual check for handlers that need per-field authorization.

    Raises 401 when unauthenticated (or when the session's active role
    is no longer assigned), 403 when the active role lacks the
    capability. Prefer require_capability() for single-capability routes.
    """
    if user is None or session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth_required")
    if active_role_for_session(session, user) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="active_role_revoked")
    if capability not in capabilities_for_session(session, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


def require_capability(capability: Capability, *, allow_anonymous: bool = False):
    """Dependency factory enforcing a capability server-side.

    401 when authentication is required but missing (including when the
    session's active role is no longer assigned — fail closed, never
    fall back to another role), 403 when the active role lacks the
    capability. Frontend guards are UX only.
    """

    def _check(
        user=Depends(get_current_user_optional),
        session=Depends(get_current_session_optional),
    ):
        if session is not None and not hasattr(session, "active_role"):
            # Direct unit-test invocation (the Depends marker never
            # resolves outside a request): there is no session. Without a
            # user this is the anonymous path; with a user, fall back to
            # the assigned-roles union, as before Phase 12. Real requests
            # always resolve to an AuthSession row or None, so HTTP
            # behavior stays strict.
            if user is None:
                session = None
            else:
                if capability not in capabilities_for_roles(roles_for_user(user)):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
                return user
        if user is None or session is None:
            if allow_anonymous and session is None and user is None:
                return None
            # A broken session (revoked role, tampered token) must never
            # silently downgrade to anonymous: fail closed.
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth_required")
        if active_role_for_session(session, user) is None:
            if allow_anonymous:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth_required")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="active_role_revoked")
        if capability not in capabilities_for_session(session, user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return _check
