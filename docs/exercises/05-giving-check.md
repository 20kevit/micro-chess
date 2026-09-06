# Exercise 5 — Giving Check (کیش دادن)

Production v1 status. The user sees a complete chess position loaded from
the shared `puzzles.db` and must find ALL legal moves that give check to
the opponent's King («با کدام حرکت‌ها می‌توان کیش داد؟»), drawing one
arrow per move (`from → to`), then presses «بررسی جواب».
Identifier: `give-check`.

The one rule that defines this exercise:

> A move is a correct answer iff it is a legal chess move, made by a
> non-King piece, and after the move the opponent's King is in check.

Tactical quality is irrelevant: any legal checking move counts, even an
objectively terrible one. No engine evaluation is used — legality plus
the resulting check status (both from python-chess) is the whole rule.
Fifth vertical slice; it reuses the Exercise 1–4 patterns (generator from
the shared position source, per-move scorer, speed sessions, play loop,
design tokens) plus a reusable multi-arrow board layer instead of
inventing parallel infrastructure.

## Roadmap note (renumbering)

Exercises previously planned as 5 (Hanging Pieces) and 6
(Attacker/Defender Equality) were **removed** from the project — no
placeholders remain. All later exercises moved two numbers back, so the
former Exercise 7 (Give Check) is now Exercise 5. Castling Rights moved
to the end of the roadmap. Exercises 1–4 are unchanged.

## User flow

```text
Main Page (/)
   ↓  کیش دادن card
   ├── تمرینی (?mode=practice)      └── سرعتی (?mode=speed)
   ↓                                     ↓
full-viewport game screen           prepare ≥20 puzzles (no clock)
   ↓                                     ↓
first puzzle loads immediately     clock starts → 60s session
   ↓                                     ↓
draw arrows → بررسی جواب → instant per-puzzle feedback pill → queued next
feedback → prefetched next               ↓
                                     authoritative final report
```

- The Practice and Speed buttons on the home page directly enter their
  corresponding exercise modes. There is no intermediate mode-selection
  screen; the buttons themselves are the mode selection.
- Gameplay runs in a full-viewport overlay (`PieceGameLayout.GameShell`):
  board + question + timer + submit always fit without page scrolling.
- Board: press/drag from a source square, drag toward the destination,
  release to create an arrow (mouse and touch). Each arrow is one
  candidate checking move. Arrows can be removed individually (✕ per
  arrow) or cleared all at once; duplicates normalize away; direction
  matters (`e2→e4` ≠ `e4→e2`). Pawn-to-last-rank arrows carry a
  per-arrow promotion picker (Q/R/B/N, default Q). Submission happens
  ONLY via «بررسی جواب» — never on arrow draw.
- While submitting, the button locks and duplicate submits are refused.
- Board locks while submitting / after submission; feedback shows states.

## Full-viewport gameplay (no scroll)

Same shell as Exercises 1–4 (shared `PieceGameLayout` components):

- `GameShell`: fixed full-viewport overlay, compact top bar (back link,
  title, mode badge, optional tally), body scroll locked while mounted.
- Portrait stacks question → timer → board → arrow list → action;
  landscape puts the board beside a 240px control column. Orientation is
  measured from the game root (`orientationOf`, tested); board size is
  exact via ResizeObserver (`fitSquareSize`, capped at 600px).
- Arrows render as SVG over the board in board-fraction coordinates
  (`viewBox="0 0 8 8"`), so they stay aligned at every size and after
  every resize — no separate board implementation, no duplicated
  coordinate math. Tested at 360×800 … 1366×768: board and arrow layer
  never overflow the viewport.
- Speed feedback is a floating pill over the board (zero layout growth);
  practice feedback details sit in-flow while the board flex-shrinks.
- Touch: `touch-action: none` on the board while drawing so page scroll
  and browser gestures never fight the arrow gesture; square buttons keep
  `touch-action: manipulation` with ≥44px targets.

## Practice Mode

- Untimed. Entering the mode immediately loads the first puzzle.
- Client prefetch buffer (current + next): while the user solves the
  current puzzle, the next one is prepared in the background. Pressing
  «معمای بعدی» swaps to the already-ready puzzle and refills the buffer.
- Fresh puzzles come from `POST /api/v1/giving-check/next`
  (accepts `exclude_ids` to avoid just-shown repeats).
- Answers submit through the standard `POST /api/v1/attempts`
  (mode=practice, anonymous allowed, `rating_delta` always None).
- Stale-request protection: a generation counter + mounted guard means a
  slow/old response can never overwrite the current puzzle; prefetch
  failures never destroy the active puzzle (on-demand fallback, which
  stays inside the giving-check exercise).
- Anonymous attempts also append to browser localStorage
  (`lib/localProgress.ts`); the server is source of truth for accounts.
