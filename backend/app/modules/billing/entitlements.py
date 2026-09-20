"""Feature entitlements: the single authoritative access vocabulary.

Everything currently shippable in the beta stays available to free
accounts (the beta must keep working). Premium-only gates apply
exclusively to new advanced capabilities that do not exist yet or are
explicitly introduced as premium (see ``PREMIUM_ONLY_FEATURES``).
Routes must call ``can_access``/``require_entitlement`` here instead of
scattering ``if user.subscription == ...`` checks; the frontend is never
authoritative (a hidden button is not security).
"""

# All known feature keys. Free-tier keys are usable with a free
# subscription; premium keys additionally require trialing/active paid
# access. ``personalized_training_package`` names the future
# rating-signal training package (external FIDE/Lichess/Chess.com
# integrations are NOT implemented; the key only reserves the boundary).
FREE_FEATURES = frozenset(
    {
        "basic_training",
        "practice_access",
        "progress_tracking",
        "recommendations",
        "basic_xp_streak",
        "coach_features",
        "parent_features",
    }
)

PREMIUM_ONLY_FEATURES = frozenset(
    {
        "advanced_analytics",
        "advanced_personalization",
        "personalized_training_package",
        "speed_training",
        "premium_training_content",
    }
)

ALL_FEATURES = FREE_FEATURES | PREMIUM_ONLY_FEATURES

# Subscription statuses that confer paid access. ``cancelled`` keeps paid
# access until ``current_period_end`` (handled by time check, not here).
PAID_STATUSES = frozenset({"trialing", "active", "past_due"})


def is_paid_status(status: str) -> bool:
    return status in PAID_STATUSES


def features_for_plan(plan_code: str, status: str, has_paid_access: bool) -> set[str]:
    """Authoritative feature set for a (plan, status) pair.

    Free plan (any usable status) -> free features only. Premium plan
    with live paid access -> everything. Anything else -> free features
    (fail closed to the useful free tier, never to nothing: the beta
    must stay usable).
    """
    _ = (plan_code, status)
    if has_paid_access:
        return set(ALL_FEATURES)
    return set(FREE_FEATURES)


def can_access(feature: str, *, has_paid_access: bool) -> bool:
    """Pure predicate: does this access level include ``feature``?"""
    if feature in FREE_FEATURES:
        return True
    if feature in PREMIUM_ONLY_FEATURES:
        return bool(has_paid_access)
    # Unknown features deny by default (fail closed).
    return False
