# Exercise 1 — Piece Recognition (تشخیص مهره)

Production v1 status. The exercise asks the user to identify all pieces of
a specific type and color on a chess position (e.g. «تمام اسب‌های سفید را
پیدا کن»). Identifier: `piece-recognition`.

## Purpose

Teach board vision: recognize piece shapes and colors and map them to
squares. First vertical slice of the platform; its patterns (generator,
sessions, play loop, design tokens) are the template for later exercises.

## User flow

```text
Main Page (/)
   ↓  تشخیص مهره card
   ├── تمرینی (?mode=practice)      └── سرعتی (?mode=speed)
   ↓                                     ↓
first puzzle loads immediately     prepare ≥20 puzzles (no clock)
   ↓                                     ↓
select → بررسی جواب → instant      clock starts → 60s session
feedback → prefetched next               ↓
                                   per-puzzle feedback → queued next
                                              ↓
                                   authoritative final report
```

- The Practice and Speed buttons on the home page directly enter their
  corresponding exercise modes. There is no intermediate mode-selection
  screen; the buttons themselves are the mode selection.
- Board: tap to select, tap again to deselect, any count incl. zero.
  Submission happens ONLY via «بررسی جواب» — never on square click.
- While submitting, the button locks and duplicate submits are refused.
- Board locks while submitting / after submission; feedback shows states.

## Practice Mode

- Untimed. Entering the mode immediately loads the first puzzle.
- Client prefetch buffer (current + next): while the user solves the
  current puzzle, the next one is prepared in the background. Pressing
  «معمای بعدی» swaps to the already-ready puzzle and refills the buffer.
  Normal transitions show no loading state.
- Fresh puzzles come from `POST /api/v1/piece-recognition/next` (accepts
  `exclude_ids` to avoid just-shown repeats).
- Answers submit through the standard `POST /api/v1/attempts`
  (mode=practice, anonymous allowed, `rating_delta` always None).
- Stale-request protection: a generation counter + mounted guard means a
  slow/old response can never overwrite the current puzzle; prefetch
  failures never destroy the active puzzle (on-demand fallback).
- Anonymous attempts also append to browser localStorage
  (`lib/localProgress.ts`); the server is source of truth for accounts.
- Every answered puzzle persists as an `attempts` row, so nothing is lost
  when the user exits (no separate practice summary feature).
- Practice never terminates on zero-target questions (validator returns
  CORRECT for empty==empty).

## Speed Mode

Lifecycle: `preparing` → `active` → `finished`/`expired`.

1. Enter → a session opens in `preparing` (NO clock runs).
2. The client prepares **at least 20 puzzles** (`POST .../sessions/{id}/puzzles`
   `{"count": 20}`) with a visible progress state.
3. `POST .../sessions/{id}/start` starts the authoritative 60-second clock
   (refused with `409 buffer_not_ready` below 20 buffered). Preparation
   time is never billed to the session.
4. Loop over the client queue: select → submit → ~450ms board feedback
   (green/red/orange) → AUTOMATIC advance to the next queued puzzle. There
   is deliberately NO manual "next puzzle" button in Speed Mode; a single
   lock held from submit through the transition refuses double-submits,
   the 60s timer keeps running, and expiry mid-transition routes to the
   report.
5. Expiry/finish → `GET .../sessions/{id}/report`: the complete
   authoritative report (see below).

- The frontend shows a countdown + progress bar for UX, but the backend is
  authoritative: `submit`/`next`/`puzzles` compare server time to stored
  `ends_at` and answer `410 session_expired` when the clock has run out.
- Each answer also persists as a normal `attempts` row (mode=practice),
  so history/analytics keep working; the session row only aggregates.
- Scoring uses the registered per-square scorer (below), summed into the
  session total. No separate scoring system.

## Puzzle source

- Shared read-only `puzzles.db` (Lichess dump) via
  `app/modules/positions/repository.py`. Only the `FEN` column is used;
  `Moves`/`Rating`/`Themes` are ignored for correctness.
- The file is optional local data (see `PUZZLES_DB_PATH`, never committed).
  When absent/unreadable, a curated fallback FEN list is used.
- One row per call via indexed rowid probing; the table is never fully
  loaded. Invalid/unparseable FENs are skipped (bounded retries).
- No Exercise-1-specific copy of the database exists; future exercises reuse
  the same repository (`puzzles.db → repository → generator → exercise`).

## FEN usage

- Server validates every FEN with python-chess before use.
- The FEN travels to the client ONLY as `Puzzle.fen` for rendering.
  Client-provided FENs are never trusted for grading.

## Question generation (`generator.py`)

- Uniform random pick among the 12 canonical targets
  (`CANONICAL_TARGETS`: 6 kinds × white/black), deliberately unbiased so
  zero-target questions occur naturally.
- Target squares computed server-side (`squares_for_target`).
- Persian prompt (`prompt_for_target`, e.g. «تمام رخ‌های سیاه را پیدا کن»),
  explanation (lists squares, or teaches that selecting nothing is correct),
  and one generic hint per piece kind.