- Practice never terminates on zero-target questions (validator returns
  CORRECT for empty==empty, scored +5).

## Speed Mode

Lifecycle: `preparing` → `active` → `finished`/`expired`.

1. Enter → a session opens in `preparing` (NO clock runs).
2. The client prepares **at least 20 puzzles**
   (`POST .../sessions/{id}/puzzles` `{"count": 20}`) behind a plain
   loading state («در حال آماده‌سازی...»). Internal buffer counts are
   NEVER shown to users.
3. `POST .../sessions/{id}/start` starts the authoritative 60-second
   clock (refused with `409 buffer_not_ready` below 20 buffered).
   Preparation time is never billed to the session.
4. Loop over the client queue: draw arrows → submit → ~450ms arrow
   feedback (`FEEDBACK_MS = 450`, green/red/orange) → AUTOMATIC advance
   to the next queued puzzle. There is deliberately NO manual "next
   puzzle" button in Speed Mode; a single lock held from submit through
   the transition refuses double-submits and is released on EVERY advance
   path, the 60s timer keeps running, and expiry mid-transition routes
   to the report.
5. Background refill is proactive: whenever the queue drops below 12, 12
   more puzzles are prepared without blocking the active puzzle, so the
   buffer oscillates in a healthy range instead of draining toward
   empty. Failed refills are silent and retried on the next transition;
   a genuinely exhausted queue falls back to a single on-demand fetch.
6. Expiry/finish → `GET .../sessions/{id}/report`: the complete
   authoritative report (see below).

Every automatic transition runs a full per-puzzle reset (arrows,
hints, feedback, startedAt, submit lock) so puzzles #2, #3, … submit
exactly like #1 — regression-tested with three consecutive submissions.

Session-loss recovery mirrors Exercises 1–4 (404 `session_not_found` /
`session_expired` → authoritative report attempt, then dead screen
«ارتباط با جلسه سرعتی قطع شد…» with fresh-start retry; unknown puzzle
→ skip and auto-advance, give up after 3 consecutive skips).

## Checking-move definition (MVP)

A move is correct iff ALL of these hold:

```text
1. the move is legal from the current position (python-chess legal_moves:
   pins, blockers, self-check, pawn rules, castling rights, en passant)
2. the moving piece is NOT the King (kings can never legally give check,
   so castling and king-discovered lines are never answers)
3. after the move, the opponent's King is in check (board.is_check())
```

This naturally covers:

- **Direct check** — a slider moves onto a checking line (`a1→a8`).
- **Capture with check** — captures count like ordinary moves
  (`d4→d5` taking on d5 and checking).
- **Discovered check** — the answer arrow is the MOVING piece's
  `from→to` (e.g. knight `d4→f5` uncovering `Bb2`), never the hidden
  checking piece.
- **Double check** — one move, one arrow (e.g. `d4→f5` uncovering the
  bishop AND checking with the knight).
- **Promotion** — each legal checking promotion is a distinct answer
  (`g7g8q` vs `g7g8r`); the answer identity includes the piece letter,
  so a promotion arrow without a piece never matches.
- **En passant** — evaluated as the real legal move; counts only when it
  actually checks.

Worked examples (verified with raw python-chess):

