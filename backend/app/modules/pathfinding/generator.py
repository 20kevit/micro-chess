"""Deterministic pathfinding puzzle generator.

Puzzles are built from hand-designed templates (covering all six piece
types and the required situation variety) and every template is proven
solvable by breadth-first search before it is accepted. Generation is fully
deterministic: the same code always yields the same 15 puzzles.

The BFS solver searches (position × captured-set) states using the same
single-step rule as the validator (`iter_moves`). Independent test
recomputation with raw python-chess guards against shared bugs.
"""

from collections import deque

import chess

from app.modules.pathfinding.validator import iter_moves, mover_color

# Each template: piece kind (for distribution checks), start, target,
# full FEN, minimum accepted shortest-path length in moves, prompt,
# explanation, hints, rating.
TEMPLATES: list[dict] = [
    {
        "kind": "knight",
        "start": "b1",
        "target": "d2",
        "fen": "k5r1/8/8/8/8/8/8/1N5K w - - 0 1",
        "min_moves": 1,
        "explanation": "اسب از b1 مستقیم به d2 می‌پرد؛ راه ساده و یک‌حرکتی.",
        "hints": [{"id": "h1", "text_fa": "حرکت اسب به شکل L است.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "kind": "knight",
        "start": "e4",
        "target": "g5",
        "fen": "k5r1/8/5p2/8/4N3/8/8/7K w - - 0 1",
        "min_moves": 5,
        "explanation": "سرباز f6 خانه g5 را کنترل می‌کند؛ اسب اول آن را می‌زند و بعد با چند حرکت به g5 می‌رسد.",
        "hints": [{"id": "h1", "text_fa": "اول مهره‌ای که راه را بسته بزن.", "rating_cost": 10}],
        "rating": 1100.0,
    },
    {
        "kind": "knight",
        "start": "d4",
        "target": "e6",
        "fen": "k7/8/4p3/8/3N4/8/8/7K w - - 0 1",
        "min_moves": 1,
        "explanation": "اسب d4 سرباز e6 را می‌زند و همان‌جا می‌ماند.",
        "hints": [{"id": "h1", "text_fa": "زدن مهره دشمن هم یک حرکت قانونی است.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "kind": "rook",
        "start": "a1",
        "target": "a8",
        "fen": "7k/8/8/8/8/8/8/R6K w - - 0 1",
        "min_moves": 1,
        "explanation": "ستون a کاملاً باز است؛ رخ مستقیم به a8 می‌رود.",
        "hints": [{"id": "h1", "text_fa": "رخ در ستون و ردیف خالی مستقیم می‌رود.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "kind": "rook",
        "start": "a1",
        "target": "g1",
        "fen": "k7/8/8/8/8/8/7K/R3p3 w - - 0 1",
        "min_moves": 2,
        "explanation": "سرباز e1 راه را بسته؛ رخ اول آن را می‌زند و بعد به g1 می‌رود.",
        "hints": [{"id": "h1", "text_fa": "زدن مهره مسیر را باز می‌کند.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "kind": "rook",
        "start": "a1",
        "target": "h1",
        "fen": "k7/8/8/8/8/8/2p1p3/R5K1 w - - 0 1",
        "min_moves": 3,
        "explanation": "سربازهای c2 و e2 ردیف اول را کنترل می‌کنند؛ رخ از ستون a بالا می‌رود و از دور می‌چرخد.",
        "hints": [{"id": "h1", "text_fa": "اگر راه مستقیم خطرناک است، دور بزن.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "kind": "bishop",
        "start": "c1",
        "target": "h6",
        "fen": "k7/8/8/4p3/8/8/8/2B3K1 w - - 0 1",
        "min_moves": 1,
        "explanation": "قطر c1 تا h6 کاملاً باز است.",
        "hints": [{"id": "h1", "text_fa": "فیل فقط روی قطر خودش حرکت می‌کند.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "kind": "bishop",
        "start": "c1",
        "target": "e3",
        "fen": "k7/8/8/8/8/8/3p4/2B4K w - - 0 1",
        "min_moves": 2,
        "explanation": "سرباز d2 راه قطر را بسته؛ فیل اول آن را می‌زند و بعد به e3 می‌رود.",
        "hints": [{"id": "h1", "text_fa": "مهره‌ای که راه را بسته بزن.", "rating_cost": 5}],
        "rating": 900.0,
    },
    {
        "kind": "queen",
        "start": "d1",
        "target": "h5",
        "fen": "k7/8/8/8/8/8/8/3Q2K1 w - - 0 1",
        "min_moves": 1,
        "explanation": "وزیر مستقیم از قطر به h5 می‌رود.",
        "hints": [{"id": "h1", "text_fa": "وزیر هم مثل رخ و هم مثل فیل حرکت می‌کند.", "rating_cost": 5}],
        "rating": 750.0,
    },
    {
        "kind": "queen",
        "start": "d4",
        "target": "d8",
        "fen": "k7/8/3p4/8/3Q4/8/8/6K1 w - - 0 1",
        "min_moves": 2,
        "explanation": "سرباز d6 ستون را بسته؛ وزیر از راه دیگر (مثلاً h8) به d8 می‌رسد.",
        "hints": [{"id": "h1", "text_fa": "وقتی ستون بسته است، از عرض یا قطر برو.", "rating_cost": 10}],
        "rating": 950.0,
    },
    {
        "kind": "king",
        "start": "e1",
        "target": "g3",
        "fen": "k7/8/8/8/3b4/8/8/4K3 w - - 0 1",
        "min_moves": 3,
        "explanation": "فیل d4 خانه‌های f2 و e3 را کنترل می‌کند؛ شاه با احتیاط و قدم‌به‌قدم جلو می‌رود.",
        "hints": [{"id": "h1", "text_fa": "شاه هیچ‌وقت وارد خانه زیر ضربه نمی‌شود.", "rating_cost": 10}],
        "rating": 1000.0,
    },
    {
        "kind": "king",
        "start": "e1",
        "target": "d2",
        "fen": "k7/8/8/8/8/8/3p4/4K3 w - - 0 1",
        "min_moves": 1,
        "explanation": "شاه سرباز بی‌دفاع d2 را می‌زند.",
        "hints": [{"id": "h1", "text_fa": "زدن مهره بی‌دفاع با شاه مجاز است.", "rating_cost": 5}],
        "rating": 800.0,
    },
    {
        "kind": "pawn",
        "start": "e2",
        "target": "e4",
        "fen": "k7/8/8/8/8/8/4P3/7K w - - 0 1",
        "min_moves": 1,
        "explanation": "سرباز از خانه اول مستقیم دو خانه جلو می‌رود؛ راه کاملاً امن است.",
        "hints": [{"id": "h1", "text_fa": "سرباز از خانه اول می‌تواند دو خانه برود.", "rating_cost": 5}],
        "rating": 700.0,
    },
    {
        "kind": "pawn",
        "start": "e4",
        "target": "d6",
        "fen": "k7/8/8/3p1p2/4P3/8/8/7K w - - 0 1",
        "min_moves": 2,
        "explanation": "سرباز e4 سرباز d5 را می‌زند و بعد یک خانه جلو می‌رود.",
        "hints": [{"id": "h1", "text_fa": "سرباز فقط مورب می‌زند.", "rating_cost": 5}],
        "rating": 850.0,
    },
    {
        "kind": "pawn",
        "start": "e3",
        "target": "d5",
        "fen": "k7/8/8/8/3p4/4P3/8/7K w - - 0 1",
        "min_moves": 2,
        "explanation": "سرباز سیاه e4 راه مستقیم را بسته؛ باید اول d4 را زد و بعد جلو رفت.",
        "hints": [{"id": "h1", "text_fa": "اگر جلو بسته است، مورب را بررسی کن.", "rating_cost": 10}],
        "rating": 950.0,
    },
]

PROMPT_FA = "مهره‌ی مشخص‌شده را قدم‌به‌قدم به خانه‌ی ستاره‌دار برسان."


def solve(fen: str, start: str, target: str, max_depth: int = 12) -> list[str] | None:
    """Shortest valid path from start to target, or None when unreachable.

    Breadth-first search over (position × captured-set) states. This is the
    independent solvability proof used at generation time.
    """
    mover = mover_color(fen, start)
    queue: deque[tuple[str, str, list[str], frozenset]] = deque([(fen, start, [start], frozenset())])
    seen = {(start, frozenset())}
    while queue:
        cur_fen, pos, path, captured = queue.popleft()
        if pos == target:
            return path
        if len(path) - 1 >= max_depth:
            continue
        for dest, new_fen, taken in iter_moves(cur_fen, mover, pos):
            new_captured = captured | ({taken} if taken else set())
            key = (dest, frozenset(new_captured))
            if key in seen:
                continue
            seen.add(key)
            queue.append((new_fen, dest, path + [dest], new_captured))
    return None


def generate_all() -> list[dict]:
    """Build and verify all pathfinding puzzles. Raises on any failure."""
    puzzles = []
    for item in TEMPLATES:
        board = chess.Board(item["fen"])  # raises on invalid FEN
        if board.piece_at(chess.parse_square(item["start"])) is None:
            raise ValueError(f"no selected piece: {item['fen']} {item['start']}")
        path = solve(item["fen"], item["start"], item["target"])
        if path is None:
            raise ValueError(f"unsolvable template: {item['fen']} {item['start']}->{item['target']}")
        if len(path) - 1 < item["min_moves"]:
            raise ValueError(f"path too short ({len(path) - 1} moves): {item['fen']}")
        puzzles.append(
            {
                "fen": item["fen"],
                "from": item["start"],
                "target": item["target"],
                "kind": item["kind"],
                "prompt_fa": PROMPT_FA,
                "explanation": item["explanation"],
                "hints": item["hints"],
                "rating": item["rating"],
                "shortest_moves": len(path) - 1,
            }
        )
    kinds = sorted({p["kind"] for p in puzzles})
    if kinds != ["bishop", "king", "knight", "pawn", "queen", "rook"]:
        raise ValueError(f"piece distribution incomplete: {kinds}")
    return puzzles