- Persisted as a published `puzzles` row:
  `position_json={"target": key}`, `answer_json={"squares": [...], "target": key}`.
  No new puzzle table; switching sources later only touches the repository.

## Target generation

Authoritative squares come from the stored `answer_json`. The puzzle
response (`PuzzleOut`) never contains `answer_json`.

## Validation (`validator.py`)

Backend-authoritative exact set match:

| Target | Selection | Result |
|---|---|---|
| `{e4}` | `{e4}` | CORRECT |
| `{e4}` | `{}` | WRONG |
| `{e4}` | `{e4, d5}` | WRONG extra → PARTIAL (some correct) / WRONG (none correct) |
| `{}` | `{}` | CORRECT |
| `{}` | `{e4}` | WRONG |

- CORRECT: selected set == target set (empty==empty included).
- PARTIAL: ≥1 correct selection with missed and/or wrong ones.
- WRONG: no correct selections.
- Malformed square names count as wrong, never crash.
- Legacy seed targets (`queen-any`, `minor-white/black`) still validate;
  the generator only emits the 12 canonical ones.

## Result states

Preserved validator semantics (score is always computed independently):

- CORRECT: selected set exactly equals the target set (empty==empty included).
- PARTIAL: ≥1 correct selection with missed and/or wrong ones.
- WRONG: no correct selections.

## Final report (Speed)

`GET /api/v1/piece-recognition/sessions/{id}/report` rebuilds the report
from stored attempts (refresh-safe; the UI can never fabricate results):

- Summary: attempted / correct / partial / wrong / total score, plus
  average per puzzle and accuracy rendered client-side (hidden when 0 answered).
- Per-puzzle entries in answer order: prompt, result badge (درست/ناقص/اشتباه),
  score, missed/wrong counts, and the correct squares (revealed post-answer).

## Feedback

After submit: colored banner (green/amber/red) + backend `feedback_key`
text + per-puzzle score + counts (درست / جا افتاده / اشتباه) +
child-friendly legend:

- `✓` درست انتخاب کردی (correct → green rings)
- `✕` این مهره هدف نبود (wrong → red rings)
- `!` این مهره را جا انداختی (missed → orange/amber rings)

Board rings mirror the same three states; the correct-answer squares and
the Persian explanation are shown. Symbols are text markers, never chess
glyphs (pieces are always SVG). In Speed Mode the banner shows for
~450ms (`FEEDBACK_MS`) and the loop auto-advances — no manual button;
Practice keeps its manual «معمای بعدی» step.

## Persian / RTL rendering

Root cause fixed (was: declared-but-never-loaded typeface): the Design
System specifies `Vazirmatn` first in the font stack, but no font asset
was bundled, so browsers silently fell back to arbitrary system fonts.
The fix loads self-hosted Vazirmatn (Fontsource, weights 400/700/900,
`font-display: swap`, arabic+latin subsets) through the existing
`index.css` typography mechanism — no per-component special font.

Verified encoding chain (all must hold; re-check if Persian ever breaks):

- Source files (`fa.ts`, backend prompts): UTF-8, Persian block intact —
  fix sources, never mask in CSS.
- API: FastAPI JSON `application/json`, UTF-8 decoded; prompts verified
  byte-level with 24+ Persian chars and no `�`/mojibake markers.
- DB: SQLite TEXT (UTF-8); prompts round-trip byte-identical.
- HTML: `<html lang="fa" dir="rtl">`, `<meta charset="UTF-8">`; page stays
  RTL, chessboard islands stay `dir="ltr"`, square names stay Latin.

## Scoring (authoritative, per-square)

Exact formula, computed backend-side from the validation detail:

```text
score = (correct_selected × 5) − (missed_targets × 1) − (wrong_selected × 2)
```

with one explicit exception: a correctly answered zero-target question
(empty target set, empty selection) awards a +5 completion bonus instead
of 0. The bonus applies ONLY when the result is CORRECT and all three
detail lists are empty — that signature uniquely means
empty-target/empty-selection.

Example from the spec (`target=[e4,g7,b2]`, `selected=[e4,g7,d5]`):
`2×5 − 1×1 − 1×2 = 7`. Further pinned examples: `[]/[]` → CORRECT +5;
`[]/[e4]` → WRONG −2; `[e4]/[e4]` → +5; `[e4]/[]` → −1;
`[e4,e5]/[e4]` → +4; `[e4,e5]/[e4,e6]` → +2.

- Registered via `register_scorer("piece-recognition", score_squares)`;
  other exercises keep the shared correct=1.0/partial=0.5/else-0 default.
- Never trusted from the client; may be negative (e.g. −4); never clamped.
- Computed independently of the result label (CORRECT/PARTIAL/WRONG).
- Each wrong square on a zero-target question costs −2 with no bonus.
- Malformed selections count as wrong squares (−2 each).

## Zero-target scoring

```text
target = {} , selected = {}  → CORRECT, score +5
target = {} , selected = {e4} → WRONG, score −2
```