- `4k3/8/8/8/8/8/8/R3K3` → `{a1a2,…,a1a7}` (whole open file checks).
- `7k/8/8/8/3N4/8/1B6/4K3` → all 8 knight moves (each uncovers `Bb2`).
- `8/6k1/8/8/3N4/8/1B6/4K3` → `d4f5` is double check (one answer).
- `3kr3/8/8/8/8/8/4Q3/4K3` → `{e2e7,e2e8}` (`e2h5` is pinned away).
- `7k/6P1/8/8/8/8/8/4K3` → `{g7g8q,g7g8r}` (knight/bishop promotions
  don't check here).
- `8/4k3/8/3pP3/8/8/8/4K3 w - d6` → `{e5d6}` (en passant with check);
  against `Ke8` instead → `{}` (legal EP, no check).
- `k7/8/8/8/8/8/5K2/R7` → king moves never included, even the legal
  `f2e3` that uncovers the rook.

## Position source (`generator.py`)

Shared `puzzles.db`, exactly like Exercises 1 and 4 — never a separate
database:

- Only the FEN column is used; Moves/Rating/Themes are ignored.
- Access goes through `positions.repository` (read-only indexed rowid
  probing, invalid rows skipped, curated fallback FENs when the file is
  absent). The schema is never modified.
- Positions where EITHER king is already in check are rejected
  (`either_king_in_check`, bounded rejection sampling — never an
  infinite loop). The exercise asks which moves GIVE check, not how to
  answer one.
- The authoritative answer is computed server-side with
  `checking_moves()` (legal non-King moves + resulting check).
- Bounded selection: up to 25 candidate FENs are sampled and evaluated;
  a position with at least one checking move is preferred, but ~15% of
  puzzles keep the first valid FEN immediately so zero-target ("no
  checking move") questions stay real. Fallback is always a valid
  random position.
- Persian prompt («با کدام حرکت‌ها می‌توان کیش داد؟»), generic
  explanation, and one hint; rating scales with answer count (700–1250
  range, base 800).
- Persisted as a published `puzzles` row:
  `position_json={"fen"}`,
  `answer_json={"moves": ["e2e4", "g7g8q", ...]}` (UCI strings).
  Identical FEN rows are reused, not duplicated; `exclude_ids` steers
  variety with bounded re-rolls.

## Arrow interaction (frontend)

New reusable layer on the existing board (`components/chess/`):

- `ChessBoard` accepts `arrows: BoardArrow[]` (`{from, to, tone?}`)
  alongside the legacy single `arrow`; tones map to violet (user),
  green (correct), amber (missed), red (wrong) — same semantics as the
  square rings. Pure helpers (`arrowKey`, `normalizeArrows`,
  `uciToArrow`, `arrowToUci`, `computeArrowGeometry`) are exported and
  unit-tested.
- Arrow rendering model (SVG-based, Lichess-style): each arrow is a slim
  shaft (`<line>`, 0.18 square units wide) plus an independent filled
  triangular head (`<polygon>`, 0.45 long × 0.42 wide in square units).
  The shaft is shortened along the direction vector so it terminates at
  the CENTER of the arrowhead base (tip = destination square center);
  a 0.02-unit overlap tucked under the opaque head prevents
  antialiasing seams, so no shaft is ever visible inside the triangle.
  Short arrows clamp the head to 60% of their length. All geometry lives
  in board units (`viewBox="0 0 8 8"`), so it scales with board size by
  construction — no pixel constants, no CSS triangles, no marker hacks.
- `arrowDrawMode="any-drag"` turns every press-drag-release (left mouse
  button or touch) into an arrow — no right-button or long-press needed
  — while the default mode keeps the legacy behavior for older
  exercises. Taps without movement still pass through as
  `onSquarePress`; the arrow overlay never duplicates board
  sizing/coordinate math (single SVG `viewBox`, fraction centers).
- `GivingCheckPlay` (practice + speed, same architecture as the
  Exercise 4 loop) owns the arrow SET: add on draw, per-arrow ✕ remove,
  clear-all, per-arrow promotion picker (only for pawn-to-last-rank
  arrows), and feedback recoloring from `result.detail` UCI lists.
  Submission payload: `{moves: [{from, to, promotion?}]}` — promotion
  is sent ONLY for promotion arrows (a bare `g7→g8` never matches
  `g7g8q`, by design).

## Validation (`validator.py`)

Backend-authoritative exact set match on canonical UCI strings (same
contract as Exercises 1–4):

| Targets | Selection | Result |
|---|---|---|
| `{d4d8,d4h8}` | `{d4d8,d4h8}` (any order) | CORRECT |
| `{d4d8,d4h8}` | `{}` | WRONG |
| `{d4d8,d4h8}` | `{d4d8}` | PARTIAL |
| `{d4d8,d4h8}` | `{d4d8,e2e4}` | PARTIAL |
| `{}` | `{}` | CORRECT |
| `{}` | `{e2e4}` | WRONG |
| `{g7g8q}` | `{g7→g8}` (no piece) | WRONG |

- CORRECT: selected set == target set (empty==empty included).
- PARTIAL: ≥1 correct selection with missed and/or wrong ones.
- WRONG: no correct selections (including any arrow on zero-target).
- Duplicates normalized (sets); order irrelevant; direction matters;
  malformed arrows count as wrong, never crash.
- Client-supplied `fen`/`moves`-overrides/`score` fields are ignored;
  grading always runs against the stored `answer_json`.

## Scoring (authoritative, per-move)

Exact formula, computed backend-side from the validation detail:

```text
score = (correct_selected × 5) − (missed_targets × 1) − (wrong_selected × 2)
```

with one explicit exception: a correctly answered zero-target question
(empty checking-move set, no arrows) awards a +5 completion bonus
instead of 0.

- Registered via `register_scorer("give-check", score_moves)`;
  computed independently of the result label.
- Never trusted from the client; malformed arrows cost −2 each.
- Negative scores allowed, never clamped.

## Final report (Speed)

`GET /api/v1/giving-check/sessions/{id}/report` rebuilds the report
from stored attempts (refresh-safe):

- Summary: attempted / correct / partial / wrong / total score, plus
  average per puzzle and accuracy rendered client-side.
- Per-puzzle entries in answer order: prompt, result badge
  (درست/ناقص/اشتباه), score, missed/wrong counts, checking moves
  rendered as `e2→e4` arrows (revealed post-answer).

## Feedback

After submit: colored arrows on the board + banner + per-puzzle score +
counts (درست / جا افتاده / اشتباه):

- Green: correctly drawn checking moves.
- Orange/amber: valid checking moves missed.
- Red: drawn arrows that are not checking moves.

Before submission, no arrow is ever marked — the frontend never receives
`answer_json`.

In Speed Mode the pill shows for ~450ms and the loop auto-advances;
Practice keeps its manual «معمای بعدی» step.

## Persian / RTL rendering

Existing Design System typography (self-hosted Vazirmatn, `lang="fa"`
`dir="rtl"`, UTF-8). Page stays RTL; the chessboard island stays
`dir="ltr"` with a-file left in White orientation. Question
(«با کدام حرکت‌ها می‌توان کیش داد؟») is prominent, centered, RTL. New
strings: `givecheck.title/howto/emptyAllowed/arrows/removeArrow/
promotion`, `exercises.give-check.title/desc` («کیش دادن»).

## Security

- `answer_json`/checking moves/solution metadata never leave the
  server before submission — including inside prefetch buffers (covered
  by API tests).
- Grading and scoring use the stored answer only; client `fen`/`score`
  fields are ignored (covered by tests).
- Only puzzles issued to a session can be submitted to it (404
  otherwise); the speed clock is server-authoritative (410 on expiry).

## API

| Method & path | Purpose |
|---|---|
| `POST /api/v1/giving-check/next` `{exclude_ids?}` | fresh random practice puzzle (`PuzzleOut`, no answer) |
| `POST /api/v1/giving-check/sessions` | open session (`preparing`, clock NOT running) |
| `POST /api/v1/giving-check/sessions/{id}/puzzles` `{count}` | prepare N buffer puzzles (`410` when expired; capped at 60) |
| `POST /api/v1/giving-check/sessions/{id}/start` | start the 60s clock (`409 buffer_not_ready` below 20) |
| `POST /api/v1/giving-check/sessions/{id}/next` | single session puzzle |
| `POST /api/v1/giving-check/sessions/{id}/submit` | graded answer + updated summary (`409` before start, `410` when expired) |
| `GET /api/v1/giving-check/sessions/{id}` | summary (auto-expires) |
| `GET /api/v1/giving-check/sessions/{id}/report` | authoritative per-puzzle report |
| `POST /api/v1/giving-check/sessions/{id}/finish` | end early + summary |
| `POST /api/v1/attempts` | standard attempt submit (practice) |

Errors: `session_not_found` (404), `session_not_started` (409),
`session_expired` (410), `buffer_not_ready` (409),
`puzzle_not_in_session`/`puzzle_not_available` (404).

## Tests

- `tests/test_give_check.py` (54 tests) — checking-move computation
  (all five piece types, single/multiple/zero, capture, discovered with
  moving-piece identity, double-check single-answer, pins,
  blocked/self-check legality, king exclusion incl. castling and
  king-uncovered lines, pawn/promotion distinctness, en passant
  check/no-check, in-check detection both colors), generator rejection
  of in-check positions, set semantics (order/duplicates/direction/
  plain-UCI/malformed), zero-target, exact scoring formula + bonus,
  registry, security (client fields ignored), practice next + full
  speed lifecycle (20-buffer, 60s, no-leak, report, pre-start refusal,
  unknown-session 404).
- Frontend (`npm test`, vitest): catalog practice/speed entries + URLs,
  roadmap order (no hanging/equal, give-check 5th, castling last),
  direct mode entry, mouse + touch arrow drawing, duplicates/direction,
  per-arrow remove + clear, promotion picker payload, feedback arrow
  colors (green/amber/red), zero-target +5 display, practice 2nd/3rd
  puzzle progression, speed prepare-20-before-clock without buffer
  counts, 3-consecutive auto-advance with double-submit lock, arrows
  drawn and cleared in speed.
- `ChessBoard.test.tsx`: arrow helpers (key/dedupe/UCI round-trip),
  multi-arrow rendering in board-fraction coordinates (resize-proof),
  tone colors, legacy single arrow, zero-length/off-board safety.

## Known limitations

- Speed sessions are per-exercise (`giving_check_speed_sessions`,
  mirroring the Exercises 1–4 tables); a generic session table can
  replace all five when the pattern stabilises.
- Rating stays a stub: `rating_delta` is always None.
- Puzzle selection ignores `Rating`/`Themes`/`Moves` by design; smarter
  per-exercise selection (difficulty targeting, theme filtering,
  zero-target rate tuning) is future work.
- Promotion arrows default to queen in the UI; the picker covers all
  four choices but positions where two promotions check are rare in the
  shared source.
