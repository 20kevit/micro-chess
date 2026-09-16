"""Canonical P2 vocabulary: mistakes, skills, evidence ordinals.

Authoritative sources (Proposed, Phase 0C/skill spec):

* ``docs/MISTAKE_TAXONOMY.md`` — 8 core mistakes + 26 exercise-specific
  types, mistake -> skill mapping, strength/confidence ordinals, evidence
  record shape, repetition/speed rules.
* ``docs/SKILL_TAXONOMY.md`` — 18 atomic skills, exercise -> skill mapping
  (primary/secondary with link strength).

Rules enforced here:

* Core keys are stable strings (``missed-target`` etc.). No new generic
  keys are invented; ``partial`` stays an outcome, never a mistake.
* Strength and confidence are ORDINALS (Phase 0 rejects numeric severity
  in v1). Strength in {weak, direct, strong}; confidence in
  {high, medium, low}. Derivation:
    - validator-direct observation -> direct / high
    - deterministic recompute from stored raw answer + puzzle -> direct
      / high (same function, same inputs)
    - engine/post-hoc derivation needing an extra step (SAN parse, FEN
      replay, stalemate test) -> at most strong / medium
    - format/terminal/latency signals -> weak / high
    - repetition of an established mistake pattern -> strong / high
    - scaffolding (hints used) downgrades positive evidence -> weak
    - strength x confidence multiply; unresolvable input -> neutral /
      weak / low, never a fabricated specific claim.
* Direction in {positive, negative, neutral}:
    - positive: clean or scaffolded correct demonstration.
    - negative: classified chess/skill error (incl. repeated patterns).
    - neutral: recorded but must not move skill estimates (no-response,
      malformed input, inefficiency notes on correct solves,
      invalid-puzzle outcomes, unclassifiable failures).
* ``no-response`` never carries a skill (effort signal, not weakness).
* ``malformed-input`` carries the originating primary skill at weak
  strength (format failure, not ability evidence) with neutral direction.
"""

# --- core mistake keys (MISTAKE_TAXONOMY.md section 2) -----------------------

MISSED_TARGET = "missed-target"
WRONG_TARGET = "wrong-target"
MALFORMED_INPUT = "malformed-input"
ILLEGAL_ACTION = "illegal-action"
WRONG_CHOICE = "wrong-choice"
INEFFICIENCY = "inefficiency"
NO_RESPONSE = "no-response"
REPEATED_MISTAKE = "repeated-mistake"

CORE_MISTAKES = (
    MISSED_TARGET,
    WRONG_TARGET,
    MALFORMED_INPUT,
    ILLEGAL_ACTION,
    WRONG_CHOICE,
    INEFFICIENCY,
    NO_RESPONSE,
    REPEATED_MISTAKE,
)

# --- exercise-specific mistake keys (MISTAKE_TAXONOMY.md section 3) ----------
# Value: core parent. ``missed-alternative`` is documented as an accepted
# alternative, not an error, so it is never emitted.

SPECIFIC_TO_CORE: dict[str, str] = {
    "missed-capture": MISSED_TARGET,
    "phantom-capture": WRONG_TARGET,
    "missed-loose-piece": MISSED_TARGET,
    "false-loose-claim": WRONG_TARGET,
    "missed-trap": MISSED_TARGET,
    "false-trap-claim": WRONG_TARGET,
    "role-swap": WRONG_TARGET,
    "non-pin-triplet": WRONG_TARGET,
    "escape-blindness": WRONG_CHOICE,
    "stalemate-blindness": WRONG_CHOICE,
    "false-alarm": WRONG_CHOICE,
    "missed-check": MISSED_TARGET,
    "phantom-check": WRONG_TARGET,
    "missed-escape": MISSED_TARGET,
    "phantom-escape": WRONG_TARGET,
    "wrong-start": ILLEGAL_ACTION,
    "illegal-step": ILLEGAL_ACTION,
    "incomplete-path": MISSED_TARGET,
    "unsafe-step": ILLEGAL_ACTION,
    # "defended-capture" deferred: needs transition cause analysis (Medium);
    # unsafe-step covers obstacle replay failures at P2.
    "miscount-direction": WRONG_CHOICE,
    "arithmetic-gap": WRONG_TARGET,
    "over-count": INEFFICIENCY,
    "binding-error": WRONG_TARGET,
    "omission-lapse": MISSED_TARGET,
    "hallucination": WRONG_TARGET,
    "identity-error": WRONG_TARGET,
    "parity-error": WRONG_CHOICE,
    "wrong-tactic": WRONG_TARGET,
    "notation-error": MALFORMED_INPUT,
    "early-divergence": ILLEGAL_ACTION,
    "late-divergence": ILLEGAL_ACTION,
    "illegal-sequence": ILLEGAL_ACTION,
    "missed-option": MISSED_TARGET,
    "false-option": WRONG_TARGET,
}

