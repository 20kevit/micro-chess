# Exercise 2 — Legal Destinations (مقصدهای قانونی)

Production v1 status. The user sees a board of WHITE pieces only (no black
king, no black pieces in generated positions) with one TARGET piece marked
by a sky-blue ring, and must select ALL legal destination squares for that
piece («این فیل به چه خانه‌هایی می‌تواند برود؟»), then presses
«بررسی جواب». Identifier: `legal-destinations`.

## Purpose

Teach piece movement: how each of the six kinds (pawn/knight/bishop/rook/
queen/king) moves and how friendly pieces block paths. Second vertical
slice; it reuses the Exercise 1 patterns (generator, sessions, play loop,
design tokens) instead of inventing parallel infrastructure.

## User flow

```text
Main Page (/)
   ↓  مقصدهای قانونی card
   ├── تمرینی (?mode=practice)      └── سرعتی (?mode=speed)
   ↓                                     ↓
full-viewport game screen           prepare ≥20 puzzles (no clock)
   ↓                                     ↓
first puzzle loads immediately     clock starts → 60s session
   ↓                                     ↓
select → بررسی جواب → instant      per-puzzle feedback pill → queued next
feedback → prefetched next               ↓
                                    authoritative final report
```

- The Practice and Speed buttons on the home page directly enter their
  corresponding exercise modes. There is no intermediate mode-selection
  screen; the buttons themselves are the mode selection.
- Gameplay runs in a full-viewport overlay (`PieceGameLayout.GameShell`):
  board + question + timer + submit always fit without page scrolling.
- Board: tap to select, tap again to deselect, any count incl. zero.
  The target piece carries a sky-blue ring (`target` square state); it
  never implies a correct destination and feedback states overwrite it.
  Submission happens ONLY via «بررسی جواب» — never on square click.
- While submitting, the button locks and duplicate submits are refused.
- Board locks while submitting / after submission; feedback shows states.

## Full-viewport gameplay (no scroll)

Same shell as Exercise 1 (shared `PieceGameLayout` components):

- `GameShell`: fixed full-viewport overlay, compact top bar (back link,
  title, mode badge, optional tally), body scroll locked while mounted.
- Portrait stacks question → timer → board → action; landscape puts the
  board beside a 240px control column. Orientation is measured from the
  game root (`orientationOf`, tested); board size is exact via
  ResizeObserver (`fitSquareSize`, capped at 600px).
- Speed feedback is a floating pill over the board (zero layout growth);
  practice feedback details sit in-flow while the board flex-shrinks.
- Responsive matrix inherited from Exercise 1 (360×800 … 1366×768):
  board square and in view, question/submit/timer in view, no page
  scroll, RTL page with LTR board island, Vazirmatn loaded.

## Practice Mode

- Untimed. Entering the mode immediately loads the first puzzle.
- Client prefetch buffer (current + next): while the user solves the
  current puzzle, the next one is prepared in the background. Pressing
  «معمای بعدی» swaps to the already-ready puzzle and refills the buffer.
- Fresh puzzles come from `POST /api/v1/legal-destinations/next`
  (accepts `exclude_ids` to avoid just-shown repeats).
- Answers submit through the standard `POST /api/v1/attempts`
  (mode=practice, anonymous allowed, `rating_delta` always None).
- Stale-request protection: a generation counter + mounted guard means a
  slow/old response can never overwrite the current puzzle; prefetch
  failures never destroy the active puzzle (on-demand fallback).
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
4. Loop over the client queue: select → submit → ~450ms board feedback
   (`FEEDBACK_MS = 450`, green/red/orange) → AUTOMATIC advance to the
   next queued puzzle. There is deliberately NO manual "next puzzle"
   button in Speed Mode; a single lock held from submit through the
   transition refuses double-submits and is released on EVERY advance
   path, the 60s timer keeps running, and expiry mid-transition routes
   to the report.
5. Background refill is proactive: whenever the queue drops below 12, 12
   more puzzles are prepared without blocking the active puzzle, so the
   buffer oscillates in a healthy range instead of draining toward
   empty. Failed refills are silent and retried on the next transition;
   a genuinely exhausted queue falls back to a single on-demand fetch.
6. Expiry/finish → `GET .../sessions/{id}/report`: the complete
   authoritative report (see below).

Every automatic transition runs a full per-puzzle reset (selection,
hints, feedback, startedAt, submit lock) so puzzles #2, #3, … submit
exactly like #1 — regression-tested with three consecutive submissions.

Session-loss recovery mirrors Exercise 1 (404 `session_not_found` /
`session_expired` → authoritative report attempt, then dead screen
«ارتباط با جلسه سرعتی قطع شد…» with fresh-start retry; unknown puzzle
→ skip and auto-advance, give up after 3 consecutive skips).

