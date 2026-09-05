# Exercise 4 — Undefended Pieces (مهره‌های بی‌دفاع)

Production v1 status. The user sees a complete chess position loaded from
the shared `puzzles.db` and must select ALL undefended pieces of BOTH
colors («کدام مهره‌ها بی‌دفاع هستند؟»), then presses «بررسی جواب».
Identifier: `undefended-pieces`.

The one rule that defines this exercise:

> A non-King piece is Undefended iff at least one valid enemy piece
> attacks it AND no valid friendly piece defends it.

This is structural, not tactical: no hanging/material evaluation, no
engine, no "would the opponent actually capture it".

## Purpose

Teach attack/defense structure across a real position: pawn diagonals,
knight jumps, sliding rays with blockers, king adjacency — plus the one
subtlety that changes answers, the Absolute Pin rule. Fourth vertical
slice; it reuses the Exercise 1–3 patterns (generator from the shared
position source, per-square scorer, speed sessions, play loop, design
tokens) instead of inventing parallel infrastructure.

## User flow

```text
Main Page (/)
   ↓  مهره‌های بی‌دفاع card
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
  Nothing is highlighted up front (the whole board is the question); only
  the user's selections are shown. Submission happens ONLY via
  «بررسی جواب» — never on square click.
- While submitting, the button locks and duplicate submits are refused.
- Board locks while submitting / after submission; feedback shows states.

## Full-viewport gameplay (no scroll)

Same shell as Exercises 1–3 (shared `PieceGameLayout` components):

- `GameShell`: fixed full-viewport overlay, compact top bar (back link,
  title, mode badge, optional tally), body scroll locked while mounted.
- Portrait stacks question → timer → board → action; landscape puts the
  board beside a 240px control column. Orientation is measured from the
  game root (`orientationOf`, tested); board size is exact via
  ResizeObserver (`fitSquareSize`, capped at 600px).
- Speed feedback is a floating pill over the board (zero layout growth);
  practice feedback details sit in-flow while the board flex-shrinks.
- Responsive matrix inherited from Exercises 1–3 (360×800 … 1366×768):
  board square and in view, question/submit/timer in view, no page
  scroll, RTL page with LTR board island, Vazirmatn loaded.

## Practice Mode

- Untimed. Entering the mode immediately loads the first puzzle.
- Client prefetch buffer (current + next): while the user solves the
  current puzzle, the next one is prepared in the background. Pressing
  «معمای بعدی» swaps to the already-ready puzzle and refills the buffer.
- Fresh puzzles come from `POST /api/v1/undefended-pieces/next`
  (accepts `exclude_ids` to avoid just-shown repeats).
- Answers submit through the standard `POST /api/v1/attempts`
  (mode=practice, anonymous allowed, `rating_delta` always None).
- Stale-request protection: a generation counter + mounted guard means a
  slow/old response can never overwrite the current puzzle; prefetch
  failures never destroy the active puzzle (on-demand fallback, which
  stays inside the undefended-pieces exercise).
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

Session-loss recovery mirrors Exercises 1–3 (404 `session_not_found` /
`session_expired` → authoritative report attempt, then dead screen
«ارتباط با جلسه سرعتی قطع شد…» with fresh-start retry; unknown puzzle
→ skip and auto-advance, give up after 3 consecutive skips).

## Undefended definition (MVP)

A non-King piece is undefended iff:

```text
at least one valid enemy piece attacks it
AND
no valid friendly piece defends it
```

Attack geometry comes from python-chess (`board.attackers`): pawn
diagonals (never straight ahead), knight jumps over blockers, sliding
rays stopped by the first occupied square, kings adjacent — even when
moving there would be illegal. No legal-move, exchange, or engine logic.

Validity filter (the Absolute Pin rule): an absolutely pinned piece
(`board.is_pinned`: moving it would expose its OWN King to check) does
NOT count as an attacker or defender. A piece shielding any other piece
(Queen, rook, …) is NOT absolutely pinned and still counts normally.
The King itself is never an answer, but it still attacks/defends
adjacent squares when evaluating other pieces.

Worked examples from the seed set:

- `4k3/8/2b5/8/4R3/8/8/4K3` → `{e4}` (attacked, no defender).
- Same plus white queen e2 → `{}` (defended).
- `4k1r1/8/1b6/8/8/4R3/6N1/6K1` → `{e3}` (the geometric defender Ng2 is
  absolutely pinned, so it does not count).
- `4k3/3b4/2B1R3/8/8/8/8/4K3` → `{}` (the only attacker Bd7 is absolutely
  pinned, so it does not count).
- `4q2k/3b4/2B1R3/8/8/8/8/K7` → `{e6}` (Bd7 shields its Queen, not its
  King, so it still counts as an attacker).
- `8/8/8/4k3/8/8/4Q3/4K3` → `{}` (the attacked King is never an answer).

## Position source (`generator.py`)

Shared `puzzles.db`, exactly like Exercise 1 — never a separate database:

- Only the FEN column is used; Moves/Rating/Themes are ignored.
- Access goes through `positions.repository` (read-only indexed rowid
  probing, invalid rows skipped, curated fallback FENs when the file is
  absent). The schema is never modified.
- The authoritative answer is computed server-side with
  `undefended_squares()` (absolute-pin aware).
- Bounded selection (never an infinite loop): up to 25 candidate FENs
  are sampled and evaluated; a position with at least one undefended
  piece is preferred, but ~15% of puzzles keep the first valid FEN
  immediately so zero-target ("nothing undefended") questions stay real.
  Fallback is always a valid random position.
- Persian prompt («کدام مهره‌ها بی‌دفاع هستند؟»), generic explanation,
  and one hint; rating scales with answer count (750–1250 range).
- Persisted as a published `puzzles` row:
  `position_json={"fen", "mode": "standard"}`,
  `answer_json={"squares"}`. Identical FEN rows are reused, not
  duplicated; `exclude_ids` steers variety with bounded re-rolls.

## No pre-highlight

Unlike Exercise 3 (hunter ring), the whole board is the question: the
`targetOf` function always returns null and only the user's selections
carry the `selected` board state before submission. Correct squares are
never marked before submission — the frontend never receives
`answer_json`.

## Validation (`validator.py`)

Backend-authoritative exact set match (same contract as Exercises 1–3):

| Targets | Selection | Result |
|---|---|---|
| `{a1,f6}` | `{a1,f6}` (any order) | CORRECT |
| `{a1,f6}` | `{}` | WRONG |
| `{a1,f6}` | `{a1}` | PARTIAL |
| `{a1,f6}` | `{a1,h7}` | PARTIAL |
| `{}` | `{}` | CORRECT |
| `{}` | `{a1}` | WRONG |

- CORRECT: selected set == target set (empty==empty included).
- PARTIAL: ≥1 correct selection with missed and/or wrong ones.
- WRONG: no correct selections (including any selection on zero-target).
- Duplicates normalized (sets); order irrelevant; malformed square
  names count as wrong, never crash.
- Client-supplied `squares`/`fen`/`score` fields are ignored; grading
  always runs against the stored `answer_json`.

## Scoring (authoritative, per-square)

Exact formula, computed backend-side from the validation detail:

```text
score = (correct_selected × 5) − (missed_targets × 1) − (wrong_selected × 2)
```

with one explicit exception: a correctly answered zero-target question
(empty target set, empty selection) awards a +5 completion bonus instead
of 0.

Spec examples: `[a1,f6,h7]` all three → +15; `[a1,f6]` → +10 − 1 = +9;
`[a1,f6,b2]` → +10 − 1 − 2 = +7; nothing → −3 (negatives kept, never
clamped). Zero-target: `[]/[]` → CORRECT +5; `[]/[a1]` → WRONG −2.

- Registered via `register_scorer("undefended-pieces", score_squares)`;
  computed independently of the result label.
- Never trusted from the client; malformed selections cost −2 each.

## Final report (Speed)

`GET /api/v1/undefended-pieces/sessions/{id}/report` rebuilds the report
from stored attempts (refresh-safe):

- Summary: attempted / correct / partial / wrong / total score, plus
  average per puzzle and accuracy rendered client-side.
- Per-puzzle entries in answer order: prompt, result badge
  (درست/ناقص/اشتباه), score, missed/wrong counts, correct squares
  (revealed post-answer).

## Feedback

After submit: colored board rings + banner + per-puzzle score + counts
(درست / جا افتاده / اشتباه) + child-friendly legend:

- Green (`✓`): correctly selected undefended pieces.
- Orange/amber (`!`): undefended pieces missed.
- Red (`✕`): selected squares that are not undefended.

In Speed Mode the banner shows for ~450ms and the loop auto-advances;
Practice keeps its manual «معمای بعدی» step.

## Persian / RTL rendering

Existing Design System typography (self-hosted Vazirmatn, `lang="fa"`
`dir="rtl"`, UTF-8). Page stays RTL; the chessboard island stays
`dir="ltr"` with a-file left in White orientation. Question
(«کدام مهره‌ها بی‌دفاع هستند؟») is prominent, centered, RTL. Hint uses
the compact circular `؟` button (44px hit area, proper aria-label) with
an overlay popover. New strings: `undefended.title`,
`undefended.intro`, `undefended.emptyAllowed`,
`exercises.undefended-pieces.title/desc`.

## Security

- `answer_json`/undefended squares/solution metadata never leave the
  server before submission — including inside prefetch buffers (covered
  by API tests).
- Grading and scoring use the stored answer only; client `fen`/
  `squares`/`score` fields are ignored (covered by tests).
- Only puzzles issued to a session can be submitted to it (404
  otherwise); the speed clock is server-authoritative (410 on expiry).

## API

| Method & path | Purpose |
|---|---|
| `POST /api/v1/undefended-pieces/next` `{exclude_ids?}` | fresh random practice puzzle (`PuzzleOut`, no answer) |
| `POST /api/v1/undefended-pieces/sessions` | open session (`preparing`, clock NOT running) |
| `POST /api/v1/undefended-pieces/sessions/{id}/puzzles` `{count}` | prepare N buffer puzzles (`410` when expired; capped at 60) |
| `POST /api/v1/undefended-pieces/sessions/{id}/start` | start the 60s clock (`409 buffer_not_ready` below 20) |
| `POST /api/v1/undefended-pieces/sessions/{id}/next` | single session puzzle |
| `POST /api/v1/undefended-pieces/sessions/{id}/submit` | graded answer + updated summary (`409` before start, `410` when expired) |
| `GET /api/v1/undefended-pieces/sessions/{id}` | summary (auto-expires) |
| `GET /api/v1/undefended-pieces/sessions/{id}/report` | authoritative per-puzzle report |
| `POST /api/v1/undefended-pieces/sessions/{id}/finish` | end early + summary |
| `POST /api/v1/attempts` | standard attempt submit (practice) |
| `GET /api/v1/puzzles?exercise=undefended-pieces` | seed rows (read-only) |

Errors: `session_not_found` (404), `session_not_started` (409),
`session_expired` (410), `buffer_not_ready` (409),
`puzzle_not_in_session`/`puzzle_not_available` (404).

## Tests

- `tests/test_undefended_pieces.py` — spec coverage: basic detection
  (white/black/defended/multiple-both-colors/zero/king-excluded),
  piece types (pawn diagonal-only, knight jumps, slider attacks, king
  as attacker/defender, queen), sliding blockers (attack + defense
  blocked, ray-hides-behind), absolute-pin regressions (pinned
  defender, pinned attacker, pin-to-queen still counts, each with an
  explicit `is_pinned` assertion), validation semantics
  (exact/partial/wrong, order/duplicates, malformed, empty,
  client-fields-ignored), registry, exact scoring formula + spec
  examples, zero-target +5, generator (shared-source answers,
  persist/dedup, invalid-FEN rejection), seed (15 puzzles, independent
  python-chess recomputation), practice next + full speed lifecycle
  (20-buffer, 60s, no-leak, report-vs-attempts equality,
  client-solution ignored, foreign-puzzle rejection, expiry authority,
  pre-start refusal).
- Frontend (`npm test`, vitest): catalog practice/speed entries + URLs,
  direct mode entry, NO pre-highlight without answer leak,
  multi-select toggles, submit payload shape, feedback ring colors
  (green/amber/red), zero-target +5 display, practice advance, speed
  3-consecutive-submission reset, auto-advance with no next button,
  background refill continuity, preparing UI without buffer counts,
  expiry report rendering, compact `؟` hint button.

## Known limitations

- Speed sessions are per-exercise (`undefended_speed_sessions`,
  mirroring `piece_speed_sessions` / `legal_speed_sessions` /
  `capture_speed_sessions`); a generic session table can replace all
  four when the pattern stabilises.
- Rating stays a stub: `rating_delta` is always None.
- Puzzle selection ignores `Rating`/`Themes`/`Moves` by design; smarter
  per-exercise selection (difficulty targeting, theme filtering) is
  future work.
