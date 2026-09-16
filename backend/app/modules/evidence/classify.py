"""Mistake classification: validation -> mistake drafts (P2).

Exercise-aware and modular: each exercise slug maps to a classifier
function via :func:`register_classifier` (populated below from data
tables, never a giant ``if/elif exercise_slug`` chain in core flow).
Set-selection exercises share one parametrized engine; only
genuinely different answer semantics get dedicated functions.

Every function here is total: unexpected input yields an explicit
neutral ``unclassified`` draft (never raises, never fabricates a
specific claim). Confidence follows the taxonomy rule — validator-live
is High, post-hoc engine derivation (SAN parse, FEN replay, stalemate
test) is Medium. Chess-rule logic is never duplicated: classifiers
reuse the exercise validators' own pure helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.modules.evidence import taxonomy as tx
from app.modules.rule_engine.base import AttemptResult

TERMINAL_RESULTS = (
    AttemptResult.TIMEOUT.value,
    AttemptResult.SKIPPED.value,
    AttemptResult.ABANDONED.value,
)


@dataclass(frozen=True)
class MistakeDraft:
    """One evidence row to persist (repeat detection happens in service)."""

    direction: str
    mistake_core: str | None
    mistake_specific: str | None
    skill: str | None
    role: str = tx.ROLE_PRIMARY
    # Documented link qualifier for secondary rows ("strong"/"weak"/None).
    link: str | None = None
    strength: str = tx.STRENGTH_DIRECT
    confidence: str = tx.CONFIDENCE_HIGH
    context: dict[str, Any] = field(default_factory=dict)


ClassifierFn = Callable[
    [str, dict[str, Any], dict[str, Any], dict[str, Any], list[str]], list[MistakeDraft]
]

_CLASSIFIERS: dict[str, ClassifierFn] = {}


def register_classifier(slug: str, fn: ClassifierFn) -> None:
    _CLASSIFIERS[slug] = fn


def get_classifier(slug: str) -> ClassifierFn | None:
    return _CLASSIFIERS.get(slug)


# --- shared draft builders ----------------------------------------------------


def _positive(skill: str | None, hints_used: list[str]) -> MistakeDraft:
    scaffolded = bool(hints_used)
    return MistakeDraft(
        direction=tx.DIRECTION_POSITIVE,
        mistake_core=None,
        mistake_specific=None,
        skill=skill,
        strength=tx.STRENGTH_WEAK if scaffolded else tx.STRENGTH_DIRECT,
        confidence=tx.CONFIDENCE_HIGH,
        context={"scaffolded": scaffolded},
    )


def _no_response() -> MistakeDraft:
    # Effort signal only: never carries a skill (taxonomy section 5).
    return MistakeDraft(
        direction=tx.DIRECTION_NEUTRAL,
        mistake_core=tx.NO_RESPONSE,
        mistake_specific=None,
        skill=None,
        role=tx.ROLE_NONE,
        strength=tx.STRENGTH_WEAK,
        confidence=tx.CONFIDENCE_HIGH,
    )


def _malformed(skill: str | None, count: int = 0) -> MistakeDraft:
    # Format failure, not ability evidence: neutral + weak, originating skill.
    return MistakeDraft(
        direction=tx.DIRECTION_NEUTRAL,
        mistake_core=tx.MALFORMED_INPUT,
        mistake_specific=None,
        skill=skill,
        strength=tx.STRENGTH_WEAK,
        confidence=tx.CONFIDENCE_HIGH,
        context={"malformed_count": count} if count else {},
    )


def _invalid_content(note: str) -> MistakeDraft:
    # The puzzle/row cannot be answered (invalid FEN, no pin, ...):
    # a wrong result here blames content, never the user.
    return MistakeDraft(
        direction=tx.DIRECTION_NEUTRAL,
        mistake_core=None,
        mistake_specific=None,
        skill=None,
        role=tx.ROLE_NONE,
        strength=tx.STRENGTH_WEAK,
        confidence=tx.CONFIDENCE_HIGH,
        context={"invalid_content": note},
    )


def _unclassified(skill: str | None, reason: str) -> MistakeDraft:
    return MistakeDraft(
        direction=tx.DIRECTION_NEUTRAL,
        mistake_core=None,
        mistake_specific=None,
        skill=skill,
        role=tx.ROLE_NONE,
        strength=tx.STRENGTH_WEAK,
        confidence=tx.CONFIDENCE_LOW,
        context={"classification": "unsupported", "reason": reason},
    )


def _negative(
    core: str,
    specific: str | None,
    skill: str,
    *,
    strength: str = tx.STRENGTH_DIRECT,
    confidence: str = tx.CONFIDENCE_HIGH,
    context: dict[str, Any] | None = None,
) -> MistakeDraft:
    if specific is not None:
        expected_parent = tx.SPECIFIC_TO_CORE.get(specific)
        assert expected_parent == core, f"{specific} is not a {core}"
    return MistakeDraft(
        direction=tx.DIRECTION_NEGATIVE,
        mistake_core=core,
        mistake_specific=specific,
        skill=skill,
        strength=strength,
        confidence=confidence,
        context=dict(context or {}),
    )


def _with_secondaries(
    drafts: list[MistakeDraft],
    exercise_slug: str,
    *,
    commission_only: bool,
    had_commission: bool,
) -> list[MistakeDraft]:
    """Fan out canonical secondary-skill rows (SKILL_TAXONOMY section 5).

    Secondary rows inherit the primary row's mistake/direction/strength/
    confidence; the ``role`` + ``link`` fields are the guardrail P3 must
    use instead of equal weighting (secondary weights are Open).
    """
    secondaries = tx.secondary_skills(exercise_slug)
    if not secondaries:
        return drafts
    if commission_only and not had_commission:
        return drafts
    out = list(drafts)
    for draft in drafts:
        if draft.direction != tx.DIRECTION_NEGATIVE or draft.role != tx.ROLE_PRIMARY:
            continue
        if draft.skill != tx.primary_skill(exercise_slug):
            continue
        if commission_only and draft.mistake_core != tx.WRONG_TARGET:
            # Enumeration-weakness links (give-check, captures,
            # get-out-of-check) implicate the sub-skill only through
            # hallucinated commissions, never through omissions.
            continue
        for skill, link in secondaries:
            out.append(
                MistakeDraft(
                    direction=draft.direction,
                    mistake_core=draft.mistake_core,
                    mistake_specific=draft.mistake_specific,
                    skill=skill,
                    role=tx.ROLE_SECONDARY,
                    link=link,
                    strength=draft.strength,
                    confidence=draft.confidence,
                    context={**draft.context, "skill_link": link},
                )
            )
    return out


def _as_lists(detail: dict[str, Any]) -> tuple[list, list, list]:
    def _list(value: Any) -> list:
        return list(value) if isinstance(value, list) else []

    return _list(detail.get("correct")), _list(detail.get("missed")), _list(detail.get("wrong"))


# --- set-selection engine -----------------------------------------------------
# Shared by every square/move/option set-match exercise. Only the specific
# key names, the raw-answer parser, and the secondary rule differ per
# exercise, so those stay data (see _SET_MATCH_PARAMS below).


def make_set_match_classifier(
    *,
    specific_missed: str | None,
    specific_wrong: str | None,
    parse_selections: Callable[[Any], tuple[set, list]],
    secondary_mode: str | None = None,
    invalid_guard: Callable[[dict[str, Any]], str | None] | None = None,
) -> ClassifierFn:
    """Build a set-match classifier.

    ``parse_selections`` reuses the exercise's own split helper on the raw
    attempt (shared ``split_squares``/``split_moves``/``split_options`` —
    input parsing, never chess rules). ``secondary_mode`` is None (no
    secondaries), "commission" (enumerate-weakness only on false
    positives), or "any". ``invalid_guard`` optionally maps the puzzle
    answer to an invalid-content note (content bug, not user error).
    """

    def classify_set(
        slug: str,
        detail: dict[str, Any],
        raw_answer: dict[str, Any],
        puzzle_answer: dict[str, Any],
        hints_used: list[str],
    ) -> list[MistakeDraft]:
        skill = tx.primary_skill(slug)
        _correct, missed, wrong = _as_lists(detail)
        valid_selected, malformed = parse_selections(raw_answer)
        if not valid_selected and not _correct:
            if malformed:
                return [_malformed(skill, len(malformed))]
            # Nothing submitted against a non-empty target: effort
            # signal, not a skill claim.
            return [_no_response()]
        wrong_valid = [w for w in wrong if w not in set(malformed)]
        drafts: list[MistakeDraft] = []
        if missed:
            drafts.append(
                _negative(
                    tx.MISSED_TARGET,
                    specific_missed,
                    skill or slug,
                    context={"missed": list(missed)[:64], "missed_count": len(missed)},
                )
            )
        if wrong_valid:
            drafts.append(
                _negative(
                    tx.WRONG_TARGET,
                    specific_wrong,
                    skill or slug,
                    context={"wrong": list(wrong_valid)[:64], "wrong_count": len(wrong_valid)},
                )
            )
        if malformed:
            drafts.append(_malformed(skill, len(malformed)))
        if not drafts:
            return [_unclassified(skill, "empty-set-diff")]
        commission = bool(wrong_valid)
        return _with_secondaries(
            drafts,
            slug,
            commission_only=(secondary_mode == "commission"),
            had_commission=commission,
        )

    def fn(
        slug: str,
        detail: dict[str, Any],
        raw_answer: dict[str, Any],
        puzzle_answer: dict[str, Any],
        hints_used: list[str],
    ) -> list[MistakeDraft]:
        if invalid_guard is not None:
            note = invalid_guard(puzzle_answer)
            if note is not None:
                return [_invalid_content(note)]
        return classify_set(slug, detail, raw_answer, puzzle_answer, hints_used)

    return fn


def _parse_square_sets(raw_answer: dict[str, Any]) -> tuple[set, list]:
    from app.modules.rule_engine.base import split_squares

    if not isinstance(raw_answer, dict):
        return set(), []
    return split_squares(raw_answer.get("selected_squares", []))


def _parse_give_check_moves(raw_answer: dict[str, Any]) -> tuple[set, list]:
    from app.modules.give_check.validator import split_moves

    if not isinstance(raw_answer, dict):
        return set(), []
    return split_moves(raw_answer.get("moves", []))


def _parse_escape_moves(raw_answer: dict[str, Any]) -> tuple[set, list]:
    from app.modules.get_out_of_check.validator import _selected_moves

    if not isinstance(raw_answer, dict):
        return set(), []
    return _selected_moves(raw_answer)


def _parse_castling_options(raw_answer: dict[str, Any]) -> tuple[set, list]:
    from app.modules.castling_rights.validator import split_options

    if not isinstance(raw_answer, dict):
        return set(), []
    return split_options(raw_answer.get("options", []))


def _get_out_of_check_guard(puzzle_answer: dict[str, Any]) -> str | None:
    """Invalid puzzles (side not in check) make every submission WRONG by
    construction — that verdict describes content, never the user."""
    from app.modules.get_out_of_check.validator import escaping_moves

    fen = puzzle_answer.get("fen") if isinstance(puzzle_answer, dict) else None
    if not isinstance(fen, str):
        return "missing-fen"
    try:
        if not escaping_moves(fen):
            return "side-not-in-check"
    except ValueError:
        return "invalid-fen"
    return None


# slug -> (specific_missed, specific_wrong, parser, secondary_mode, guard?).
# piece-recognition and legal-destinations intentionally carry NO specific
# keys (taxonomy section 3 + rejected list): their set diffs cannot
# distinguish the error mechanism, so core C1/C2 is the honest ceiling.
_SET_MATCH_PARAMS: dict[
    str, tuple[str | None, str | None, Callable[[Any], tuple[set, list]], str | None]
] = {
    "piece-recognition": (None, None, _parse_square_sets, None),
    "legal-destinations": (None, None, _parse_square_sets, None),
    "captures": ("missed-capture", "phantom-capture", _parse_square_sets, "commission"),
    "undefended-pieces": ("missed-loose-piece", "false-loose-claim", _parse_square_sets, None),
    "trapped-pieces": ("missed-trap", "false-trap-claim", _parse_square_sets, "any"),
    "give-check": ("missed-check", "phantom-check", _parse_give_check_moves, "commission"),
    "castling-rights": ("missed-option", "false-option", _parse_castling_options, None),
}

for _slug, (_missed, _wrong, _parser, _secondary) in _SET_MATCH_PARAMS.items():
    register_classifier(
        _slug,
        make_set_match_classifier(
            specific_missed=_missed,
            specific_wrong=_wrong,
            parse_selections=_parser,
            secondary_mode=_secondary,
        ),
    )

# get-out-of-check shares the set engine plus the invalid-puzzle guard
# (mechanism — capture/block/king — is unobservable by design: no type).
register_classifier(
    "get-out-of-check",
    make_set_match_classifier(
        specific_missed="missed-escape",
        specific_wrong="phantom-escape",
        parse_selections=_parse_escape_moves,
        secondary_mode="commission",
        invalid_guard=_get_out_of_check_guard,
    ),
)


# --- single-choice exercises --------------------------------------------------


def _choice_classifier(
    slug: str,
    detail: dict[str, Any],
    raw_answer: dict[str, Any],
    puzzle_answer: dict[str, Any],
    hints_used: list[str],
    *,
    specific_for: Callable[[str, str], str | None],
    choice_keys: tuple[str, ...] = ("choice",),
) -> list[MistakeDraft]:
    """3-way/2-way misclassification (C5 family + miscount-direction)."""
    skill = tx.primary_skill(slug)
    _correct, missed, wrong = _as_lists(detail)
    submitted = wrong[0] if wrong else None
    expected = detail.get("expected") or (missed[0] if missed else None)
    _ = (raw_answer, puzzle_answer, choice_keys)
    if not isinstance(submitted, str) or not submitted:
        return [_malformed(skill, 1)]
    if not isinstance(expected, str) or not expected:
        return [_unclassified(skill, "unknown-expected-choice")]
    specific = specific_for(expected, submitted)
    return [
        _negative(
            tx.WRONG_CHOICE,
            specific,
            skill or slug,
            context={"expected": expected, "submitted": submitted},
        )
    ]


def _checkmate_specific(expected: str, submitted: str) -> str | None:
    if expected == "check" and submitted == "checkmate":
        return "escape-blindness"
    if expected == "not_check" and submitted == "checkmate":
        return None  # resolved by the stalemate test below
    if expected != "checkmate" and submitted == "checkmate":
        return "false-alarm"
    return None


def _classify_checkmate(
    slug: str,
    detail: dict[str, Any],
    raw_answer: dict[str, Any],
    puzzle_answer: dict[str, Any],
    hints_used: list[str],
) -> list[MistakeDraft]:
    import chess

    from app.modules.checkmate.validator import classify as classify_mate

    skill = tx.primary_skill(slug)
    _correct, _missed, wrong = _as_lists(detail)
    submitted = wrong[0] if wrong else None
    if not isinstance(submitted, str) or not submitted:
        return [_malformed(skill, 1)]
    # The validator echoes only the submitted choice, never the expected
    # state: recompute it deterministically from the stored FEN with the
    # validator's own helper (same function, same inputs -> High).
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    fen = answer.get("fen")
    try:
        expected = classify_mate(fen) if isinstance(fen, str) else None
    except ValueError:
        expected = None
    if not isinstance(expected, str) or not expected:
        return [_unclassified(skill, "unknown-expected-choice")]
    if expected == "not_check" and submitted == "checkmate":
        # Stalemate-vs-mate needs the real board: engine derivation,
        # so Medium confidence / Strong-at-best strength (taxonomy 6-7).
        fen = puzzle_answer.get("fen") if isinstance(puzzle_answer, dict) else None
        try:
            board = chess.Board(fen) if isinstance(fen, str) else None
            stalemate = bool(board and not board.is_check() and not list(board.legal_moves))
        except ValueError:
            board, stalemate = None, False
        if stalemate:
            return [
                _negative(
                    tx.WRONG_CHOICE,
                    "stalemate-blindness",
                    skill or slug,
                    strength=tx.STRENGTH_STRONG,
                    confidence=tx.CONFIDENCE_MEDIUM,
                    context={"expected": expected, "submitted": submitted},
                )
            ]
        return [
            _negative(
                tx.WRONG_CHOICE,
                "false-alarm",
                skill or slug,
                context={"expected": expected, "submitted": submitted},
            )
        ]
    specific = _checkmate_specific(expected, submitted)
    return [
        _negative(
            tx.WRONG_CHOICE,
            specific,
            skill or slug,
            context={"expected": expected, "submitted": submitted},
        )
    ]


def _classify_heavier_side(
    slug: str,
    detail: dict[str, Any],
    raw_answer: dict[str, Any],
    puzzle_answer: dict[str, Any],
    hints_used: list[str],
) -> list[MistakeDraft]:
    return _choice_classifier(
        slug,
        detail,
        raw_answer,
        puzzle_answer,
        hints_used,
        specific_for=lambda _e, _s: "miscount-direction",
    )


register_classifier("is-checkmate", _classify_checkmate)
register_classifier("heavier-side", _classify_heavier_side)


# --- pin (atomic ordered triplet) ---------------------------------------------


def _classify_pin(
    slug: str,
    detail: dict[str, Any],
    raw_answer: dict[str, Any],
    puzzle_answer: dict[str, Any],
    hints_used: list[str],
) -> list[MistakeDraft]:
    from app.modules.rule_engine.base import normalize_square

    skill = tx.primary_skill(slug)
    raw = raw_answer.get("squares", raw_answer.get("selected_squares"))
    if not isinstance(raw_answer, dict):
        raw = None
    squares: list[str] = []
    if isinstance(raw, list) and len(raw) == 3:
        normalized = [normalize_square(s) for s in raw]
        if all(s is not None for s in normalized):
            squares = [s for s in normalized if s is not None]
    if not squares:
        return [_malformed(skill, 1)]
    expected: list[str] | None = None
    answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    pin = answer.get("pin")
    if isinstance(pin, list) and len(pin) == 3:
        normalized = [normalize_square(s) for s in pin]
        if all(s is not None for s in normalized):
            expected = [s for s in normalized if s is not None]
    if expected is None:
        # Deterministic recompute from the stored position (same pure
        # helper the validator uses): still High confidence.
        from app.modules.pin.validator import find_pins

        fen = answer.get("fen")
        try:
            pins = find_pins(fen) if isinstance(fen, str) else []
        except ValueError:
            return [_invalid_content("invalid-fen")]
        if not pins:
            return [_invalid_content("no-pin-on-board")]
        first = pins[0]
        expected = [first["pinner"], first["pinned"], first["behind"]]
    if sorted(squares) == sorted(expected) and squares != expected:
        return [_negative(tx.WRONG_TARGET, "role-swap", skill or slug)]
    return [_negative(tx.WRONG_TARGET, "non-pin-triplet", skill or slug)]


register_classifier("pin", _classify_pin)


# --- blindfold square vision (tap vs color choice) ----------------------------


def _classify_square_vision(
    slug: str,
    detail: dict[str, Any],
    raw_answer: dict[str, Any],
    puzzle_answer: dict[str, Any],
    hints_used: list[str],
) -> list[MistakeDraft]:
    from app.modules.rule_engine.base import normalize_square

    skill = tx.primary_skill(slug)
    answer = raw_answer if isinstance(raw_answer, dict) else {}
    clicked = normalize_square(answer.get("square"))
    if clicked is not None:
        # Practice tap on the visible board: wrong square, High confidence.
        return [
            _negative(
                tx.WRONG_TARGET,
                "identity-error",
                skill or slug,
                context={"clicked": clicked},
            )
        ]
    choice = answer.get("choice")
    if isinstance(choice, str) and choice.strip().lower() in ("white", "black"):
        # Speed color button: parity collapse, sources unseparable within.
        return [
            _negative(
                tx.WRONG_CHOICE,
                "parity-error",
                skill or slug,
                context={"choice": choice.strip().lower()},
            )
        ]
    return [_malformed(skill, 1)]


register_classifier("blindfold-square-vision", _classify_square_vision)


# --- blind SAN tactics (calculation + opening traps) --------------------------


def _classify_blind_tactic(
    specific_wrong: str | None, notation_specific: str | None
) -> ClassifierFn:
    def fn(
        slug: str,
        detail: dict[str, Any],
        raw_answer: dict[str, Any],
        puzzle_answer: dict[str, Any],
        hints_used: list[str],
    ) -> list[MistakeDraft]:
        import chess

        skill = tx.primary_skill(slug)
        answer = raw_answer if isinstance(raw_answer, dict) else {}
        submitted = answer.get("move")
        submitted = submitted.strip() if isinstance(submitted, str) else ""
        if not submitted:
            return [_no_response()]
        stored = puzzle_answer if isinstance(puzzle_answer, dict) else {}
        fen = stored.get("fen")
        try:
            board = chess.Board(fen) if isinstance(fen, str) else None
        except ValueError:
            board = None
        if board is None:
            # Result observed, mechanism unverifiable: core only.
            return [_negative(tx.WRONG_CHOICE, None, skill or slug)]
        try:
            move = board.parse_san(submitted)
        except (
            chess.InvalidMoveError,
            chess.IllegalMoveError,
            chess.AmbiguousMoveError,
            ValueError,
        ):
            # Notation vs tactic search is inseparable in the result:
            # weak, Medium (post-hoc parse).
            return [
                MistakeDraft(
                    direction=tx.DIRECTION_NEUTRAL,
                    mistake_core=tx.MALFORMED_INPUT,
                    mistake_specific=notation_specific,
                    skill=skill,
                    strength=tx.STRENGTH_WEAK,
                    confidence=tx.CONFIDENCE_MEDIUM,
                    context={"submitted": submitted[:32]},
                )
            ]
        solutions = stored.get("solutions")
        solution = stored.get("solution")
        if isinstance(solutions, list):
            ok = move.uci() in [s for s in solutions if isinstance(s, str)]
        elif isinstance(solution, str):
            ok = move.uci() == solution
        else:
            ok = False  # legacy mate rows: mating test already failed server-side
        _ = ok
        return [
            _negative(
                tx.WRONG_TARGET,
                specific_wrong,
                skill or slug,
                confidence=tx.CONFIDENCE_MEDIUM,
                context={"submitted": submitted[:32], "uci": move.uci()},
            )
        ]

    return fn


# blindfold-calculation names both post-hoc classes; opening-traps only
# names wrong-tactic (an unparseable trap SAN is generic malformed-input).
register_classifier(
    "blindfold-calculation", _classify_blind_tactic("wrong-tactic", "notation-error")
)
register_classifier("opening-traps", _classify_blind_tactic("wrong-tactic", None))


# --- chinese-board (binding / omission / hallucination) -----------------------


def _classify_chinese_board(
    slug: str,
    detail: dict[str, Any],
    raw_answer: dict[str, Any],
    puzzle_answer: dict[str, Any],
    hints_used: list[str],
) -> list[MistakeDraft]:
    from collections import Counter

    from app.modules.chinese_board.validator import normalize_entry

    skill = tx.primary_skill(slug)
    answer = raw_answer if isinstance(raw_answer, dict) else {}
    raw_pieces = answer.get("pieces")
    if not isinstance(raw_pieces, list):
        return [_malformed(skill, 1)]
    normalized: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for entry in raw_pieces:
        item = normalize_entry(entry)
        if item is None or item[2] in seen:
            return [_malformed(skill, 1)]
        seen.add(item[2])
        normalized.append(item)
    missing = detail.get("missing") if isinstance(detail.get("missing"), list) else []
    extra = detail.get("extra") if isinstance(detail.get("extra"), list) else []
    wrong = detail.get("wrong") if isinstance(detail.get("wrong"), list) else []
    if not missing and not extra and not wrong:
        # Well-formed reconstruction the validator still rejects (bad
        # stored FEN, over-budget, ...): content-side, not user error.
        return [_invalid_content("unexplained-reconstruction-reject")]
    drafts: list[MistakeDraft] = []
    if missing:
        drafts.append(
            _negative(
                tx.MISSED_TARGET,
                "omission-lapse",
                skill or slug,
                context={"missing": missing[:32], "missing_count": len(missing)},
            )
        )
    pair_count = 0
    if wrong and extra:
        rest = list(Counter(wrong) - Counter(extra))
        pair_count = len(rest)
    elif wrong:
        pair_count = len(wrong)
    if pair_count:
        drafts.append(
            _negative(
                tx.WRONG_TARGET,
                "binding-error",
                skill or slug,
                context={"binding_count": pair_count},
            )
        )
    if extra:
        drafts.append(
            _negative(
                tx.WRONG_TARGET,
                "hallucination",
                skill or slug,
                context={"extra": extra[:32], "extra_count": len(extra)},
            )
        )
    return drafts or [_unclassified(skill, "empty-chinese-diff")]


register_classifier("chinese-board", _classify_chinese_board)


# --- balance-scale (arithmetic gap + over-count) ------------------------------


def _classify_balance_scale(
    slug: str,
    detail: dict[str, Any],
    raw_answer: dict[str, Any],
    puzzle_answer: dict[str, Any],
    hints_used: list[str],
) -> list[MistakeDraft]:
    from app.modules.balance_scale.validator import split_pieces

    skill = tx.primary_skill(slug)
    answer = raw_answer if isinstance(raw_answer, dict) else {}
    _submitted, malformed = split_pieces(answer.get("pieces"))
    if malformed:
        return [_malformed(skill, len(malformed))]
    submitted_value = detail.get("submitted_value")
    target_value = detail.get("target_value")
    used = detail.get("used_count")
    optimal = detail.get("optimal_count")
    drafts = [
        _negative(
            tx.WRONG_TARGET,
            "arithmetic-gap",
            skill or slug,
            context={
                "submitted_value": submitted_value,
                "target_value": target_value,
                "used_count": used,
                "optimal_count": optimal,
            },
        )
    ]
    drafts = _with_secondaries(drafts, slug, commission_only=False, had_commission=True)
    if isinstance(used, int) and isinstance(optimal, int) and used > optimal:
        drafts.append(
            MistakeDraft(
                direction=tx.DIRECTION_NEUTRAL,
                mistake_core=tx.INEFFICIENCY,
                mistake_specific="over-count",
                skill=skill,
                strength=tx.STRENGTH_WEAK,
                confidence=tx.CONFIDENCE_HIGH,
                context={"used_count": used, "optimal_count": optimal},
            )
        )
    return drafts


register_classifier("balance-scale", _classify_balance_scale)


# --- pathfinding family (replay-located failures) ----------------------------


def _classify_path(slug: str, *, obstacle: bool) -> ClassifierFn:
    def fn(
        _slug: str,
        detail: dict[str, Any],
        raw_answer: dict[str, Any],
        puzzle_answer: dict[str, Any],
        hints_used: list[str],
    ) -> list[MistakeDraft]:
        from app.modules.rule_engine.base import normalize_square

        skill = tx.primary_skill(_slug)
        answer = raw_answer if isinstance(raw_answer, dict) else {}
        raw_path = answer.get("path")
        if not isinstance(raw_path, list) or not raw_path:
            return [_no_response()]
        path: list[str] = []
        for entry in raw_path:
            square = normalize_square(entry)
            if square is None:
                return [_malformed(skill, 1)]
            path.append(square)
        stored = puzzle_answer if isinstance(puzzle_answer, dict) else {}
        try:
            if obstacle:
                from app.modules.pathfinding_obstacles import transitions as tr
                from app.modules.pathfinding_obstacles.validator import (
                    replay_path as replay_obstacle,
                )

                state = tr.parse_state(stored)
                start = state.white_square
                run = replay_obstacle(state, path)
            else:
                from app.modules.pathfinding import moves
                from app.modules.pathfinding.validator import replay_path as replay_simple

                start = normalize_square(stored.get("from"))
                target = normalize_square(stored.get("target"))
                kind = stored.get("piece")
                kind = kind.strip().lower() if isinstance(kind, str) else None
                optimal = stored.get("optimal_moves")
                if (
                    start is None
                    or target is None
                    or kind not in moves.ALLOWED_KINDS
                    or not isinstance(optimal, int)
                ):
                    return [_invalid_content("invalid-path-puzzle")]
                run = replay_simple(kind, start, target, path)
        except ValueError:
            return [_invalid_content("invalid-path-puzzle")]
        if run.get("ok"):
            return [_unclassified(skill, "replay-disagrees-with-validator")]
        if path[0] != start:
            return _with_secondaries(
                [_negative(tx.ILLEGAL_ACTION, "wrong-start", skill or _slug)],
                _slug,
                commission_only=False,
                had_commission=True,
            )
        fail_at = run.get("fail_at")
        prefix = run.get("prefix") or []
        drafts: list[MistakeDraft] = []
        if len(prefix) == len(path):
            # Every submitted step was legal but the target was never
            # reached: completeness failure, not a rule violation.
            drafts.append(_negative(tx.MISSED_TARGET, "incomplete-path", skill or _slug))
        else:
            specific = "unsafe-step" if obstacle else "illegal-step"
            # Obstacle failure cause (blocked vs controlled vs defended)
            # needs transition analysis: Medium. Simple geometry: High.
            confidence = tx.CONFIDENCE_MEDIUM if obstacle else tx.CONFIDENCE_HIGH
            drafts.append(
                _negative(
                    tx.ILLEGAL_ACTION,
                    specific,
                    skill or _slug,
                    confidence=confidence,
                    context={"fail_at": fail_at},
                )
            )
        return _with_secondaries(drafts, _slug, commission_only=False, had_commission=True)

    return fn


register_classifier("pathfinding", _classify_path("pathfinding", obstacle=False))
register_classifier(
    "pathfinding-obstacles", _classify_path("pathfinding-obstacles", obstacle=True)
)


# --- reverse-opening (divergence point + illegal sequences) -------------------


def _classify_reverse_opening(
    slug: str,
    detail: dict[str, Any],
    raw_answer: dict[str, Any],
    puzzle_answer: dict[str, Any],
    hints_used: list[str],
) -> list[MistakeDraft]:
    skill = tx.primary_skill(slug)
    answer = raw_answer if isinstance(raw_answer, dict) else {}
    raw_moves = answer.get("moves")
    if not isinstance(raw_moves, list) or not raw_moves:
        return [_no_response()]
    if any(not isinstance(m, str) for m in raw_moves):
        return [_malformed(skill, 1)]
    stored = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    start_fen = stored.get("start_fen")
    target_fen = stored.get("target_fen")
    raw_solutions = stored.get("solutions")
    canonical = (
        [m for m in raw_solutions[0] if isinstance(m, str)]
        if isinstance(raw_solutions, list) and raw_solutions and isinstance(raw_solutions[0], list)
        else []
    )
    if not isinstance(start_fen, str) or not isinstance(target_fen, str) or not canonical:
        return [_invalid_content("invalid-sequence-puzzle")]
    try:
        from app.modules.reverse_opening.validator import matched_plies, play_sequence

        play_sequence(start_fen, [m for m in raw_moves if isinstance(m, str)])
    except ValueError:
        # Deterministic replay hit a malformed/illegal move: illegal-sequence.
        return [_negative(tx.ILLEGAL_ACTION, "illegal-sequence", skill or slug)]
    except Exception:
        return [_unclassified(skill, "sequence-replay-failed")]
    matched = detail.get("matched_plies")
    expected_plies = detail.get("expected_plies") or len(canonical)
    if not isinstance(matched, int):
        try:
            from app.modules.reverse_opening.validator import matched_plies as _mp

            matched = _mp(canonical, [m for m in raw_moves if isinstance(m, str)])
        except Exception:
            return [_unclassified(skill, "sequence-replay-failed")]
    expected_len = expected_plies or len(canonical)
    specific = "early-divergence" if matched * 2 < expected_len else "late-divergence"
    return [
        _negative(
            tx.ILLEGAL_ACTION,
            specific,
            skill or slug,
            context={"matched_plies": matched, "expected_plies": expected_len},
        )
    ]


register_classifier("reverse-opening", _classify_reverse_opening)


# --- efficiency notes on correct solves ---------------------------------------


def _efficiency_note(
    slug: str,
    detail: dict[str, Any],
    skill: str | None,
) -> MistakeDraft | None:
    """Neutral inefficiency note for an otherwise correct attempt
    (positive-with-note: ability shown, fluency lacking)."""
    moves = detail.get("moves")
    optimal = detail.get("optimal_moves")
    if isinstance(moves, int) and isinstance(optimal, int) and moves > optimal:
        return MistakeDraft(
            direction=tx.DIRECTION_NEUTRAL,
            mistake_core=tx.INEFFICIENCY,
            mistake_specific=None,
            skill=skill,
            strength=tx.STRENGTH_WEAK,
            confidence=tx.CONFIDENCE_HIGH,
            context={"moves": moves, "optimal_moves": optimal},
        )
    used = detail.get("used_count")
    optimal_count = detail.get("optimal_count")
    if isinstance(used, int) and isinstance(optimal_count, int) and used > optimal_count:
        return MistakeDraft(
            direction=tx.DIRECTION_NEUTRAL,
            mistake_core=tx.INEFFICIENCY,
            mistake_specific="over-count",
            skill=skill,
            strength=tx.STRENGTH_WEAK,
            confidence=tx.CONFIDENCE_HIGH,
            context={"used_count": used, "optimal_count": optimal_count},
        )
    return None


# --- entry point --------------------------------------------------------------


def classify(
    *,
    exercise_slug: str,
    result: str,
    detail: dict[str, Any],
    raw_answer: dict[str, Any],
    puzzle_answer: dict[str, Any],
    hints_used: list[str],
) -> list[MistakeDraft]:
    """Turn one validation into mistake drafts. Total: never raises.

    Terminal client results bypass validation by design -> a single
    ``no-response`` draft. Correct results -> positive evidence
    (downgraded when scaffolded, annotated when inefficient).
    Everything else dispatches to the exercise classifier.
    """
    detail = dict(detail) if isinstance(detail, dict) else {}
    raw_answer = raw_answer if isinstance(raw_answer, dict) else {}
    puzzle_answer = puzzle_answer if isinstance(puzzle_answer, dict) else {}
    if isinstance(hints_used, list):
        hints_used = [h for h in hints_used if isinstance(h, str)]
    else:
        hints_used = []
    if result in TERMINAL_RESULTS:
        return [_no_response()]
    skill = tx.primary_skill(exercise_slug)
    if result == AttemptResult.CORRECT.value:
        drafts = [_positive(skill or exercise_slug, hints_used)]
        note = _efficiency_note(exercise_slug, detail, skill or exercise_slug)
        if note is not None:
            drafts.append(note)
        return drafts
    fn = get_classifier(exercise_slug)
    try:
        if fn is None:
            # Unknown exercise (registry also refuses these): honest neutral.
            return [_unclassified(exercise_slug, "no-classifier-for-exercise")]
        drafts = fn(exercise_slug, detail, raw_answer, puzzle_answer, hints_used)
    except Exception as exc:  # defensive: classification never breaks submits
        return [_unclassified(skill or exercise_slug, f"classifier-error:{type(exc).__name__}")]
    if not drafts:
        return [_unclassified(skill or exercise_slug, "classifier-emitted-nothing")]
    return drafts
