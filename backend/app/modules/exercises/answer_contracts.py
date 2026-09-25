"""Typed answer contracts for admin content authoring (Phase 12).

Derived from the real exercise validators (``app/modules/<slug>/validator.py``):
each exercise slug maps to exactly one answer contract describing

* the canonical ``answer_json`` shape the validator reads,
* the attempt field the player client submits,
* whether the expected answer is derived from a stored FEN
  (``fen_derived``: correctness is recomputed server-side from the
  position, the admin only authors the position) or stored explicitly.

The admin frontend renders one answer editor per contract type instead
of forcing every exercise into a single answer UI. Adding a new
exercise means adding one entry here next to its validator — never a
second validation engine.
"""

from __future__ import annotations

from typing import Any

# Contract types (stable strings consumed by the admin frontend).
SQUARES = "squares"  # multi-square select: {"squares": [...]}
MOVES = "moves"  # multi-move select (UCI): {"moves": [...]}
SINGLE_MOVE = "single_move"  # one tactical/best move: {"move": "Nf3"}
MOVE_SEQUENCE = "move_sequence"  # ordered UCI replay: {"moves": [...]}
ORDERED_SQUARES = "ordered_squares"  # ordered square tuple (pin triplet)
SINGLE_SQUARE = "single_square"  # one square: {"square": "e4"}
SQUARE_OR_COLOR = "square_or_color"  # square tap or white/black choice
CHOICE = "choice"  # fixed option list: {"choice": "..."}
OPTIONS = "options"  # multi-option select: {"options": [...]}
PATH = "path"  # square path: {"path": [...]}
PLACEMENTS = "placements"  # piece reconstruction: {"pieces": [...]}
PIECES = "pieces"  # piece set: {"pieces": [...]}

CONTRACT_TYPES = (
    SQUARES,
    MOVES,
    SINGLE_MOVE,
    MOVE_SEQUENCE,
    ORDERED_SQUARES,
    SINGLE_SQUARE,
    SQUARE_OR_COLOR,
    CHOICE,
    OPTIONS,
    PATH,
    PLACEMENTS,
    PIECES,
)


def _contract(
    *,
    answer_type: str,
    answer_fields: list[dict[str, Any]],
    attempt_field: str,
    fen_derived: bool = False,
    needs_board: bool = True,
    position_fields: list[dict[str, Any]] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "answer_type": answer_type,
        "answer_fields": answer_fields,
        "attempt_field": attempt_field,
        "fen_derived": fen_derived,
        "needs_board": needs_board,
        "position_fields": position_fields or [],
        "notes": notes,
    }


def _string_list_field(name: str, description: str, item_hint: str = "") -> dict[str, Any]:
    return {"name": name, "kind": "string_list", "description": description, "item_hint": item_hint}


def _string_field(name: str, description: str, hint: str = "") -> dict[str, Any]:
    return {"name": name, "kind": "string", "description": description, "item_hint": hint}


def _fen_position_fields(mode: str) -> list[dict[str, Any]]:
    return [
        _string_field("fen", "Visible position", "FEN"),
        _string_field("mode", "Playback mode", mode),
    ]


