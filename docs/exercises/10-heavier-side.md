# Exercise 10 — Heavier Side (کدام طرف سنگین‌تر است؟)

Train quick material evaluation on real chess positions.

## Purpose

The player sees a real chess position and answers which side is ahead
**on material only**:

- سفید (White is ahead)
- سیاه (Black is ahead)
- مساوی (Equal material)

No positional judgment: king safety, initiative, pawn structure,
development, activity, tactics, and engine evaluation are all irrelevant.
A position can be strategically winning for one side yet count as مساوی
here when the material is equal.

## Piece values

| Piece  | Value |
| ------ | ----: |
| Pawn   |     1 |
| Knight |     3 |
| Bishop |     3 |
| Rook   |     5 |
| Queen  |     9 |
| King   |     0 |

Kings contribute zero (effectively excluded). Totals are computed
separately for White and Black from the displayed board via python-chess:

```text
white_material > black_material → WHITE
black_material > white_material → BLACK
otherwise                        → EQUAL
```

The 0-vs-0 case (kings only) classifies as EQUAL.

## Puzzle source

Real positions from the shared `puzzles.db` (FEN only; Moves/Rating/Themes
ignored), served through `positions/repository.py` (indexed rowid probing;
the table is never loaded into memory). The stored FEN is used exactly as
exposed — no solution moves are applied. The material calculation always
runs on the exact board state shown to the user.

## The 10% difficulty constraint

Every served puzzle satisfies:

```text
difference = abs(white - black)
larger = max(white, black)
eligible <=> larger == 0 OR difference / larger <= 0.10
```

No rounding before comparison: 30 vs 27 is accepted, 30 vs 26 rejected.
The generator uses bounded rejection sampling (up to 40 candidates per
puzzle, ~73% acceptance on the real database) targeting a uniform desired
category (white / black / equal) per puzzle, falling back to the first
eligible candidate — yielding roughly balanced answer categories over
time without bias toward trivial positions.

## Answer categories

Approximately White ahead ~33% / Black ahead ~33% / Equal ~33% over time
(exact split not guaranteed; bounded sampling keeps it healthy). Inside
the 10% band, equal, tiny, and moderate differences (e.g. 50/50, 40/39,
30/28, 20/19) all occur; 30/25 never appears.

## Scoring

Registered scorer: CORRECT = +5, WRONG = −2 (negatives kept). No partial
credit; malformed input is WRONG.

## Server authority

- Client sends only `{choice}` plus the puzzle/session id. Client totals,
  scores, and FENs are ignored.
- The server loads the stored FEN, recomputes material, grades, and scores.
- Active-puzzle APIs (`/next`, session buffers, `PuzzleOut`) never expose
  the verdict, totals, or `answer_json`.

## Practice mode

Untimed. Current + next prefetch buffer. Tapping a choice submits
immediately (no Submit button); feedback shows green/red plus the correct
answer briefly, plays the success/error sound, then auto-advances after
~1500ms (a manual «معمای بعدی» is also available).

## Speed mode

Standard 60s prepare-then-clock lifecycle: open (`preparing`) → prepare
≥20 → start clock → tap-to-submit loop with ~450ms auto-advance → finish
→ server-rebuilt per-puzzle report from stored attempts. Late submits are
rejected authoritatively (410).

## Files

- `backend/app/modules/material_comparison/material.py` — values,
  board/FEN totals, classifier, 10% gate (isolated, fully tested).
- `backend/app/modules/material_comparison/validator.py` — FEN-shape
  validation (`{choice}` vs FEN-derived verdict) + legacy left/right
  fallback for pre-existing rows.
- `backend/app/modules/material_comparison/scoring.py` — +5/−2.
- `backend/app/modules/material_comparison/generator.py` — eligible
  sampling from `puzzles.db` with category balancing.
- `backend/app/modules/material_comparison/sessions.py` (+ `models.py`,
  `schemas.py`, `router.py`) — speed sessions under `/api/v1/heavier-side`.
- `backend/app/modules/material_comparison/seed.py` — 15 verified FEN
  seeds (5/5/5).
- `frontend/src/components/exercise/HeavierSidePlay.tsx` — practice +
  speed loops over the shared `ChessBoard` (read-only) with three large
  touch choices.
- i18n: `heavierSide.*` keys in `src/i18n/fa.ts`.
