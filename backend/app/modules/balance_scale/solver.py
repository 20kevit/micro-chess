"""Balance Scale solver: minimum-piece combination for a target value.

This exercise is intentionally independent of chess rules: no python-chess,
no board, no kings, no checks. Only piece type and its material value
matter; color is irrelevant.

Allowed values: pawn=1, knight=3, bishop=3, rook=5, queen=9. Since knight
and bishop share a value, the minimum *count* only depends on the distinct
denominations [1, 3, 5, 9] — a small bounded coin-change problem solved
exactly with dynamic programming (no lookup tables, no heuristics).

The solver never trusts client input; the server recomputes the target
from the stored left pieces and the optimal count from scratch.
"""

from __future__ import annotations

# Distinct denominations that matter for the minimum count.
DENOMINATIONS = (1, 3, 5, 9)

# Canonical representative piece per value (lowercase per the puzzle spec).
VALUE_TO_PIECE = {1: "p", 3: "n", 5: "r", 9: "q"}

# Hard physical limit of the right pan (10 pyramid slots).
MAX_PIECES = 10


def optimal_count(target: int) -> int | None:
    """Minimum number of pieces summing exactly to ``target``.

    Returns None for non-positive targets (no puzzle should have one).
    Every positive target is reachable because pawns (value 1) are
    unlimited, so None only signals invalid input — never an
    "impossible" puzzle.
    """
    if not isinstance(target, int) or target <= 0:
        return None
    INF = target + 1
    dp = [0] + [INF] * target
    for amount in range(1, target + 1):
        best = INF
        for coin in DENOMINATIONS:
            if coin <= amount:
                cand = dp[amount - coin] + 1
                if cand < best:
                    best = cand
        dp[amount] = best
    return dp[target] if dp[target] <= target else None


def optimal_combination(target: int) -> list[str]:
    """One canonical minimum-cardinality combination for ``target``.

    Used by the generator and tests only — the validator accepts ANY
    exact combination, never just this one. Prefers heavier pieces
    (greedy from the largest denomination that keeps optimality).
    """
    count = optimal_count(target)
    if count is None:
        raise ValueError("target must be a positive integer")
    combo: list[str] = []
    remaining = target
    # Rebuild via DP table so the result is provably optimal.
    INF = target + 1
    dp = [0] + [INF] * target
    for amount in range(1, target + 1):
        best = INF
        for coin in DENOMINATIONS:
            if coin <= amount:
                cand = dp[amount - coin] + 1
                if cand < best:
                    best = cand
        dp[amount] = best
    while remaining > 0:
        for coin in sorted(DENOMINATIONS, reverse=True):
            if coin <= remaining and dp[remaining - coin] == dp[remaining] - 1:
                combo.append(VALUE_TO_PIECE[coin])
                remaining -= coin
                break
        else:  # pragma: no cover - defensive; pawns guarantee progress
            raise RuntimeError("solver failed to rebuild a combination")
    return combo
