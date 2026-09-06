# Exercise 13 — Chinese Board (صفحه چینی)

Train visual memory: study a real chess position briefly, then rebuild the
exact position from memory. Unlike tactical exercises there are no moves,
legal-move rules, checks, captures, or engine evaluations — only piece
type + color + square for every original piece.

## The loop

```text
memorize (piece_count × 0.3s, read-only board)
↓ fade (skipped under prefers-reduced-motion)
reconstruct (empty board + tap palette)
↓ بررسی صفحه
feedback (counts + score + yours/correct toggle)
↓
practice: manual «صفحه بعدی» (no auto-advance)
speed:    brief feedback → auto-advance (~600ms)
```

## Puzzle source

Real positions from the shared `puzzles.db` (FEN only; Moves/Rating/Themes
ignored), served through `positions/repository.py` (indexed rowid probing;
the table is never loaded into memory). The stored FEN is the single
authority for both the board shown during memorization and the answer used
at grading — the client never supplies the original position.

## Memorization budget

```text
memorization_ms = piece_count × 1000
```

Every piece (kings included) counts once; empty squares and FEN metadata
(side to move, castling, en passant, clocks) are ignored. No difficulty
gate and no piece-count filter: the count is naturally bounded by chess
(≤ 32 pieces, so ~4s–32s on real data). Measured on the real
`puzzles.db` (5.3M rows, 2000-position sample): counts span 4–32, bulk at
7–26, median near 18–19. Every real position is servable as-is, so no
bounded policy beyond the chess maximum was needed.

The budget travels in `position_json.memorization_ms` (computed
server-side from the single `MEMORIZE_MS_PER_PIECE` constant in
`chinese_board/pieces.py`); the client only renders the countdown and
holds no independent timing value.

## Reconstruction interaction

## Reconstruction interaction

- Tap palette piece (12 SVG pieces + eraser, all fixed 44px in a wrapping
  centered row, labelled, `aria-pressed`), tap square to place; tapping an
  occupied square replaces the piece; eraser removes. No drag-and-drop
  required. Fixed-size tools (never a stretching grid) keep pieces
  undistorted in narrow sidebars and stop the palette ballooning on
  tablets — see the viewport rule in `docs/DESIGN_SYSTEM.md`.
- Free placement: duplicate kings, missing kings, illegal positions are
  all allowed mid-reconstruction. Nothing is enforced before checking.
- Fixed White orientation in both phases (critical for spatial memory);
  coordinates stay visible. Page `dir` is RTL, the board island is LTR.

## Matching algorithm (`chinese_board/validator.py`)

Pieces are `(color, type, square)` descriptors (e.g. `white:Q@d4`).
Deterministic, order-insensitive, no double-counting:

1. Exact matches first → correct (+5 each).
2. Remaining originals vs remaining user pieces paired by identical
   `(color, type)` on different squares → each pair is ONE wrong piece
   (−2). A queen remembered on the wrong square is a single error, not
   a missing plus an extra.
3. Still-unmatched originals → missing (−2 each).
4. Still-unmatched user pieces → extra (−2 each).

Result: CORRECT iff the reconstruction equals the original exactly (no
wrong, no missing, no extra); otherwise WRONG — no PARTIAL, the per-piece
score already expresses partial progress. Malformed input (bad entries,
two pieces on one square, invalid/missing FEN) fails safe as WRONG.

## Scoring (`chinese_board/scoring.py`, registered scorer)

```text
score = 5 × correct − 2 × (wrong + missing)
```

`detail["wrong"]` already contains wrong-square pairs AND extras (every
user-side error exactly once); `detail["missed"]`/`detail["missing"]`
contains every original-side gap — the two lists are disjoint by
construction. Examples: 10/10 → 50; 9 + 1 missing → 43; 9 + 1
wrong-square → 43; 10 + 1 extra → 48. No floor: negative scores are
allowed (an empty board scores −2 per original piece).

## Server authority

- Client sends only `{pieces: [{square, piece, color}]}` plus the
  puzzle/session id. Client score/count/FEN fields are ignored; the
  server reloads the stored FEN, re-derives the piece set, grades, and
  scores. Session submit additionally strips malformed entries.
- Active-puzzle APIs (`/next`, session buffers, `PuzzleOut`) never expose
  `answer_json`. The FEN in `position_json` is the board shown during
  memorization; nothing is re-sent after the board clears — the
  post-submit «پاسخ صحیح» view renders from the already-held FEN.
- The 60s speed clock is server-authoritative (410 on late submits); the
  per-puzzle study budget is a display budget only.

## Practice mode

Untimed at the session level; each puzzle keeps its own study budget.
Manual «صفحه بعدی» after feedback (no auto-advance); retry re-studies the
same puzzle. Current + next prefetch buffer of public puzzle data.

## Speed mode

Standard 60s prepare-then-clock lifecycle: open (`preparing`) → prepare
≥20 → start clock → memorize → rebuild → check → ~600ms feedback →
auto-advance → finish → server-rebuilt per-puzzle report from stored
attempts. Late submits are rejected authoritatively (410).

## Feedback

Counts (درست/اشتباه/جا افتاده/اضافی) + score + success/error sound.
Practice boards: yours (green exact, red wrong/extra) toggleable with the
correct board (green exact, amber gaps) — only after submission, never
before; review boards are width-capped (`max-w-[520px]`, centered) so
they never blow out narrow viewports. Speed feedback is counts + score
only (no board), so the 600ms glance always fits without scrolling.

## Responsive viewport fit

The whole exercise fits the viewport with no page-level scroll
(`board_size <= min(available_width, available_height)` via the shared
`useGameFit` measurement — the board container determines the size, never
the reverse). Portrait stacks question → board → palette → بررسی;
landscape keeps the height-capped board large beside a 368px control
column sized by arithmetic (2-row palette + single-line question +
timer + check fit 330px+ heights, verified down to 844×390 and 667×375).
Verified with `frontend/qa/chinese-board.cjs` on 1920×1080, 1366×768,
768×1024, 1024×768, 390×844, 360×800, 844×390 (board/palette/check
in-view, no overflow, no JS errors, both modes).

## Files

- `backend/app/modules/chinese_board/pieces.py` — extraction, counting,
  `MEMORIZE_MS_PER_PIECE = 1000` (pure, fully tested).
- `backend/app/modules/chinese_board/validator.py` — descriptor matching
  (`{pieces}` vs FEN-derived set) + square overlays for the result UI.
- `backend/app/modules/chinese_board/scoring.py` — +5/−2, negatives kept.
- `backend/app/modules/chinese_board/generator.py` — any-valid-FEN
  sampling from `puzzles.db` with server-side budget.
- `backend/app/modules/chinese_board/sessions.py` (+ `models.py`,
  `schemas.py`, `router.py`) — speed sessions under
  `/api/v1/chinese-board`.
- `backend/app/modules/chinese_board/seed.py` — 15 verified positions
  spanning 4–32 pieces.
- `frontend/src/components/exercise/ChineseBoardPlay.tsx` — practice +
  speed loops over the shared `ChessBoard` (read-only memorize board,
  tap-palette rebuild, result toggle).
- `frontend/qa/chinese-board.cjs` — headless viewport + interaction QA.
- i18n: `chineseBoard.*` keys in `src/i18n/fa.ts`.
