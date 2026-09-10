# Exercise 9 — Balance Scale (ترازو)

A dedicated visual exercise with NO chessboard, NO FEN, NO legal moves,
NO kings, and NO captures. The child sees a large tilting balance scale:
black pieces on one pan (the immutable target), an unlimited inventory of
white pieces, and an empty 10-slot right pan to fill.

Goal: add white pieces until both pans hold exactly the same material
value — using as FEW pieces as possible.

## Piece values

Pawn 1, Knight 3, Bishop 3, Rook 5, Queen 9. No king exists here.

## Puzzle model

- Left pan: 4–10 random black pieces (`position_json: {"left": [...]}`).
- `answer_json: {"left": [...], "target": int, "optimal_count": int}`
  is server-only; puzzle endpoints never expose it. The frontend renders
  only the left pieces; `optimal_count` is never revealed before solving.
- `Puzzle.fen` is NULL (nothing to render as a board).

## Generator (`balance_scale/generator.py`)

Random composition (pawn-weighted pool, count uniform in 4–10), then
generate → solve → validate → accept:

1. Recompute the target from the left pieces.
2. Solve the minimum piece count with exact DP over [1, 3, 5, 9]
   (`balance_scale/solver.py` — no lookup tables).
3. Accept only when `optimal_count <= 10` (matchable in the 10-slot pan).
4. Tier mixing (low 4–15 / medium 16–35 / high 36–90) plus throttling of
   1-piece optimals keeps low/medium/high targets, multi-piece solutions,
   heavy-optimal and light-optimal cases, and multi-solution targets
   (e.g. 10 = 9+1 or 5+5).

Note: with the 4-piece left minimum, single-piece optimals (targets
9/5/3/1) cannot be generated; every puzzle needs ≥ 2 white pieces.
The 90 ceiling (10 black queens) is matched by 10 white queens.

## Validation (`balance_scale/validator.py`)

Attempt: `{"pieces": [...]}` (the placed white pieces). CORRECT iff every
piece is valid, at most 10 were placed, and the submitted total EQUALS the
stored target (recomputed server-side; client target/optimal/score fields
are ignored). Under/over/invalid/>10/malformed input is WRONG.
ANY exact combination solves — no hard-coded answer.
Legacy bank/right rows from the earlier prototype keep their original
subset-sum rule so old databases still grade.

## Scoring (`balance_scale/scoring.py`, registered scorer)

`score = max(0, 10 - (used - optimal))` on CORRECT, 0 on WRONG.
Optimal solution scores 10, each extra piece costs 1, floor 0 (never
negative). Experimenting before balance is free: only the balanced state
is graded.

## Interaction (frontend)

- Tap inventory piece → add one white copy (unlimited stock, 10-slot cap).
- Tap a white piece on the pan → remove it. Black pieces are immutable.
- Full pan: subtle capacity message, never a wrong answer, never scored.
- NO Submit button: exact balance auto-submits one attempt immediately,
  plays the shared success sound, and locks the pan.
- Practice: success card shows the score plus «معمای بعدی»; the child
  advances explicitly (no auto-advance).
- Speed: standard 60s session lifecycle (open → prepare ≥20 → start clock
  → submit loop with ~500ms auto-advance → server-rebuilt report).
  Per-answer rows reuse `attempts` (mode=practice, `rating_delta` None).

## Scale visual (`BalanceScaleView.tsx` + `BalanceScalePlay.tsx`)

- One rotating assembly (beam + both hanging pans + pieces) over a static
  stand, so pieces stay attached while tilting; smooth 500ms ease-out.
- Tilt: `angle = 25° · diff / (|diff| + 8)` — 0 when balanced, signed by
  the heavier side, asymptotically bounded, never clipping (headroom above
  the pivot, `overflow-x: clip`, responsive shrink).
- Pyramid 1+2+3+4 slots per pan; pieces sorted heavy-first so the heaviest
  sit on the bottom row; stable uids (no reshuffle jumps).
- SVG pieces only (no glyphs); live totals سیاه/سفید; totals card turns
  green on balance. `motion-safe:` transitions respect
  `prefers-reduced-motion`. Pan pieces are board-density targets (like
  chess squares); inventory buttons are ≥56px touch targets.
