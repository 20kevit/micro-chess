# Exercise 1 — Piece Recognition (تشخیص مهره)

MVP status: production-quality. The exercise asks the user to identify all
pieces of a specific type and color on a chess position (e.g. «تمام اسب‌های
سفید را پیدا کن»). Identifier: `piece-recognition`.

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
POST .../next → random puzzle      POST .../sessions → 60s session
   ↓                                     ↓
select squares (0..n) → بررسی جواب  loop: next → select → submit
   ↓                                     ↓
server validation → feedback → بعدی   410 on expiry → final summary
```

- The Practice and Speed buttons on the home page directly enter their
  corresponding exercise modes (`?mode=practice` / `?mode=speed`). There is
  no intermediate mode-selection screen; the buttons themselves are the
  mode selection.
- Board: tap to select, tap again to deselect, any count incl. zero.
  Submission happens ONLY via «بررسی جواب» — never on square click.
- Board locks while submitting / after submission; feedback shows states.

## Practice Mode

- Untimed. Each «معمای بعدی» calls `POST /api/v1/piece-recognition/next`
  which generates and persists a fresh random puzzle.
- Answers submit through the standard `POST /api/v1/attempts`
  (mode=practice, anonymous allowed, `rating_delta` always None).
- Anonymous attempts also append to browser localStorage
  (`lib/localProgress.ts`); the server is source of truth for accounts.
- Practice never terminates on zero-target questions (validator returns
  CORRECT for empty==empty).

## Speed Mode

- 60-second session (`SPEED_DURATION_S = 60` in `sessions.py`).
- `POST /api/v1/piece-recognition/sessions` → `{session_id, expires_at, ...}`.
- Loop: `POST .../sessions/{id}/next` → select → `POST .../sessions/{id}/submit`.
- The frontend shows a countdown + progress bar for UX, but the backend is
  authoritative: `submit`/`next` compare server time to stored `ends_at`
  and answer `410 session_expired` when the clock has run out.
- `POST .../sessions/{id}/finish` (or expiry) → summary:
  `attempted / correct / partial / wrong / score`.
- Each answer also persists as a normal `attempts` row (mode=practice),
  so history/analytics keep working; the session row only aggregates.
- Scoring reuses `scoring_engine.score_for` (correct=1.0, partial=0.5,
  else 0); no separate scoring system.

## Puzzle source

- Shared read-only `puzzles.db` (Lichess dump) via
  `app/modules/positions/repository.py`. Only the `FEN` column is used;
  `Moves`/`Rating`/`Themes` are ignored for correctness.
- The file is optional local data (see `PUZZLES_DB_PATH`, never committed).
  When absent/unreadable, a curated fallback FEN list is used.
- One row per call (`ORDER BY RANDOM() LIMIT 1`); the table is never fully
  loaded. Invalid/unparseable FENs are skipped (up to 25 tries).
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

## Feedback

After submit: colored banner (green/amber/red) + backend `feedback_key`
text + counts (درست / جا افتاده / اشتباه) + child-friendly legend:

- `✓` درست انتخاب کردی (correct)
- `✕` این مهره هدف نبود (wrong)
- `!` این مهره را جا انداختی (missed)

Board rings mirror the same three states; the correct-answer squares and
the Persian explanation are shown. Symbols are text markers, never chess
glyphs (pieces are always SVG).

## Scoring

`scoring_engine.score_for`: correct=1.0, partial=0.5, else 0. Speed summary
sums per-attempt scores. Practice attempts never set `rating_delta`
(rating engine still a stub; speed submits use mode=practice too).

## Hints

Shared mechanism: puzzle `hint_json.hints`, per-attempt `hints_used`
persisted on the attempt row. Hints never reveal full squares.

## API

| Method & path | Purpose |
|---|---|
| `POST /api/v1/piece-recognition/next` | fresh random practice puzzle (`PuzzleOut`, no answer) |
| `POST /api/v1/piece-recognition/sessions` | start 60s session |
| `POST /api/v1/piece-recognition/sessions/{id}/next` | session puzzle (`410` when expired) |
| `POST /api/v1/piece-recognition/sessions/{id}/submit` | graded answer + updated summary (`410` when expired) |
| `GET /api/v1/piece-recognition/sessions/{id}` | summary (auto-expires) |
| `POST /api/v1/piece-recognition/sessions/{id}/finish` | end early + summary |
| `POST /api/v1/attempts` | standard attempt submit (practice) |
| `GET /api/v1/puzzles?exercise=piece-recognition` | legacy seed rows (read-only) |

## Security

- `answer_json`/target squares/solution metadata never leave the server
  before submission (covered by API tests).
- Grading uses the stored answer only; client `fen`/`squares`/`target`
  fields in the answer payload are ignored (covered by tests).
- Only puzzles issued to a session can be submitted to it (404 otherwise).

## Edge cases

- Zero-target question + empty submit → CORRECT; practice continues.
- Invalid FEN rows in puzzles.db → skipped, never break the flow.
- Missing puzzles.db → fallback FENs (documented, tested).
- Late speed submit → 410, attempt NOT recorded, summary returned.
- Unknown session → 404. Finishing twice → idempotent.

## Tests

- `tests/test_piece_recognition.py` — validator incl. zero-target/king cases.
- `tests/test_positions_repository.py` — read-only source, invalid skip, fallback.
- `tests/test_piece_generator.py` — all 12 targets, 0/1/n targets, randomness, persistence.
- `tests/test_piece_speed_api.py` — no-leak, 60s config, expiry authority,
  summary accumulation, hints, override resistance.
- `tests/test_piece_attempts_api.py` — legacy seed + attempt flow (unchanged).

## Known limitations

- Generated puzzles accumulate as rows in `puzzles` (acceptable for MVP;
  a future cleanup/retention policy can prune anonymous session puzzles).
- `ORDER BY RANDOM()` on a very large puzzles.db is O(table): measured
  ~1.4s per fetch at 5.3M rows — acceptable for one fetch per puzzle in MVP,
  replace with indexed sampling if it ever shows up in profiling.
- Speed sessions are per-exercise (`piece_speed_sessions`); a generic
  session table can replace it when a second timed exercise lands.
- Rating stays a stub: `rating_delta` is always None.