## Hints

Shared mechanism: puzzle `hint_json.hints`, per-attempt `hints_used`
persisted on the attempt row. Hints never reveal full squares.

## Practice reporting

No fixed length and no separate summary screen: every answered puzzle is a
persisted `attempts` row, and the UI keeps a running solved/correct/score
tally. Exiting loses nothing.

## API

| Method & path | Purpose |
|---|---|
| `POST /api/v1/piece-recognition/next` `{exclude_ids?}` | fresh random practice puzzle (`PuzzleOut`, no answer) |
| `POST /api/v1/piece-recognition/sessions` | open session (`preparing`, clock NOT running) |
| `POST /api/v1/piece-recognition/sessions/{id}/puzzles` `{count}` | prepare N buffer puzzles (`410` when expired; capped at 60) |
| `POST /api/v1/piece-recognition/sessions/{id}/start` | start the 60s clock (`409 buffer_not_ready` below 20) |
| `POST /api/v1/piece-recognition/sessions/{id}/next` | single session puzzle |
| `POST /api/v1/piece-recognition/sessions/{id}/submit` | graded answer + updated summary (`409` before start, `410` when expired) |
| `GET /api/v1/piece-recognition/sessions/{id}` | summary (auto-expires) |
| `GET /api/v1/piece-recognition/sessions/{id}/report` | authoritative per-puzzle report |
| `POST /api/v1/piece-recognition/sessions/{id}/finish` | end early + summary |
| `POST /api/v1/attempts` | standard attempt submit (practice) |
| `GET /api/v1/puzzles?exercise=piece-recognition` | legacy seed rows (read-only) |

Submit responses carry the per-puzzle `score` plus `detail`
(`correct`/`missed`/`wrong`); `score` is authoritative and may be negative.
Errors: `session_not_found` (404), `session_not_started` (409),
`session_expired` (410), `buffer_not_ready` (409),
`puzzle_not_in_session`/`puzzle_not_available` (404).

## Security

- `answer_json`/target squares/solution metadata never leave the server
  before submission — including inside prefetch buffers (covered by API tests).
- Grading and scoring use the stored answer only; client `fen`/`squares`/
  `target`/`score` fields are ignored (covered by tests).
- Only puzzles issued to a session can be submitted to it (404 otherwise).

## Puzzle source & sampling

- Shared read-only `puzzles.db`, FEN column only; invalid rows skipped.
- Indexed rowid probing (no full-table scans): measured milliseconds per
  fetch even at 5.3M rows, which makes 20-puzzle buffers and background
  refill cheap.
- Missing/unreadable source → curated fallback FENs (documented, tested).

## Generated puzzle persistence

- Identical (position, question) rows are reused, not duplicated; buffers
  additionally exclude already-issued ids, so one session buffer stays
  duplicate-free (best-effort, bounded re-rolls).
- Each answered puzzle keeps its row (referenced by attempts and the
  server-rebuilt report). Growth is ~1 small row per answered puzzle —
  the same order as the attempt rows themselves. A future retention policy
  may prune rows whose reports are no longer needed; reports rebuild from
  attempts, so pruning never corrupts finished summaries.

## Edge cases

- Zero-target question + empty submit → CORRECT, score 0; practice continues.
- Invalid FEN rows in puzzles.db → skipped, never break the flow.
- Missing puzzles.db → fallback FENs (documented, tested).
- Prefetch failure → silent; current puzzle unaffected, on-demand fallback.
- Stale prefetch response → discarded by generation guard, never applied.
- Submit before speed start → 409; late speed submit → 410, attempt NOT recorded.
- Start with <20 buffered → 409 `buffer_not_ready`.
- Unknown session → 404. Finishing twice → idempotent.
- Zero answered in report → explicit empty state, no misleading stats.

## Tests

- `tests/test_piece_recognition.py` — validator incl. zero-target/king cases.
- `tests/test_piece_scoring.py` — 5/−1/−2 formula, spec example (=7),
  zero-target, negatives, label-independence, registry default intact.
- `tests/test_positions_repository.py` — read-only source, fast sampling,
  invalid skip, fallback, pinned-path semantics, real-DB integration (skipped
  when absent).
- `tests/test_piece_generator.py` — all 12 targets, 0/1/n targets,
  randomness, persistence, dedup-reuse, exclude steering.
- `tests/test_piece_speed_api.py` — no-leak, prepare≥20/start lifecycle,
  60s config, expiry authority, report-vs-attempts equality, summary
  accumulation, hints, override resistance.
- `tests/test_piece_attempts_api.py` — legacy seed + per-square attempt flow.
- Frontend (`npm test`, vitest): catalog mode URLs, direct mode entry,
  select/deselect/submit, empty submit, 20-buffer-before-clock, expiry
  report rendering.

## Known limitations

- Speed sessions are per-exercise (`piece_speed_sessions`); a generic
  session table can replace it when a second timed exercise lands.
- Rating stays a stub: `rating_delta` is always None.
- Practice has attempt history but no summary screen (by design; §18).