# Canonical contracts, one per exercise validator. ``answer_fields``
# mirrors exactly what each validator reads from ``answer_json``.
_CONTRACTS: dict[str, dict[str, Any]] = {
    "piece-recognition": _contract(
        answer_type=SQUARES,
        answer_fields=[
            _string_list_field("squares", "Squares holding the target pieces", "e.g. a2"),
            _string_field("target", "Target key, e.g. white-pawn", "white-pawn"),
        ],
        attempt_field="selected_squares",
        position_fields=[_string_field("target", "Target key shown to the player", "white-pawn")],
        notes="Exact set match. Empty selection is correct for zero-target positions.",
    ),
    "legal-destinations": _contract(
        answer_type=SQUARES,
        answer_fields=[
            _string_list_field("squares", "All legal destination squares", "e.g. e6"),
            _string_field("from", "Hunter square", "e.g. d4"),
            _string_field("profile", "Rule profile: standard | ignore-enemy-attacks", "standard"),
        ],
        attempt_field="selected_squares",
        position_fields=[
            _string_field("from", "Hunter square (visible task)", "e.g. d4"),
            _string_field("profile", "Rule profile", "standard"),
        ],
        notes="Destinations should be computed from the position, not invented.",
    ),
    "captures": _contract(
        answer_type=SQUARES,
        answer_fields=[
            _string_list_field("squares", "Every capturable enemy square", "e.g. d5"),
            _string_field("from", "Hunter square", "e.g. e4"),
            _string_field("profile", "Rule profile: standard | ignore-enemy-attacks", ""),
        ],
        attempt_field="selected_squares",
        position_fields=[
            _string_field("from", "Hunter square (visible task)", "e.g. e4"),
            _string_field("profile", "Rule profile", "ignore-enemy-attacks"),
        ],
    ),
    "undefended-pieces": _contract(
        answer_type=SQUARES,
        answer_fields=[_string_list_field("squares", "Undefended piece squares", "e.g. c4")],
        attempt_field="selected_squares",
        position_fields=_fen_position_fields("standard"),
    ),
    "trapped-pieces": _contract(
        answer_type=SQUARES,
        answer_fields=[_string_list_field("squares", "Trapped piece squares", "e.g. h6")],
        attempt_field="selected_squares",
        position_fields=_fen_position_fields("standard"),
    ),
    "give-check": _contract(
        answer_type=MOVES,
        answer_fields=[_string_list_field("moves", "Every checking move (UCI)", "e.g. e2e4")],
        attempt_field="moves",
        position_fields=_fen_position_fields("standard"),
        notes="Union over both colors. Kings never give check. Each promotion choice is distinct.",
    ),
    "get-out-of-check": _contract(
        answer_type=MOVES,
        answer_fields=[_string_field("fen", "Position with side to move in check", "FEN")],
        attempt_field="moves",
        fen_derived=True,
        position_fields=[_string_field("fen", "Visible check position", "FEN")],
        notes="Expected escapes are recomputed from the FEN. The side to move must start in check.",
    ),
    "pin": _contract(
        answer_type=ORDERED_SQUARES,
        answer_fields=[
            _string_field("fen", "Position containing exactly one pin", "FEN"),
            _string_list_field(
                "pin", "Pin triplet in order: pinner, pinned, behind", "e.g. e8, e6, e1"
            ),
        ],
        attempt_field="squares",
        fen_derived=True,
        position_fields=[_string_field("fen", "Visible pinned position", "FEN")],
        notes="Skewers are rejected. Order matters: pinner, pinned, behind.",
    ),
    "is-checkmate": _contract(
        answer_type=CHOICE,
        answer_fields=[_string_field("fen", "Position to classify", "FEN")],
        attempt_field="choice",
        fen_derived=True,
        position_fields=_fen_position_fields("classify"),
        notes="Choice is derived: checkmate | check | not_check. Both kings required.",
    ),
    "castling-rights": _contract(
        answer_type=OPTIONS,
        answer_fields=[
            {
                "name": "options",
                "kind": "option_list",
                "description": "Legal castling options",
                "options": [
                    "white_kingside",
                    "white_queenside",
                    "black_kingside",
                    "black_queenside",
                ],
            }
        ],
        attempt_field="options",
        position_fields=_fen_position_fields("castling"),
        notes="Empty selection is correct when no castling is legal.",
    ),
    "blindfold-square-vision": _contract(
        answer_type=SQUARE_OR_COLOR,
        answer_fields=[_string_field("square", "Target square (color is derived)", "e.g. d5")],
        attempt_field="square | choice",
        needs_board=False,
        position_fields=[
            _string_field("square", "Target square shown to the player", "e.g. d5"),
            _string_field("mode", "Playback mode", "standard"),
        ],
        notes="Colors are never stored: a1 is dark. Practice taps, speed picks white/black.",
    ),
    "blindfold-calculation": _contract(
        answer_type=SINGLE_MOVE,
        answer_fields=[
            _string_field("fen", "Hidden position", "FEN"),
            _string_field("solution", "Best move (UCI)", "e.g. g1f3"),
        ],
        attempt_field="move",
        needs_board=False,
        position_fields=[
            _string_field("description_fa", "Persian description shown instead of a board", "Position description"),
            _string_field("side_to_move", "Side to move: w | b", "w"),
            _string_field("mode", "Playback mode", "best-move"),
            {"name": "piece_count", "kind": "integer", "description": "Number of pieces"},
        ],
        notes="Player submits SAN; the server normalizes to UCI and compares.",
    ),
    "opening-traps": _contract(
        answer_type=SINGLE_MOVE,
        answer_fields=[
            _string_field("fen", "Trap position", "FEN"),
            _string_list_field("solutions", "Accepted tactical moves (UCI)", "e.g. f3e5"),
            _string_field("theme", "Tactical theme, e.g. FORK", "FORK"),
        ],
        attempt_field="move",
        needs_board=False,
        position_fields=[
            _string_field("description_fa", "Persian position description", "Position description"),
            _string_field("side_to_move", "Side to move: w | b", "w"),
            _string_field("mode", "Playback mode", "tactic-1"),
            _string_field("opening_fa", "Persian opening name", "Opening"),
            _string_field("trap_fa", "Persian tactical trap description", "Trap"),
            _string_field("theme_fa", "Persian tactical theme", "Theme"),
        ],
        notes="Several winning moves may be accepted. Checkmate is not required.",
    ),
    "reverse-opening": _contract(
        answer_type=MOVE_SEQUENCE,
        answer_fields=[
            _string_field("start_fen", "Start position", "FEN"),
            _string_field("target_fen", "Target position to rebuild", "FEN"),
            {
                "name": "solutions",
                "kind": "move_sequence_list",
                "description": "Canonical sequences (UCI); any order reaching the target counts",
                "item_hint": "e.g. e2e4, e7e5, g1f3",
            },
        ],
        attempt_field="moves",
        position_fields=[
            _string_field("start_fen", "Visible starting position", "FEN"),
            _string_field("target_fen", "Visible target position", "FEN"),
            _string_field("mode", "Playback mode", "reconstruct"),
            _string_field("opening_fa", "Persian opening name", "Opening"),
            _string_field("description_fa", "Persian reconstruction description", "Description"),
        ],
        notes="Correctness is positional (placement + turn + castling + en passant).",
    ),
    "pathfinding": _contract(
        answer_type=PATH,
        answer_fields=[
            _string_field("from", "Start square", "e.g. a1"),
            _string_field("target", "Target square", "e.g. h8"),
            _string_field("piece", "Piece kind", "e.g. knight"),
            {"name": "optimal_moves", "kind": "integer", "description": "Optimal move count"},
        ],
        attempt_field="path",
        position_fields=[
            _string_field("from", "Start square", "e.g. a1"),
            _string_field("target", "Target square", "e.g. h8"),
            _string_field("piece", "Piece kind", "e.g. knight"),
        ],
    ),
    "pathfinding-obstacles": _contract(
        answer_type=PATH,
        answer_fields=[
            _string_field("from", "Start square", "e.g. a1"),
            _string_field("target", "Target square", "e.g. h8"),
            _string_field("piece", "Piece kind", "e.g. knight"),
            {
                "name": "enemies",
                "kind": "enemy_list",
                "description": "Enemy pieces as square/kind objects",
            },
            {"name": "optimal_moves", "kind": "integer", "description": "Optimal move count"},
        ],
        attempt_field="path",
        position_fields=[
            _string_field("from", "Start square", "e.g. a1"),
            _string_field("target", "Target square", "e.g. h8"),
            _string_field("piece", "Piece kind", "e.g. knight"),
            {
                "name": "enemies",
                "kind": "enemy_list",
                "description": "Enemy pieces as square/kind objects",
            },
        ],
    ),
    "chinese-board": _contract(
        answer_type=PLACEMENTS,
        answer_fields=[_string_field("fen", "Position to memorize and rebuild", "FEN")],
        attempt_field="pieces",
        fen_derived=True,
        position_fields=[
            _string_field("fen", "Visible position", "FEN"),
            {"name": "piece_count", "kind": "integer", "description": "Number of pieces"},
            {"name": "memorization_ms", "kind": "integer", "description": "Study budget in milliseconds"},
            _string_field("mode", "Playback mode", "standard"),
        ],
        notes="Player rebuilds placements [{color, piece, square}].",
    ),
    "heavier-side": _contract(
        answer_type=CHOICE,
        answer_fields=[_string_field("fen", "Position to compare", "FEN")],
        attempt_field="choice",
        fen_derived=True,
        position_fields=[
            _string_field("fen", "Visible position", "FEN"),
            _string_field("mode", "Comparison mode", "standard"),
        ],
        notes="The white/black/equal answer is derived from material totals in the FEN.",
    ),
    "balance-scale": _contract(
        answer_type=PIECES,
        answer_fields=[
            _string_list_field("left", "Black pieces already on the left pan", "e.g. N"),
        ],
        attempt_field="pieces",
        position_fields=[_string_list_field("left", "Visible black pieces", "e.g. N")],
        notes="The target and optimal count are recomputed from the visible left pieces.",
    ),
}


