"""Record parser/validator for the official Lichess puzzle CSV.

Official columns (see https://database.lichess.org/, puzzle section)::

    PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,
    Themes,GameUrl,OpeningTags,DailyDate

The dump carries no header row; a header is tolerated (auto-detected)
so hand-made fixtures stay readable. Parsing is pure and streaming
friendly: one CSV row in, one normalized record or one error out. No
I/O, no database, no global state — uniqueness of ``PuzzleId`` is
enforced by the pipeline layer, which owns the run-scoped seen-set.

Lichess move semantics (documented on the source page): ``FEN`` is the
position *before* the opponent's move; presenting ``Moves[0]`` gives
the position shown to the player, and ``Moves[1:]`` is the solution.
The normalized record materializes both FENs so future importers never
re-derive them.
"""

from __future__ import annotations

import chess

HEADER_FIELDS = (
    "PuzzleId",
    "FEN",
    "Moves",
    "Rating",
    "RatingDeviation",
    "Popularity",
    "NbPlays",
    "Themes",
    "GameUrl",
    "OpeningTags",
    "DailyDate",
)

EXPECTED_COLUMNS = len(HEADER_FIELDS)

GAME_URL_PREFIX = "https://lichess.org/"

# Shared with the Phase 07 content rating bounds
# (app.modules.puzzles.validation.MIN_RATING/MAX_RATING).
MIN_RATING = 100
MAX_RATING = 3000
MIN_RATING_DEVIATION = 0
MAX_RATING_DEVIATION = 500
MIN_POPULARITY = -100
MAX_POPULARITY = 100


def is_header_row(cells: list[str]) -> bool:
    """True when the row is the optional human-readable header."""
    return len(cells) == EXPECTED_COLUMNS and [c.strip() for c in cells] == list(HEADER_FIELDS)


def split_tags(value: str) -> list[str]:
    """Space-separated Lichess tag list (Themes / OpeningTags)."""
    return [token for token in value.split() if token]


def _parse_int(value: str, *, field: str, minimum: int, maximum: int | None) -> int:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"{field} is empty")
    try:
        number = int(text)
    except ValueError:
        raise ValueError(f"{field} is not an integer: {text!r}") from None
    if number < minimum or (maximum is not None and number > maximum):
        raise ValueError(f"{field} out of range: {text!r}")
    return number


def validate_move_line(fen: str, moves_text: str) -> list[str]:
    """Validate the full UCI solution line against the FEN.

    Every move must parse as UCI and be legal in sequence starting from
    ``fen``. Returns the cleaned UCI tokens. Raises ``ValueError`` with
    a stable message otherwise.
    """
    try:
        board = chess.Board(fen.strip())
    except ValueError:
        raise ValueError("FEN is not parseable by python-chess") from None
    tokens = moves_text.split()
    if not tokens:
        raise ValueError("Moves is empty")
    for token in tokens:
        try:
            move = chess.Move.from_uci(token.strip())
        except ValueError:
            raise ValueError(f"move is not valid UCI: {token!r}") from None
        if move not in board.legal_moves:
            raise ValueError(f"move is illegal in sequence: {token!r}")
        board.push(move)
    return [t.strip() for t in tokens]


def derive_presented_fen(fen: str, opponent_move_uci: str) -> str:
    """FEN shown to the player: ``fen`` with the opponent move applied."""
    board = chess.Board(fen.strip())
    board.push(chess.Move.from_uci(opponent_move_uci))
    return board.fen()


def parse_row(cells: list[str]) -> tuple[dict | None, dict | None]:
    """Parse and validate one CSV row.

    Returns ``(normalized, None)`` on success or ``(None, error)`` on
    failure, where ``error`` is ``{"code", "detail"}``. Never raises for
    data problems (only for programmer errors such as a wrong arity
    type); malformed rows are reported, never fatal.
    """
    if len(cells) != EXPECTED_COLUMNS:
        return None, {
            "code": "bad_column_count",
            "detail": f"expected {EXPECTED_COLUMNS} columns, got {len(cells)}",
        }
    (
        puzzle_id,
        fen,
        moves_text,
        rating_text,
        deviation_text,
        popularity_text,
        nb_plays_text,
        themes_text,
        game_url,
        opening_tags_text,
        daily_date_text,
    ) = [c or "" for c in cells]

    puzzle_id = puzzle_id.strip()
    if not puzzle_id or any(ch.isspace() for ch in puzzle_id):
        return None, {"code": "bad_puzzle_id", "detail": "PuzzleId is empty or contains whitespace"}

    fen = fen.strip()
    if not fen:
        return None, {"code": "bad_fen", "detail": "FEN is empty"}
    try:
        chess.Board(fen)
    except ValueError:
        return None, {"code": "bad_fen", "detail": "FEN is not parseable by python-chess"}

    try:
        moves = validate_move_line(fen, moves_text)
    except ValueError as exc:
        return None, {"code": "bad_moves", "detail": str(exc)}

    try:
        rating = _parse_int(rating_text, field="Rating", minimum=MIN_RATING, maximum=MAX_RATING)
        rating_deviation = _parse_int(
            deviation_text, field="RatingDeviation",
            minimum=MIN_RATING_DEVIATION, maximum=MAX_RATING_DEVIATION,
        )
        popularity = _parse_int(
            popularity_text, field="Popularity",
            minimum=MIN_POPULARITY, maximum=MAX_POPULARITY,
        )
        nb_plays = _parse_int(nb_plays_text, field="NbPlays", minimum=0, maximum=None)
    except ValueError as exc:
        return None, {"code": "bad_numeric_field", "detail": str(exc)}

    themes = split_tags(themes_text)
    if not themes:
        return None, {"code": "bad_themes", "detail": "Themes is empty"}

    game_url = game_url.strip()
    if not game_url.startswith(GAME_URL_PREFIX):
        return None, {"code": "bad_game_url", "detail": "GameUrl must start with https://lichess.org/"}

    opening_tags = split_tags(opening_tags_text)

    daily_text = (daily_date_text or "").strip()
    daily_date_ms: int | None = None
    if daily_text:
        try:
            daily_date_ms = _parse_int(daily_text, field="DailyDate", minimum=0, maximum=None)
        except ValueError as exc:
            return None, {"code": "bad_daily_date", "detail": str(exc)}

    opponent_move = moves[0]
    try:
        presented = derive_presented_fen(fen, opponent_move)
    except ValueError:  # pragma: no cover - validated above; defensive only
        return None, {"code": "bad_moves", "detail": "first move cannot be applied to FEN"}

    return {
        "puzzle_id": puzzle_id,
        "fen_initial": fen,
        "fen_presented": presented,
        "opponent_move_uci": opponent_move,
        "solution_uci": moves[1:],
        "rating": rating,
        "rating_deviation": rating_deviation,
        "popularity": popularity,
        "nb_plays": nb_plays,
        "themes": themes,
        "game_url": game_url,
        "opening_tags": opening_tags,
        "daily_date_ms": daily_date_ms,
        "source": "lichess",
        "source_reference": puzzle_id,
    }, None