## Legal destination definition (MVP)

A square the target piece can legally move to under its movement rules
and the current board occupancy. Generated boards hold only white
pieces, so:

- No check/checkmate scenarios are invented; no black king is required.
- Ordinary movement is never rejected for lack of an opposing king.
- No enemy attack map exists, so no attack restrictions are invented
  (the generator uses the `ignore-enemy-attacks` profile, i.e.
  python-chess pseudo-legal moves: blocking rules apply, attacked
  squares stay legal).
- Pawn: one step if empty; two steps from rank 2 if both squares empty;
  diagonal captures only onto opposing pieces — on white-only boards
  there are normally NO diagonal destinations. Never backwards.
- Knight: all L-shapes on board, empty or enemy-occupied; jumps over
  pieces; friendly-occupied destinations excluded.
- Bishop/Rook/Queen: unobstructed rays until the first occupied square;
  friendly pieces block and are never destinations.
- King: all adjacent in-board squares not occupied by friendly pieces.
- Castling, en passant, and promotion choices are NOT part of this
  exercise.

Movement is computed with python-chess as the authoritative engine
(`legal_destinations()`); no second movement engine exists in the
frontend.

## Question generation (`generator.py`)

Dynamic — never a fixed FEN list:

- Target type drawn uniformly from pawn/knight/bishop/rook/queen/king
  (data-driven `PIECE_TYPES`, no special-case chains).
- Exactly one white king on the board (the target itself when it is a
  king), plus 2–6 white blockers. No black pieces at all.
- Deliberate (not purely random) blockers: 1–2 pieces placed on the
  target's movement paths with ~70% probability (slider near-rays,
  knight destinations, king neighbours, pawn blocks ahead), the rest
  random — so questions teach blocking instead of showing empty boards.
- Pawns never on rank 1/8; blocked/open/double-step situations all occur.
- Zero-target positions are valid but throttled (~15% kept) so they stay
  possible without dominating.
- Bounded retries (50 attempts); failure raises instead of looping.
- Persian prompt («این {piece} به چه خانه‌هایی می‌تواند برود؟»),
  explanation, and one hint per piece kind; rating scales with
  destination count (750–1250 range, ≥5 distinct values).
- Persisted as a published `puzzles` row:
  `position_json={"from", "profile"}`,
  `answer_json={"squares", "from", "profile"}`. Identical
  (position, target) rows are reused, not duplicated; `exclude_ids`
  steers variety with bounded re-rolls.

## Target-piece highlighting

The target square (from `position_json.from`, part of the task — NOT the
answer) renders with the shared `target` board state: sky-blue ring
(`outline-sky-400`), visible on light/dark squares, mobile/desktop,
without obscuring the SVG piece. Feedback states (green/amber/red)
overwrite it on collision. Destinations are never marked before
submission — the frontend never receives `answer_json`.

## Validation (`validator.py`)

Backend-authoritative exact set match (same contract as Exercise 1):

| Target | Selection | Result |
|---|---|---|
| `{b2,c3,d4}` | `{b2,c3,d4}` (any order) | CORRECT |
| `{b2,c3,d4}` | `{}` | WRONG |
| `{b2,c3,d4}` | `{b2,c3}` | PARTIAL |
| `{}` | `{}` | CORRECT |
| `{}` | `{e4}` | WRONG |

- CORRECT: selected set == target set (empty==empty included).
- PARTIAL: ≥1 correct selection with missed and/or wrong ones.
- WRONG: no correct selections.
- Duplicates normalized (sets); order irrelevant; malformed square
  names count as wrong, never crash.
- Client-supplied `squares`/`from`/`fen` fields are ignored; grading
  always runs against the stored `answer_json`.
- Rule profiles stay data (`RULE_PROFILES`: `standard` via
  `legal_moves`, `ignore-enemy-attacks` via `pseudo_legal_moves`).

## Scoring (authoritative, per-square)

Exact formula, computed backend-side from the validation detail:

```text
score = (correct_selected × 5) − (missed_targets × 1) − (wrong_selected × 2)
```

with one explicit exception: a correctly answered zero-target question
(empty target set, empty selection) awards a +5 completion bonus instead
of 0.

Spec examples: `[b2,c3,d4]/[b2,c3,d4]` → +15; `[b2,c3,d4]/[b2,c3]` →
+9; `[b2,c3,d4]/[b2,c3,h8]` → +7; `[b2,c3,d4]/[]` → −3 (negatives kept,
never clamped). Zero-target: `[]/[]` → CORRECT +5; `[]/[e4]` → WRONG −2.

