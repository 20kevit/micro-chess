# Exercise 3 — Captures (گرفتن مهره‌ها)

Production v1 status. The user sees a board with exactly ONE white hunter
piece plus 3–8 BLACK pieces, the hunter marked by a sky-blue ring, and must
select ALL black pieces the hunter can capture **right now**
(«کدام مهره‌های سیاه را می‌توان با این رخ زد؟»), then presses
«بررسی جواب». Identifier: `captures`.

The one rule that defines this exercise:

> Whether a black piece is defended or not DOES NOT MATTER.

A defended black queen is still a correct answer when the hunter can
capture it. Defense, exchange evaluation, and hanging-piece logic belong
to Exercise 4 and are never consulted here.

## Purpose

Teach capture mechanics per piece kind: how each of the six kinds
(pawn/knight/bishop/rook/queen/king) takes, how blockers shield pieces
behind them, and — explicitly — that a capture stays a capture even when
the target is defended. Third vertical slice; it reuses the Exercise 1/2
patterns (generator, scorer, sessions, play loop, design tokens) instead
of inventing parallel infrastructure.

## User flow

```text
Main Page (/)
   ↓  گرفتن مهره‌ها card
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
  The hunter piece carries a sky-blue ring (`target` square state); it
  never implies a correct capture and feedback states overwrite it.
  Submission happens ONLY via «بررسی جواب» — never on square click.
- While submitting, the button locks and duplicate submits are refused.
- Board locks while submitting / after submission; feedback shows states.

## Full-viewport gameplay (no scroll)

Same shell as Exercises 1–2 (shared `PieceGameLayout` components):

- `GameShell`: fixed full-viewport overlay, compact top bar (back link,
  title, mode badge, optional tally), body scroll locked while mounted.
- Portrait stacks question → timer → board → action; landscape puts the
  board beside a 240px control column. Orientation is measured from the
  game root (`orientationOf`, tested); board size is exact via
  ResizeObserver (`fitSquareSize`, capped at 600px).
- Speed feedback is a floating pill over the board (zero layout growth);
  practice feedback details sit in-flow while the board flex-shrinks.
- Responsive matrix inherited from Exercises 1–2 (360×800 … 1366×768):
  board square and in view, question/submit/timer in view, no page
  scroll, RTL page with LTR board island, Vazirmatn loaded.

## Practice Mode

- Untimed. Entering the mode immediately loads the first puzzle.
- Client prefetch buffer (current + next): while the user solves the
  current puzzle, the next one is prepared in the background. Pressing
  «معمای بعدی» swaps to the already-ready puzzle and refills the buffer.
- Fresh puzzles come from `POST /api/v1/captures/next`
  (accepts `exclude_ids` to avoid just-shown repeats).
- Answers submit through the standard `POST /api/v1/attempts`
  (mode=practice, anonymous allowed, `rating_delta` always None).
- Stale-request protection: a generation counter + mounted guard means a
  slow/old response can never overwrite the current puzzle; prefetch
  failures never destroy the active puzzle (on-demand fallback, which
  stays inside the captures exercise).
- Anonymous attempts also append to browser localStorage
  (`lib/localProgress.ts`); the server is source of truth for accounts.
- Practice never terminates on zero-capture questions (validator returns
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

Session-loss recovery mirrors Exercises 1–2 (404 `session_not_found` /
`session_expired` → authoritative report attempt, then dead screen
«ارتباط با جلسه سرعتی قطع شد…» with fresh-start retry; unknown puzzle
→ skip and auto-advance, give up after 3 consecutive skips).

## Capture definition (MVP)

A black piece the hunter can capture under its movement rules and the
current board occupancy, computed with the `ignore-enemy-attacks`
profile (python-chess pseudo-legal moves filtered to captures):

- No kings exist on generated boards (no white king, no black king), so
  no check/pin scenarios can arise; enemy attack maps are never
  consulted, so defense NEVER affects the answer.
- Rook/Bishop/Queen: unobstructed rays until the first occupied square;
  the first black piece on a ray is capturable, anything behind it is
  shielded (NOT capturable).
- Knight: all L-destinations occupied by black; surrounding pieces never
  block jumps; adjacent non-L squares are not captures.
- Pawn (white): diagonal-forward black pieces only; a piece directly
  ahead is NOT a capture; never backwards.
- King: adjacent black pieces (even defended ones — the simplified
  movement model ignores enemy attacks); pieces two squares away are not.
- Castling, en passant, and promotion choices are NOT part of this
  exercise (promotion captures still count as captures of their square).

Movement is computed with python-chess as the authoritative engine
(`capturable_squares()`); no second movement engine exists in the
frontend.

## Defense irrelevance (explicit)

This exercise deliberately does NOT evaluate whether a capture is safe:

- A black piece defended by any number of black pieces is still a
  CORRECT answer when the hunter can capture it.
- A king may capture a defended neighbour (simplified movement model).
- Regression-tested at both levels: profile computation (defended king
  capture counted under `ignore-enemy-attacks`) and validation (stored
  answer accepted regardless of board defense).
- This is what distinguishes Exercise 3 from Exercise 4 (Hanging
  Pieces), which is entirely about defense.

## Question generation (`generator.py`)

Dynamic — never a fixed FEN list:

- Hunter type drawn uniformly from pawn/knight/bishop/rook/queen/king
  (data-driven `PIECE_TYPES`, no special-case chains).
- Exactly one WHITE hunter, 3–8 BLACK pieces (kinds p/n/b/r/q, never on
  illegal pawn ranks; no black king). No other white pieces at all.
- Deliberate (not purely random) skeletons per kind: 1–2 capturable
  targets on rays/L-shapes/diagonals/adjacent squares, ~60% with a
  shielded piece behind a slider capture, 1–3 close-but-wrong decoys
  (off-ray, non-L, ahead-of-pawn, two-away-from-king), padded to ≥3
  black pieces with provably non-capturable decoys.
- Every puzzle is VERIFIED by recomputation: non-zero mode requires a
  non-empty capture set, zero mode requires an empty one.
- Zero-capture positions are valid but throttled (~12%) so they occur
  occasionally without dominating.
- Pawns never on rank 1/8. Bounded retries (50 attempts); failure raises
  instead of looping.
- Persian prompt («کدام مهره‌های سیاه را می‌توان با این {piece} زد؟»),
  explanation, and one hint per piece kind; rating scales with capture
  count (750–1250 range).
- Persisted as a published `puzzles` row:
  `position_json={"from", "profile"}`,
  `answer_json={"squares", "from", "profile"}`. Identical
  (position, hunter) rows are reused, not duplicated; `exclude_ids`
  steers variety with bounded re-rolls.

## Hunter highlighting

The hunter square (from `position_json.from`, part of the task — NOT the
answer) renders with the shared `target` board state: sky-blue ring
(`outline-sky-400`), visible on light/dark squares, mobile/desktop,
without obscuring the SVG piece. Feedback states (green/amber/red)
overwrite it on collision. Capturable squares are never marked before
submission — the frontend never receives `answer_json`.

## Validation (`validator.py`)

Backend-authoritative exact set match (same contract as Exercises 1–2):

| Targets | Selection | Result |
|---|---|---|
| `{c4,f7,h5}` | `{c4,f7,h5}` (any order) | CORRECT |
| `{c4,f7,h5}` | `{}` | WRONG |
| `{c4,f7,h5}` | `{c4,f7}` | PARTIAL |
| `{c4,f7,h5}` | `{c4,f7,a1}` | PARTIAL |
| `{}` | `{}` | CORRECT |
| `{}` | `{a1}` | WRONG |

- CORRECT: selected set == target set (empty==empty included).
- PARTIAL: ≥1 correct selection with missed and/or wrong ones.
- WRONG: no correct selections (including any selection on zero-target).
- Duplicates normalized (sets); order irrelevant; malformed square
  names count as wrong, never crash. Selecting the hunter square
  itself, an empty square, or a shielded black piece is WRONG.
- Client-supplied `squares`/`from`/`fen` fields are ignored; grading
  always runs against the stored `answer_json`.
- Rule profiles stay data (`RULE_PROFILES`: `standard` via
  `legal_moves`, `ignore-enemy-attacks` via `pseudo_legal_moves`).
  Generated puzzles use `ignore-enemy-attacks`; the legacy seed rows
  use `standard` (their stored answers stay valid either way, since
  validation compares stored sets, never recomputes).

## Scoring (authoritative, per-square)

Exact formula, computed backend-side from the validation detail:

```text
score = (correct_selected × 5) − (missed_targets × 1) − (wrong_selected × 2)
```

with one explicit exception: a correctly answered zero-target question
(empty target set, empty selection) awards a +5 completion bonus instead
of 0.

Spec examples: `[c4,f7,h5]` all three → +15; `[c4,f7]` → +10 − 1 = +9;
`[c4,f7,a1]` → +10 − 2 = +8; nothing → −3 (negatives kept, never
clamped). Zero-target: `[]/[]` → CORRECT +5; `[]/[a1]` → WRONG −2.

- Registered via `register_scorer("captures", score_squares)`;
  computed independently of the result label.
- Never trusted from the client; malformed selections cost −2 each.

## Final report (Speed)

`GET /api/v1/captures/sessions/{id}/report` rebuilds the report from
stored attempts (refresh-safe):

- Summary: attempted / correct / partial / wrong / total score, plus
  average per puzzle and accuracy rendered client-side.
- Per-puzzle entries in answer order: prompt, result badge
  (درست/ناقص/اشتباه), score, missed/wrong counts, correct captures
  (revealed post-answer).

## Feedback

After submit: colored board rings + banner + per-puzzle score + counts
(درست / جا افتاده / اشتباه) + child-friendly legend:

- Green (`✓`): correct black pieces selected.
- Orange/amber (`!`): capturable black pieces missed.
- Red (`✕`): selected squares that cannot be captured.

In Speed Mode the banner shows for ~450ms and the loop auto-advances;
Practice keeps its manual «معمای بعدی» step.

## Persian / RTL rendering

Existing Design System typography (self-hosted Vazirmatn, `lang="fa"`
`dir="rtl"`, UTF-8). Page stays RTL; the chessboard island stays
`dir="ltr"` with a-file left in White orientation. Question
(«کدام مهره‌های سیاه را می‌توان با این {piece} زد؟») is prominent,
centered, RTL. Hint uses the compact circular `؟` button (44px hit
area, proper aria-label) with an overlay popover. New strings:
`captures.title`, `captures.emptyAllowed`.

## Security

- `answer_json`/capture squares/solution metadata never leave the
  server before submission — including inside prefetch buffers (covered
  by API tests).
- Grading and scoring use the stored answer only; client `fen`/
  `squares`/`from`/`score` fields are ignored (covered by tests).
- Only puzzles issued to a session can be submitted to it (404
  otherwise); the speed clock is server-authoritative (410 on expiry).

## API

| Method & path | Purpose |
|---|---|
| `POST /api/v1/captures/next` `{exclude_ids?}` | fresh random practice puzzle (`PuzzleOut`, no answer) |
| `POST /api/v1/captures/sessions` | open session (`preparing`, clock NOT running) |
| `POST /api/v1/captures/sessions/{id}/puzzles` `{count}` | prepare N buffer puzzles (`410` when expired; capped at 60) |
| `POST /api/v1/captures/sessions/{id}/start` | start the 60s clock (`409 buffer_not_ready` below 20) |
| `POST /api/v1/captures/sessions/{id}/next` | single session puzzle |
| `POST /api/v1/captures/sessions/{id}/submit` | graded answer + updated summary (`409` before start, `410` when expired) |
| `GET /api/v1/captures/sessions/{id}` | summary (auto-expires) |
| `GET /api/v1/captures/sessions/{id}/report` | authoritative per-puzzle report |
| `POST /api/v1/captures/sessions/{id}/finish` | end early + summary |
| `POST /api/v1/attempts` | standard attempt submit (practice) |
| `GET /api/v1/puzzles?exercise=captures` | legacy seed rows (read-only) |

Errors: `session_not_found` (404), `session_not_started` (409),
`session_expired` (410), `buffer_not_ready` (409),
`puzzle_not_in_session`/`puzzle_not_available` (404).

## Tests

- `tests/test_captures.py` — legacy seed capture rules/validation/API
  (updated: per-square scoring assertion, 2 targets → 10.0).
- `tests/test_captures_ex3.py` — spec coverage: rook
  (reachable/blocked/multiple), bishop (diagonal/blocked), queen
  (rank+diagonal/blocker), knight (valid/nearby-invalid/jump-ignores-
  blockers), pawn (diagonal/forward-not/backward-invalid), king
  (adjacent/two-away), defense-irrelevance regression (slider + king +
  validation level), set semantics (order/duplicates/malformed),
  hunter/empty/shielded selections are wrong, client fields ignored,
  exact scoring formula + spec examples, zero-target +5, generator
  validity (one hunter, 3–8 black, independent python-chess
  recomputation, all six kinds, zero + multi occurrence, blocker
  contrast, forced zero mode, bounded failure, persist/dedup), practice
  next + full speed lifecycle (20-buffer, 60s, no-leak, report-vs-
  attempts equality, foreign-puzzle rejection, expiry authority,
  pre-start refusal).
- Frontend (`npm test`, vitest): catalog practice/speed entries + URLs,
  direct mode entry, hunter highlight without answer leak,
  multi-select toggles, submit payload shape, feedback ring colors
  (green/amber/red), zero-target +5 display, practice advance, speed
  3-consecutive-submission reset, auto-advance with no next button,
  background refill continuity, preparing UI without buffer counts,
  expiry report rendering, compact `؟` hint button.

## Known limitations

- Speed sessions are per-exercise (`capture_speed_sessions`, mirroring
  `piece_speed_sessions` / `legal_speed_sessions`); a generic session
  table can replace all three when the pattern stabilises.
- Rating stays a stub: `rating_delta` is always None.
- Generated boards intentionally contain no kings (simplified movement
  model); king captures of defended neighbours count by design.