def answer_contract_for(slug: str) -> dict[str, Any] | None:
    """Typed answer contract for an exercise, or None when unknown."""
    contract = _CONTRACTS.get(slug)
    if contract is None:
        return None
    return {"exercise_slug": slug, **contract}


def known_answer_slugs() -> list[str]:
    return sorted(_CONTRACTS)


def contract_answer_type(slug: str) -> str | None:
    contract = _CONTRACTS.get(slug)
    return contract["answer_type"] if contract else None


def validate_contract_shape(
    contract: dict[str, Any],
    *,
    answer: dict[str, Any],
    position: dict[str, Any],
    fen: str | None,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    fields = contract.get("answer_fields") or []
    for field in fields:
        name = str(field.get("name") or "")
        kind = str(field.get("kind") or "string")
        if name not in answer:
            errors.append({"code": "answer_field_missing", "detail": name})
            continue
        value = answer.get(name)
        valid = True
        if kind == "string":
            valid = isinstance(value, str) and bool(value.strip())
        elif kind == "string_list":
            valid = isinstance(value, list) and all(isinstance(item, str) for item in value)
        elif kind == "option_list":
            valid = isinstance(value, list) and all(isinstance(item, str) for item in value)
        elif kind == "integer":
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif kind == "move_sequence_list":
            valid = isinstance(value, list) and bool(value) and all(
                isinstance(sequence, list)
                and bool(sequence)
                and all(isinstance(move, str) for move in sequence)
                for sequence in value
            )
        elif kind == "placement_list":
            valid = isinstance(value, list)
        elif kind == "enemy_list":
            valid = isinstance(value, list) and all(
                isinstance(item, dict)
                and isinstance(item.get("square"), str)
                and isinstance(item.get("kind"), str)
                for item in value
            )
        if not valid:
            errors.append({"code": "answer_field_invalid", "detail": name})
    for field in contract.get("position_fields") or []:
        name = str(field.get("name") or "")
        if name in AUTO_POSITION_NAMES and name in answer:
            continue
        if name not in position:
            errors.append({"code": "position_field_missing", "detail": name})
    if contract.get("needs_board"):
        if not fen:
            errors.append({"code": "position_fen_missing", "detail": "fen"})
        elif isinstance(answer.get("fen"), str) and answer["fen"] != fen:
            errors.append({"code": "fen_answer_mismatch", "detail": "fen"})
    return errors


AUTO_POSITION_NAMES = frozenset(
    {
        "fen",
        "start_fen",
        "target_fen",
        "from",
        "target",
        "piece",
        "enemies",
        "left",
        "side_to_move",
        "piece_count",
        "memorization_ms",
    }
)


def canonical_attempt(contract: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any] | None:
    kind = contract.get("answer_type")
    if kind == SQUARES:
        return {"selected_squares": answer.get("squares")}
    if kind == MOVES:
        return {"moves": answer.get("moves")}
    if kind == SINGLE_MOVE:
        if isinstance(answer.get("solution"), str):
            return {"move": answer["solution"]}
        solutions = answer.get("solutions")
        if isinstance(solutions, list) and solutions and isinstance(solutions[0], str):
            return {"move": solutions[0]}
        return None
    if kind == MOVE_SEQUENCE:
        solutions = answer.get("solutions")
        if isinstance(solutions, list) and solutions and isinstance(solutions[0], list):
            return {"moves": solutions[0]}
        return None
    if kind == ORDERED_SQUARES:
        return {"squares": answer.get("pin")}
    if kind == SINGLE_SQUARE:
        return {"square": answer.get("square")}
    if kind == SQUARE_OR_COLOR:
        return {"square": answer.get("square")}
    if kind == CHOICE:
        return {"choice": answer.get("choice")} if "choice" in answer else None
    if kind == OPTIONS:
        return {"options": answer.get("options")}
    return None