- Registered via `register_scorer("legal-destinations", score_squares)`;
  computed independently of the result label.
- Never trusted from the client; malformed selections cost −2 each.

## Final report (Speed)

`GET /api/v1/legal-destinations/sessions/{id}/report` rebuilds the
report from stored attempts (refresh-safe):

- Summary: attempted / correct / partial / wrong / total score, plus
  average per puzzle and accuracy rendered client-side.
- Per-puzzle entries in answer order: prompt, result badge
  (درست/ناقص/اشتباه), score, missed/wrong counts, correct squares
  (revealed post-answer).

## Feedback

After submit: colored board rings + banner + per-puzzle score + counts
(درست / جا افتاده / اشتباه) + child-friendly legend:

- Green (`✓`): correct destinations selected.
- Orange/amber (`!`): legal destinations missed.
- Red (`✕`): selected squares that are NOT legal.

In Speed Mode the banner shows for ~450ms and the loop auto-advances;
Practice keeps its manual «معمای بعدی» step.

## Persian / RTL rendering

Existing Design System typography (self-hosted Vazirmatn, `lang="fa"`
`dir="rtl"`, UTF-8). Page stays RTL; the chessboard island stays
`dir="ltr"` with a-file left in White orientation. Hint uses the compact
circular `؟` button (44px hit area, proper aria-label) with an overlay
popover. New strings: `legal.title`, `legal.emptyAllowed`.

## Security

- `answer_json`/destination squares/solution metadata never leave the
  server before submission — including inside prefetch buffers (covered
  by API tests).
- Grading and scoring use the stored answer only; client `fen`/
  `squares`/`from`/`score` fields are ignored (covered by tests).
- Only puzzles issued to a session can be submitted to it (404
  otherwise); the speed clock is server-authoritative (410 on expiry).

## API

| Method & path | Purpose |
|---|---|
| `POST /api/v1/legal-destinations/next` `{exclude_ids?}` | fresh random practice puzzle (`PuzzleOut`, no answer) |
| `POST /api/v1/legal-destinations/sessions` | open session (`preparing`, clock NOT running) |
| `POST /api/v1/legal-destinations/sessions/{id}/puzzles` `{count}` | prepare N buffer puzzles (`410` when expired; capped at 60) |
| `POST /api/v1/legal-destinations/sessions/{id}/start` | start the 60s clock (`409 buffer_not_ready` below 20) |
| `POST /api/v1/legal-destinations/sessions/{id}/next` | single session puzzle |
| `POST /api/v1/legal-destinations/sessions/{id}/submit` | graded answer + updated summary (`409` before start, `410` when expired) |
| `GET /api/v1/legal-destinations/sessions/{id}` | summary (auto-expires) |
| `GET /api/v1/legal-destinations/sessions/{id}/report` | authoritative per-puzzle report |
| `POST /api/v1/legal-destinations/sessions/{id}/finish` | end early + summary |
| `POST /api/v1/attempts` | standard attempt submit (practice) |
| `GET /api/v1/puzzles?exercise=legal-destinations` | legacy seed rows (read-only) |

Errors: `session_not_found` (404), `session_not_started` (409),
`session_expired` (410), `buffer_not_ready` (409),
`puzzle_not_in_session`/`puzzle_not_available` (404).

## Tests

- `tests/test_legal_destinations.py` — legacy seed movement/validation/
  API (updated: per-square scoring assertion).
- `tests/test_legal_destinations_ex2.py` — spec coverage: pawn edges/
  blocks/backward, knight edge/friendly/jump, slider blockers, king
  edges/friendly, set semantics (order/duplicates/malformed), exact
  scoring formula + spec examples, zero-target +5, generator validity
  (white-only, one king, no black pieces, independent python-chess
  recomputation, all six kinds, dedup, bounded failure), practice next
  + full speed lifecycle (20-buffer, 60s, no-leak, report-vs-attempts
  equality, foreign-puzzle rejection, expiry authority).
- Frontend (`npm test`, vitest): catalog practice/speed entries + URLs,
  direct mode entry, target highlight without answer leak, multi-select
  toggles, submit payload shape, feedback ring colors
  (green/amber/red), zero-target +5 display, practice advance, speed
  3-consecutive-submission reset, auto-advance with no next button,
  background refill continuity, preparing UI without buffer counts,
  expiry report rendering, compact `؟` hint button.

## Known limitations

- Speed sessions are per-exercise (`legal_speed_sessions`, mirroring
  `piece_speed_sessions`); a generic session table can replace both
  when the pattern stabilises.
- Rating stays a stub: `rating_delta` is always None.
- Generated positions are white-only by design (MVP scope); enemy
  captures appear only in the legacy seed rows.