# --- skills (SKILL_TAXONOMY.md sections 2-3: 6 groups / 18 skills) -----------

SKILL_GROUPS: dict[str, tuple[str, ...]] = {
    "board-literacy": ("piece-identification", "square-knowledge", "position-recall"),
    "move-generation": (
        "legal-destinations",
        "check-giving",
        "check-escaping",
        "castling-legality",
    ),
    "attack-reading": (
        "capture-finding",
        "undefended-detection",
        "trap-evaluation",
        "pin-recognition",
        "mate-classification",
    ),
    "path-planning": ("shortest-path", "constrained-path"),
    "mental-board": ("blind-tactics", "sequence-reconstruction"),
    "material-reasoning": ("material-comparison", "value-composition"),
}

SKILLS: tuple[str, ...] = tuple(s for group in SKILL_GROUPS.values() for s in group)

# --- exercise -> skill mapping (SKILL_TAXONOMY.md section 5) -----------------
# Value: (primary skill, [(secondary skill, link strength)]).
# Link strength in {"strong", "weak"} is the documented qualifier; P3 must
# use the skill_role column (not equal weights) when consuming these rows.

EXERCISE_SKILLS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "piece-recognition": ("piece-identification", []),
    "blindfold-square-vision": ("square-knowledge", []),
    "chinese-board": ("position-recall", []),
    "legal-destinations": ("legal-destinations", []),
    "give-check": ("check-giving", [("legal-destinations", "strong")]),
    "get-out-of-check": ("check-escaping", [("legal-destinations", "strong")]),
    "castling-rights": ("castling-legality", []),
    "captures": ("capture-finding", [("legal-destinations", "strong")]),
    "undefended-pieces": ("undefended-detection", []),
    "trapped-pieces": ("trap-evaluation", [("capture-finding", "weak")]),
    "pin": ("pin-recognition", []),
    "is-checkmate": ("mate-classification", []),
    "pathfinding": ("shortest-path", []),
    "pathfinding-obstacles": ("constrained-path", [("shortest-path", "strong")]),
    "blindfold-calculation": ("blind-tactics", []),
    "opening-traps": ("blind-tactics", []),
    "reverse-opening": ("sequence-reconstruction", []),
    "heavier-side": ("material-comparison", []),
    "balance-scale": ("value-composition", [("material-comparison", "weak")]),
}

# --- evidence ordinals --------------------------------------------------------

SOURCE_ATTEMPT = "attempt"

DIRECTION_POSITIVE = "positive"
DIRECTION_NEGATIVE = "negative"
DIRECTION_NEUTRAL = "neutral"
DIRECTIONS = (DIRECTION_POSITIVE, DIRECTION_NEGATIVE, DIRECTION_NEUTRAL)

STRENGTH_WEAK = "weak"
STRENGTH_DIRECT = "direct"
STRENGTH_STRONG = "strong"
STRENGTHS = (STRENGTH_WEAK, STRENGTH_DIRECT, STRENGTH_STRONG)

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCES = (CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW)

ROLE_PRIMARY = "primary"
ROLE_SECONDARY = "secondary"
ROLE_NONE = "none"


def primary_skill(exercise_slug: str) -> str | None:
    """Canonical primary skill for an exercise, or None when unmapped."""
    mapping = EXERCISE_SKILLS.get(exercise_slug)
    return mapping[0] if mapping else None


def secondary_skills(exercise_slug: str) -> list[tuple[str, str]]:
    """Canonical [(skill, link strength)] secondaries for an exercise."""
    mapping = EXERCISE_SKILLS.get(exercise_slug)
    return list(mapping[1]) if mapping else []
