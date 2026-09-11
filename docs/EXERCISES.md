# Exercises (official roadmap — single source of truth)

Roadmap (final numbering):

1. Piece Recognition (`piece-recognition`, تشخیص مهره)
2. Legal Destinations (`legal-destinations`, مقصدهای قانونی)
3. Captures (`captures`, گرفتن مهره‌ها)
4. Undefended Pieces (`undefended-pieces`, مهره‌های بی‌دفاع)
5. Giving Check (`give-check`, کیش دادن)
6. Get Out of Check (`get-out-of-check`, رفع کیش)
7. Pathfinding (`pathfinding`, مسیریابی)
8. Pathfinding with Obstacles (`pathfinding-obstacles`, مسیریابی با مانع)
9. Balance Scale (`balance-scale`, ترازو)
10. Which Side is Heavier? (`heavier-side`, کدام طرف سنگین‌تر است؟)
11. Pin (`pin`, آچمز)
12. Memorization Board (`chinese-board`, صفحه‌ی حفظی — displayed as
    صفحه‌ی حفظی; the `chinese-board` slug is kept for routes/API/DB only)
13. Is it Checkmate? (`is-checkmate`, آیا مات است؟) — ADMIN-BLOCKED:
    needs an Admin workflow for entering/managing positions; do not
    continue development for now.
14. Blindfold Square Vision (`blindfold-square-vision`, خانه‌یابی ذهنی)
15. Blindfold Calculation (`blindfold-calculation`, محاسبه‌ی ذهنی)
16. Mental Opening (`opening-traps`, گشایش ذهنی) — ADMIN-BLOCKED:
    needs Admin-entered positions; do not continue development for now.
17. Reverse Opening (`reverse-opening`, گشایش معکوس) — ADMIN-BLOCKED:
    needs Admin-entered positions; do not continue development for now.
    The former `opening-move-reconstruction` implementation was
    consolidated under this slug; do not keep two exercises.
18. Trapped Piece (`trapped-pieces`, مهره‌ی گرفتار)
19. REMOVED — `avoid-stalemate` (deleted from the project, no placeholder)
20. REMOVED — `rule-of-the-square` (deleted from the project, no placeholder)
21. Castling Rights (`castling-rights`, حقوق قلعه‌رفتن) — ADMIN-BLOCKED:
    needs Admin-entered positions; do not continue development for now.

Removed (no placeholders left): the former Exercises 5 (Hanging
Pieces, `hanging-pieces`) and 6 (Equal Attackers & Defenders,
`equal-attackers-defenders`); `memory-board` (superseded by the
Memorization Board, Exercise 12); `opening-move-reconstruction`
(renamed to `reverse-opening`); `avoid-stalemate`; `rule-of-the-square`.
Removed means removed: backend modules, frontend pages, routes, catalog
entries, tests, seeds, and docs are all gone.

## How to add an exercise (later)

1. Add `Exercise` row (slug, Persian title, description).
2. Write validator `(puzzle_answer, attempt) -> ValidationResult` in the exercise's module.
3. `register_validator(slug, fn)` at startup.
4. Add backend tests (validation, scoring edge cases, custom rules).
5. Add frontend page + Persian strings; call `POST /api/v1/attempts`; render `feedback_key` via `t()`.

## First slice

**Piece Recognition** — MVP (`piece-recognition`). Full spec:
`docs/exercises/01-piece-recognition.md`.

- Route: `/exercises/piece-recognition` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons.
- Play loop: `frontend/src/components/exercise/PieceRecognitionPlay.tsx`
  (practice + speed, timer, hints, feedback legend); correctness, scoring,
  and the speed clock stay backend-authoritative.
- Position source: shared `puzzles.db` via `positions/repository.py`
  (read-only, FEN only, fallback FENs when absent); per-puzzle questions
  built by `piece_recognition/generator.py` (12 canonical color×kind
  targets, zero-target questions valid, answers server-side only).
- Validator: `backend/app/modules/piece_recognition/validator.py` (exact
  set match incl. empty==empty; malformed squares count as wrong).
- Practice: `POST /api/v1/piece-recognition/next` issues fresh random
  published puzzles (identical rows reused; `exclude_ids` steers variety);
  the client keeps a current+next prefetch buffer. Answers go through
  standard `POST /api/v1/attempts`.
- Speed: `piece_recognition/sessions.py` + `router.py` (open → prepare ≥20
  → start 60s clock → submit loop with ~450ms auto-advance, no manual next
  → server-rebuilt per-puzzle report; per-answer rows reuse `attempts`).
- Scoring: registered per-square scorer (+5 correct / −1 missed / −2 wrong,
  +5 bonus for correctly answered zero-target, negatives kept, independent
  of the CORRECT/PARTIAL/WRONG label).
- Seed: `python -m app.modules.piece_recognition.seed` (15 legacy demo
  puzzles, still served read-only; covered by tests).

## Second slice

**Legal Destinations** — IMPLEMENTED (`legal-destinations`). Full spec:
`docs/exercises/02-legal-destinations.md`.

- Route: `/exercises/legal-destinations` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons directly
  (no intermediate mode screen), same pattern as Exercise 1.
- Play loop: `frontend/src/components/exercise/LegalDestinationsPlay.tsx`
  (practice + speed reusing `PieceGameLayout` shell, timer, hints, feedback;
  target piece highlighted via the shared `target` board state, destinations
  server-authoritative); correctness, scoring, and the speed clock stay
  backend-authoritative.
- Position source: dynamic white-only generator
  (`legal_destinations/generator.py` — uniform target type, exactly one
  white king, 2–6 deliberately placed blockers, no black pieces/king,
  zero-target possible but throttled, answers server-side only).
- Validator: `backend/app/modules/legal_destinations/validator.py` (exact
  set match incl. empty==empty; duplicates/order-insensitive; malformed
  squares count as wrong). Rule profiles are data (`RULE_PROFILES`:
  `standard` via `legal_moves`, `ignore-enemy-attacks` via
  `pseudo_legal_moves`); generated positions use `ignore-enemy-attacks`.
- Practice: `POST /api/v1/legal-destinations/next` issues fresh random
  published puzzles (identical rows reused; `exclude_ids` steers variety);
  the client keeps a current+next prefetch buffer. Answers go through
  standard `POST /api/v1/attempts`.
- Speed: `legal_destinations/sessions.py` + `router.py` (open → prepare ≥20
  → start 60s clock → submit loop with ~450ms auto-advance, no manual next
  → server-rebuilt per-puzzle report; per-answer rows reuse `attempts`).
- Scoring: registered per-square scorer (+5 correct / −1 missed / −2 wrong,
  +5 bonus for correctly answered zero-target, negatives kept, independent
  of the CORRECT/PARTIAL/WRONG label).
- Seed: `python -m app.modules.legal_destinations.seed` (15 legacy demo
  puzzles incl. captures/black pieces/both profiles, still served
  read-only; covered by tests).

## Third slice

**Captures** — IMPLEMENTED (`captures`). Full spec:
`docs/exercises/03-captures.md`.

- Route: `/exercises/captures` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons directly
  (no intermediate mode screen), same pattern as Exercises 1–2.
- Play loop: `frontend/src/components/exercise/CapturesPlay.tsx`
  (practice + speed reusing `PieceGameLayout` shell, timer, hints, feedback;
  hunter highlighted via the shared `target` board state, capturable
  squares server-authoritative); correctness, scoring, and the speed clock
  stay backend-authoritative.
- Position source: dynamic hunter-vs-black generator
  (`captures/generator.py` — uniform hunter type, exactly one white
  hunter, 3–8 black pieces with deliberate capturable/shielded/decoy
  patterns, no kings, zero-capture throttled, answers server-side only).
- Defense is explicitly irrelevant: answers use the
  `ignore-enemy-attacks` profile (pseudo-legal captures), so defended
  black pieces stay correct. There are no king hunters (a king cannot
  capture a defended piece); hunter kinds are pawn/knight/bishop/
  rook/queen.
- Validator: `backend/app/modules/captures/validator.py` (exact set
  match incl. empty==empty; duplicates/order-insensitive; malformed
  squares count as wrong). Rule profiles are data (`RULE_PROFILES`:
  `standard` via `legal_moves`, `ignore-enemy-attacks` via
  `pseudo_legal_moves`); generated positions use `ignore-enemy-attacks`,
  legacy seed rows keep `standard`.
- Practice: `POST /api/v1/captures/next` issues fresh random published
  puzzles (identical rows reused; `exclude_ids` steers variety); the
  client keeps a current+next prefetch buffer. Answers go through
  standard `POST /api/v1/attempts`.
- Speed: `captures/sessions.py` + `router.py` (open → prepare ≥20 →
  start 60s clock → submit loop with ~450ms auto-advance, no manual next
  → server-rebuilt per-puzzle report; per-answer rows reuse `attempts`).
- Scoring: registered per-square scorer (+5 correct / −1 missed / −2 wrong,
  +5 bonus for correctly answered zero-target, negatives kept, independent
  of the CORRECT/PARTIAL/WRONG label).
- Seed: `python -m app.modules.captures.seed` (15 legacy demo puzzles,
  still served read-only; covered by tests).

## Removed slices (no placeholders)

**Hanging Pieces** (`hanging-pieces`, former Exercise 5) and **Equal
Attackers & Defenders** (`equal-attackers-defenders`, former Exercise 6)
were completely removed: backend modules, frontend pages, routes,
catalog entries, tests, and docs. Everything below moved two numbers
back; Exercises 1–4 are untouched.

## Fifth slice

**Giving Check** — IMPLEMENTED (`give-check`). Full spec:
`docs/exercises/05-giving-check.md`.

- Route: `/exercises/give-check` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons
  directly (no intermediate mode screen), same pattern as Exercises 1–4.
- Play loop: `frontend/src/components/exercise/GivingCheckPlay.tsx`
  (practice + speed reusing the `PieceGameLayout` shell, timer, hints,
  feedback; multi-arrow board layer in `components/chess/ChessBoard.tsx`
  with press-drag-release drawing, per-arrow remove/promotion, toned
  feedback arrows); correctness, scoring, and the speed clock stay
  backend-authoritative.
- Position source: shared `puzzles.db` via `positions/repository.py`
  (read-only, FEN only, fallback FENs when absent), exactly like
  Exercise 4; per-puzzle answers built server-side by
  `give_check/generator.py` (bounded 25-candidate sampling that rejects
  positions with either king in check and prefers non-empty answers
  while keeping zero-target valid, answers server-side only).
- Rule: every legal non-King move (UCI) that leaves the opponent king
  in check, evaluated for White AND Black regardless of side to move —
  direct, capture, discovered (moving piece's from→to),
  double (one arrow), promotion (distinct choices), en passant;
  kings/castling never answers.
- Validator: `backend/app/modules/give_check/validator.py` (exact UCI
  set match incl. empty==empty; direction-sensitive,
  duplicates/order-insensitive; malformed arrows count as wrong).
- Practice: `POST /api/v1/giving-check/next` issues fresh random
  published puzzles (identical FEN rows reused; `exclude_ids` steers
  variety); the client keeps a current+next prefetch buffer. Answers go
  through standard `POST /api/v1/attempts`.
- Speed: `give_check/sessions.py` + `router.py` (open → prepare ≥20 →
  start 60s clock → submit loop with ~450ms auto-advance, no manual next
  → server-rebuilt per-puzzle report; per-answer rows reuse `attempts`).
- Scoring: registered per-move scorer (+5 correct / −1 missed / −2 wrong,
  +5 bonus for correctly answered zero-target, negatives kept, independent
  of the CORRECT/PARTIAL/WRONG label).

## Sixth slice

**Get Out of Check** — IMPLEMENTED (`get-out-of-check`, Exercise 6),
official Persian title `رفع کیش` (never `فرار از کیش`).

- Route: `/exercises/get-out-of-check` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons directly
  (no intermediate mode screen), same pattern as Exercises 1–5.
- Play loop: `frontend/src/components/exercise/GetOutOfCheckPlay.tsx`
  (practice + speed reusing the `PieceGameLayout` shell, timer, hints,
  feedback; multi-arrow board layer in `components/chess/ChessBoard.tsx`
  with press-drag-release drawing, per-arrow remove/promotion, toned
  feedback arrows — the same arrow system as Giving Check, no second
  implementation); correctness, scoring, and the speed clock stay
  backend-authoritative. Persian prompt:
  «تمام حرکت‌هایی را پیدا کن که کیش را رفع می‌کنند.»
- Position source: dedicated synthetic generator
  (`get_out_of_check/generator.py` — parametric families with rejection
  sampling: rook 22 / queen 22 / bishop 16 / knight 16 / pawn 10 /
  double 14; White king placed first, checker(s) per family, White
  helpers + Black extras, then verified: White in check, NOT checkmate,
  ≥1 escape, ≤12 escapes, exactly one checker for single families,
  king-moves-only escapes for doubles; answers server-side only and
  always derivable from the stored FEN, never a stored move list).
- Rule: every legal White move (UCI) after which White's own king is no
  longer in check — capture the checker, block the line, or move the
  king; one distinct move is one answer. Genuine double checks accept
  only king moves (non-king moves leave the second checker attacking).
  Positions not starting in check are invalid: every submission is WRONG
  (no zero-target bonus; a valid puzzle always has ≥1 escape).
- Validator: `backend/app/modules/get_out_of_check/validator.py` (exact
  UCI set match; direction-sensitive, duplicates/order-insensitive;
  plain UCI strings and a legacy single-move shape accepted; malformed
  arrows count as wrong).
- Practice: `POST /api/v1/get-out-of-check/next` issues fresh random
  published puzzles (identical FEN rows reused; `exclude_ids` steers
  variety); the client keeps a current+next prefetch buffer. Answers go
  through standard `POST /api/v1/attempts`.
- Speed: `get_out_of_check/sessions.py` + `router.py` (open → prepare ≥20
  → start 60s clock → submit loop with ~450ms auto-advance, no manual next
  → server-rebuilt per-puzzle report; per-answer rows reuse `attempts`).
- Scoring: registered per-move scorer (+5 correct / −2 missed / −3 wrong,
  negatives kept, independent of the CORRECT/PARTIAL/WRONG label).
- Seed: `python -m app.modules.get_out_of_check.seed` (15 hand-designed
  puzzles covering king escapes, captures, blocks, knight/pawn checks,
  doubles, pinned and discovered-fail cases, single/multi answers and a
  black-to-move position; every example independently verified at seed time).

## Seventh slice (Exercise 7)

**Pathfinding** — IMPLEMENTED (`pathfinding`, simple version). Full spec:
`docs/exercises/06-pathfinding.md`.

- Route: `/exercises/pathfinding` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons directly
  (no intermediate mode screen), same pattern as Exercises 1–5.
- Play loop: `frontend/src/components/exercise/PathfindingPlay.tsx`
  (practice + speed reusing the `PieceGameLayout` shell, timer, hints,
  feedback; one white knight/bishop/rook/queen walks to a star on an
  empty board — no king, no enemies, no captures; drag primary,
  click-to-move supported, piece stays selected, 220ms practice /
  110ms speed glide, illegal buzz + 700ms red flash; arrival
  auto-submits `{path, illegal_attempts}`); correctness, optimal counts,
  scoring, and the speed clock stay backend-authoritative.
- Position source: dynamic weighted generator
  (`pathfinding/generator.py` — knight 50 / bishop 20 / rook 20 /
  queen 10, uniform distinct start/target, BFS-verified reachable with
  stored `optimal_moves`, trivial-1-move throttled, answers server-side
  only). Movement geometry is pure (`moves.py`); BFS minimizes piece
  moves; no route is ever enforced.
- Validator: `backend/app/modules/pathfinding/validator.py` (exact
  path replay: correct iff every step is legal geometry AND the path
  ends on the star; single-step oracle at `POST /api/v1/pathfinding/step`
  with post-completion rejection).
- Practice: `POST /api/v1/pathfinding/next` issues fresh random
  published puzzles (identical rows reused; `exclude_ids` steers variety);
  the client keeps a current+next prefetch buffer. Answers go through
  standard `POST /api/v1/attempts`.
- Speed: `pathfinding/sessions.py` + `router.py` (open → prepare ≥20 →
  start 60s clock → walk-to-star loop with ~400ms auto-advance, no manual
  next → server-rebuilt per-puzzle report; per-answer rows reuse
  `attempts`).
- Scoring: registered scorer (`optimal×5 − extra×2 − illegal×3`,
  negatives kept, independent of the CORRECT/WRONG label).
- Seed: `python -m app.modules.pathfinding.seed` (15 weighted puzzles
  from the generator with a fixed seed, still served read-only).
- Note: the older obstacle/enemy-control pathfinding behavior that
  previously lived under this slug was replaced by this simple version;
  obstacle concepts move to future Exercise 7 and were not carried over.

## Eighth slice (Exercise 8)

**Pathfinding with Obstacles** — IMPLEMENTED (`pathfinding-obstacles`,
obstacle/enemy-piece pathfinding). Full spec:
`docs/exercises/07-pathfinding-obstacles.md`.

- Route: `/exercises/pathfinding-obstacles` with `?mode=practice`
  (untimed) and `?mode=speed` (60s session); card renders both entry
  buttons directly (no intermediate mode screen), same pattern as
  Exercises 1–6.
- Play loop: `frontend/src/components/exercise/PathfindingObstaclesPlay.tsx`
  (practice + speed reusing the `PieceGameLayout` shell, timer, hints,
  feedback; one white knight/bishop/rook/queen walks to a star among
  1–5 black enemies — no kings at all; drag primary, click-to-move
  supported, piece stays selected, 220ms practice / 110ms speed glide,
  illegal buzz + 700ms red flash; arrival auto-submits
  `{path, illegal_attempts}`); correctness, optimal counts, scoring,
  and the speed clock stay backend-authoritative.
- Position source: dynamic solved generator
  (`pathfinding_obstacles/generator.py` — knight 50 / bishop 20 /
  rook 20 / queen 10 with per-kind retries, 2–10 optimal moves,
  capture-or-detour meaningfulness gate, BFS-verified reachable with
  stored `optimal_moves`, answers server-side only). Rules live in one
  authoritative layer (`transitions.py`: movement + blocking +
  destination safety + undefended-only captures, safety evaluated on
  the post-move board so uncoverings are illegal); BFS searches
  complete board states, never white squares alone.
- Validator: `backend/app/modules/pathfinding_obstacles/validator.py`
  (stateful path replay with capture updates; correct iff every step
  is a legal transition AND the path ends on the star; single-step
  oracle at `POST /api/v1/pathfinding-obstacles/step` rebuilds the
  live state from the client FEN with server-stored kind/target and
  returns updated FEN + `reached` + `captured`, with post-completion
  rejection).
- Practice: `POST /api/v1/pathfinding-obstacles/next` issues fresh
  solved puzzles (identical rows reused; `exclude_ids` steers
  variety); the client keeps a current+next prefetch buffer. Answers
  go through standard `POST /api/v1/attempts`.
- Speed: `pathfinding_obstacles/sessions.py` + `router.py` (open →
  prepare ≥20 → start 60s clock → walk-to-star loop with ~400ms
  auto-advance, no manual next → server-rebuilt per-puzzle report;
  per-answer rows reuse `attempts`).
- Scoring: registered scorer (`optimal×5 − extra×2 − illegal×3`,
  negatives kept, independent of the CORRECT/WRONG label).
- Seed: `python -m app.modules.pathfinding_obstacles.seed` (15 solved
  puzzles from the generator with a fixed seed, still served
  read-only).

## Pin (Exercise 11)

**Pin** — IMPLEMENTED (`pin`, Exercise 11, آچمز).

- Route: `/exercises/pin` (shared `ExercisePlay` square-selection loop with
  `requiredSelection: 3` + `orderedSelection`: the user taps the three
  pieces forming the pin in [pinner, pinned, behind] order — no move, no
  arrows, no pin-type question).
- Validator: `backend/app/modules/pin/validator.py` (value-gated classical
  pins recomputed from the stored FEN: absolute when behind is the King,
  relative only when behind is strictly more valuable P=1 N=3 B=3 R=5 Q=9;
  skewers and equal-value lines rejected; kings never pinned; CORRECT only
  for the exact ordered triplet; FEN travels in the server-only
  `answer_json`, never exposed).
- Seed: `python -m app.modules.pin.seed` (15 hand-designed positions that
  already contain exactly one pin — absolute/relative, all three sliders,
  queen/pawn/knight pinned, both colors pinning; every entry verified for
  uniqueness with an independent re-scan; legacy move-based rows archived,
  never hard-deleted).
- Scoring: shared default (correct=1.0, else 0); no speed sessions.

## Ninth slice

**Balance Scale** — IMPLEMENTED (`balance-scale`, Exercise 9, ترازو).
Full spec: `docs/exercises/09-balance-scale.md`. Rewritten from the
earlier bank-to-pan prototype into the dedicated minimum-pieces scale:

- Route: `/exercises/balance-scale` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons directly
  (no intermediate mode screen), same pattern as Exercises 1–7.
- Play loop: dedicated `BalanceScalePlay` (practice + speed) over the
  `BalanceScaleView` scale (tilting beam + hanging pyramid pans + unlimited
  inventory, SVG pieces, no chessboard); correctness, optimal counts,
  scoring, and the speed clock stay backend-authoritative.
- Position source: dynamic random generator
  (`balance_scale/generator.py` — 4–10 black pieces, tier-mixed targets,
  DP-verified solvable within 10 pieces, answers server-side only).
- Rule: exact material equality; no Submit button — balance auto-submits
  `{pieces}` once. Any exact combination solves; fewer pieces score more.
- Validator: `backend/app/modules/balance_scale/validator.py` (exact total
  match, ≤10 pieces, no kings; client score/optimal/target ignored;
  legacy bank/right rows keep their original rule).
- Optimal count: exact DP over [1, 3, 5, 9] (`balance_scale/solver.py`,
  no lookup tables); scoring is a registered scorer
  (`max(0, 10 - extra)`, 0 when wrong).
- Practice: `POST /api/v1/balance-scale/next` issues fresh random
  published puzzles (identical rows reused; `exclude_ids` steers variety);
  the client keeps a current+next prefetch buffer. Balance auto-submits
  through standard `POST /api/v1/attempts`; success shows the score plus
  «معمای بعدی» with NO auto-advance.
- Speed: `balance_scale/sessions.py` + `router.py` (open → prepare ≥20 →
  start 60s clock → submit loop with ~500ms auto-advance, no manual next
  → server-rebuilt per-puzzle report; per-answer rows reuse `attempts`).
- Seed: `python -m app.modules.balance_scale.seed` (15 hand-designed left
  pans of rising difficulty incl. targets 4/6/8/10/18/90, every entry
  independently verified solvable within 10 pieces).

## Tenth slice

**Which Side is Heavier?** — IMPLEMENTED (`heavier-side`, Exercise 10,
کدام طرف سنگین‌تر است؟). Full spec: `docs/exercises/10-heavier-side.md`.
Rewritten from the earlier scale-pan prototype (piece lists, board hidden)
into real-board material evaluation:

- Route: `/exercises/heavier-side` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons directly
  (no intermediate mode screen), same pattern as Exercises 1–7 and 10.
- Play loop: dedicated `HeavierSidePlay` (practice + speed) over the
  shared read-only `ChessBoard` (standard coordinates, correct colors, no
  highlights/arrows/totals); three large touch choices سفید/سیاه/مساوی
  submit immediately (no Submit button); correctness, scoring, and the
  speed clock stay backend-authoritative.
- Position source: shared `puzzles.db` via `positions/repository.py`
  (read-only, FEN only, fallback FENs when absent), exactly like
  Exercises 1/4/5; per-puzzle answers built server-side by
  `material_comparison/generator.py` (bounded 40-candidate sampling with
  uniform desired-category targeting that enforces the 10% gate
  `abs(diff)/max <= 0.10` with 0/0 accepted, answers server-side only).
- Rule: material only (P=1 N=3 B=3 R=5 Q=9 K=0, kings excluded); no
  engine, themes, ratings, moves, or positional evaluation.
- Validator: `backend/app/modules/material_comparison/validator.py`
  (choice matched against the FEN-derived verdict; client totals/scores
  ignored; legacy left/right rows keep their original rule).
- Scoring: registered scorer (CORRECT +5 / WRONG −2, negatives kept).
- Practice: `POST /api/v1/heavier-side/next` issues fresh random eligible
  published puzzles (identical FEN rows reused; `exclude_ids` steers
  variety); the client keeps a current+next prefetch buffer. Tapping a
  choice auto-submits through standard `POST /api/v1/attempts`; feedback
  shows the correct answer briefly plus sounds, then auto-advances after
  ~1500ms with a manual «معمای بعدی» also available.
- Speed: `material_comparison/sessions.py` + `router.py` (open → prepare
  ≥20 → start 60s clock → submit loop with ~450ms auto-advance, no manual
  next → server-rebuilt per-puzzle report; per-answer rows reuse
  `attempts`).
- Seed: `python -m app.modules.material_comparison.seed` (15 verified
  FEN seeds, 5 white / 5 black / 5 equal incl. kings-only 0/0, every
  entry independently verified against the 10% gate).

## Eleventh slice

**Is it Checkmate?** — IMPLEMENTED (`is-checkmate`, Exercise 13, آیا مات است؟).
ADMIN-BLOCKED: needs an Admin workflow for entering/managing positions;
do not continue development for now.

- Route: `/exercises/is-checkmate` (shared `ExercisePlay` options loop with
  read-only board: three fixed choices مات/کیش/بدون کیش, no hints of the
  answer on the board).
- Validator: `backend/app/modules/checkmate/validator.py` (state derived
  from the stored FEN via `is_check`/`is_checkmate`; stalemate classifies as
  not_check; FEN travels in the server-only `answer_json`, never exposed).
- Seed: `python -m app.modules.checkmate.seed` (15 hand-designed puzzles,
  5 checkmate / 5 check / 5 not_check incl. stalemate, double checks,
  blockable/capturable/king-escape and decoy cases; every classification
  independently verified at seed time).

## Thirteenth slice

**Blindfold Square Vision** — IMPLEMENTED (`blindfold-square-vision`,
Exercise 14, خانه‌یابی ذهنی).

- One uniform-random square per puzzle («خانه‌ی X چه رنگیه؟»).
- Practice: `/exercises/blindfold-square-vision?mode=practice` renders an
  empty tappable board; tapping the asked square submits `{square}`
  immediately. Correct tap = green, wrong tap = red, missed target =
  orange (server `detail` drives the shared board states; no local
  coloring). Brief feedback, then auto-advance; untimed.
- Speed: `?mode=speed` runs the standard 60s session (open → prepare ≥20
  → start clock → submit loop with ~450ms auto-advance → server-rebuilt
  report; per-answer rows reuse `attempts`). NO board is shown: two large
  سفید/سیاه buttons submit `{choice}`; only the tapped button colorizes
  (green/red). Correct +5, wrong −3.
- Square colors are NEVER stored: `square_color()` derives them
  deterministically (`(file + rank)` odd = light/white, a1 is dark).
  `position_json` carries only the square (the public question);
  `answer_json` carries only the square (server-only truth); `fen` is the
  empty board for practice rendering.
- Validator: `backend/app/modules/blindfold_square_vision/validator.py`
  (practice `{square}` matched to target, speed `{choice}` matched to the
  derived color; CORRECT/WRONG only; malformed fails safe; client colors
  ignored). Scoring: registered scorer (`+5/−3`, negatives kept).
  Sessions: `blindfold_square_vision/sessions.py` + `router.py` mirroring
  the shared session lifecycle; practice at
  `POST /api/v1/blindfold-square-vision/next`.
- Seed: `python -m app.modules.blindfold_square_vision.seed` (8 spread
  squares, both colors).

## Fourteenth slice

**Blindfold Calculation** — IMPLEMENTED (`blindfold-calculation`,
Exercise 15, محاسبه‌ی ذهنی).

- Concept: position visualization → mental reconstruction → calculation
  → move selection. This is NOT a board exercise: the user mentally
  reconstructs a real ≤12-piece position from a structured Persian
  description and types the best move in SAN.
- Position source: shared `puzzles.db` via `positions/repository.py`
  (full-row access: FEN + curated solution line). A puzzle is eligible
  only when `piece_count <= 12` AND the line's first move is legal in
  the FEN; that first UCI is the single authoritative answer (Lichess
  curation is the uniqueness invariant — nothing is invented, no engine
  replaces it). `Puzzle.fen` stays NULL; `answer_json` carries
  `{fen, solution, puzzle_id, rating}` server-side only.
- Description: `description.describe_position` (deterministic structured
  text: سفید/سیاه sections, شاه/وزیر/رخ/فیل/اسب/پیاده order, empty
  types omitted, squares in chessboard order in algebraic form,
  explicit `نوبت:` turn plus castling/en-passant lines when meaningful;
  TTS-ready via `audio/ports.py`, no provider added). Generated
  server-side per puzzle, never stored as duplicated text beyond the
  row's own `position_json`.
- Route: `/exercises/blindfold-calculation` with `?mode=practice`
  (untimed, current+next prefetch) and `?mode=speed` (standard 60s
  session: open → prepare ≥20 → start clock → submit loop with brief
  feedback auto-advance → server-rebuilt report; per-answer rows reuse
  `attempts`). Dedicated `BlindfoldCalculationPlay` loop in the shared
  viewport-fit `GameShell` (no board, no piece images, no FEN at any
  point); the description owns the flexible middle area, the SAN input
  stays pinned with touch-sized targets.
- Validator: `validator.py` (submitted SAN parsed with
  `board.parse_san` against the stored FEN, normalized to UCI, CORRECT
  only on UCI equality with the stored solution; `+`/`#` suffixes and
  whitespace tolerated; malformed/illegal/legal-but-wrong input is
  WRONG; client FEN/solution/score/timing ignored; CORRECT or WRONG
  only). Legacy mate-in-1 rows (no `solution` key) keep their original
  mate rule; the seed archives them, never hard-deletes.
- Scoring: shared default (correct=1.0, else 0); practice attempts never
  set `rating_delta`.
- Seed: `python -m app.modules.blindfold_calculation.seed` (15 real
  Lichess rows ≤12 pieces, 8 white / 7 black to move incl. captures,
  promotions, king moves and quiet moves; ratings carried over; every
  entry independently verified).

## Fifteenth slice

**Mental Opening** — IMPLEMENTED (`opening-traps`, Exercise 16, گشایش ذهنی).
ADMIN-BLOCKED: needs Admin-entered positions; do not continue
development for now.

- MVP is one tactical move from a genuine opening-trap position.
  Checkmate is NOT required; correctness is membership of the parsed move
  (normalized to UCI, never raw SAN comparison) in the puzzle's explicit
  solution set, so several different winning moves can be accepted.
- Route: `/exercises/opening-traps` (dedicated `OpeningTrapsPlay` loop:
  NO chessboard, NO piece images, NO FEN and NO solution data at any
  point; opening/trap/theme context plus Persian description, SAN input).
- Validator: `backend/app/modules/opening_traps/validator.py`
  (submitted SAN parsed with `board.parse_san`; malformed, illegal and
  ambiguous input is WRONG; legal-but-not-tactical is WRONG; CORRECT or
  WRONG only; client-supplied FEN/solutions/theme ignored).
- Description: `backend/app/modules/opening_traps/description.py`
  (deterministic Persian text: trap, opening, side to move, then pieces
  in King/Queen/Rook/Bishop/Knight/Pawn order; generic wording that never
  hints the winning move; TTS-ready via `audio/ports.py`, no provider).
- Security: `Puzzle.fen` stays NULL and `position_json` carries only
  description/side/mode/opening/trap/theme; FEN + solution UCIs live in
  server-only `answer_json`, so puzzle endpoints never leak them.
- Seed: `python -m app.modules.opening_traps.seed` (15 hand-designed
  puzzles from real lines — Legal, Blackburne Shilling, Scholar's,
  Fool's, Siberian, Noah's Ark, Mortimer, Elephant, Damiano, Fried Liver,
  Stafford, Rubinstein, Kieninger, Evans, Caro-Kann mate — each solution
  independently verified legal with its declared capture/check/mate
  property; Noah's Ark and Evans accept two tactics each; 11 white +
  4 black to move).
- Known limitation: unlisted objectively-strong alternatives count as
  WRONG, because the exercise grades the documented trap tactic, not
  general engine evaluation (no Stockfish by design).

## Sixteenth slice

**Reverse Opening** — IMPLEMENTED (`reverse-opening`, Exercise 17,
گشایش معکوس). ADMIN-BLOCKED: needs Admin-entered positions; do not
continue development for now. (Consolidated from the former
`opening-move-reconstruction` slug; there is only one exercise.)

- Route: `/exercises/reverse-opening` (dedicated
  `ReverseOpeningPlay` loop with two boards: the read-only TARGET
  board on top, the user-driven reconstruction board below starting from
  the standard initial position; tap or drag to move, server-generated
  SAN move list, undo/reset, promotion picker).
- Validator: `backend/app/modules/reverse_opening/validator.py`
  (submitted UCIs replayed with python-chess from the stored start;
  CORRECT only when placement + side to move + castling rights +
  en-passant square equal the stored target; clocks ignored; any line
  reaching the target counts, so transpositions are accepted; CORRECT or
  WRONG only; detail carries both sequences plus matched/expected plies
  as move-by-move feedback).
- Step oracle: `POST /api/v1/reverse-opening/step` (legality-only move
  assistance following the pathfinding-step precedent: replays the
  claimed history from the stored start, applies one legal move, returns
  the new FEN plus server-generated SAN and an on-track flag; reveals no
  solution data; final grading still revalidates the whole sequence).
- Security: `answer_json` (start/target/solutions) is server-only;
  `position_json` exposes start/target FENs for rendering plus opening
  context, never the sequence; client FENs/solutions are ignored.
- Seed: `python -m app.modules.reverse_opening.seed` (15
  real opening lines of 5-10 plies from the standard start — Italian,
  Ruy Lopez, Sicilian Najdorf, French Winawer, Caro-Kann, QGD, KID,
  Scotch, Four Knights, London, Petrov, Vienna, Alapin, Caro Advance,
  Evans — targets generated from the lines, all independently verified,
  no duplicate targets, mixed sides to move).
- Known limitation: single canonical line per puzzle in the seed, though
  the position-based grader already accepts any equivalent line.

## Seventeenth slice

**Trapped Piece** — IMPLEMENTED (`trapped-pieces`, Exercise 18, مهره‌ی گرفتار).

MicroChess definition (NOT the Lichess motif): a non-pawn piece
(King, Queen, Rook, Bishop, Knight, either color) is trapped iff it has
zero SAFE destinations. A destination is safe iff moving there does not
lose material after the resulting forcing exchange — an attacked square
with a favorable recapture still counts as an escape, while a quiet
square that loses the piece after the exchange does not. Pawns are never
candidates; kings use pure legality (never move into check).

- Route: `/exercises/trapped-pieces` with `?mode=practice` (untimed,
  multi-select any number + «بررسی جواب», positions hold 1–3 trapped
  pieces) and `?mode=speed` (standard 60s session, every position holds
  exactly one trapped piece so one tap submits immediately, no confirm
  step). Card renders both entry buttons directly.
- Play loop: dedicated `TrappedPiecesPlay` (practice + speed reusing the
  `PieceGameLayout` shell, timer, hints, feedback; whole board is the
  question, only user selections shown); correctness, scoring, and the
  speed clock stay backend-authoritative.
- Engine: `trapped_pieces/detector.py` — per candidate, legal moves with
  the turn set to its color, each destination pushed and graded by
  Static Exchange Evaluation (least-valuable-attacker swap, shared
  P=1 N=3 B=3 R=5 Q=9 K=0 values, kings never capture in the line);
  safe iff net ≥ 0; check-giving moves are safe unless a legal reply
  captures the piece at a net loss. Deterministic, millisecond-scale,
  server-side only. Limitation: only the on-square exchange is searched;
  deeper multi-move traps beyond the immediate exchange count as safe.
- Position source: shared `puzzles.db` via `positions/repository.py`
  (FEN only), evaluated by `trapped_pieces/generator.py` (bounded
  sampling rejecting in-check/empty/4+-degenerate positions; Speed uses
  `exactly_one` mode). Answers server-side only.
- Validator: `backend/app/modules/trapped_pieces/validator.py` (exact
  set match; duplicates/order-insensitive; malformed squares count as
  wrong; client FEN/answer/score ignored).
- Scoring: registered per-square scorer (`+5` correct / `−2` missed /
  `−2` wrong, negatives kept; `+5` bonus for correctly answered
  zero-target legacy rows). Speed reuses it: correct tap `+5`, wrong
  tap `−4` (−2 wrong plus −2 for the missed single trapped piece).
- Speed: `trapped_pieces/sessions.py` + `router.py` (open → prepare ≥20
  → start 60s clock → tap-to-submit loop with ~450ms auto-advance, no
  manual next → server-rebuilt per-puzzle report; per-answer rows reuse
  `attempts`).
- Seed: `python -m app.modules.trapped_pieces.seed` (seeded scan of the
  shared source to ~30 live puzzles: Practice mix with multi-answer
  coverage + exactly-one Speed pool; pre-SEE legacy rows archived, never
  hard-deleted; every answer independently re-verified from its FEN).

## Nineteenth slice (end of the roadmap)

**Castling Rights** — IMPLEMENTED (`castling-rights`, Exercise 21).
ADMIN-BLOCKED: needs Admin-entered positions; do not continue
development for now.
- Route: `/exercises/castling-rights` (shared `ExercisePlay` loop extended
  with a fixed four-option mode; board shows the position as context only).
- Validator: `backend/app/modules/castling_rights/validator.py` (each option
  must appear in that color's python-chess legal moves on a turn-flipped
  board; explicit king/rook presence guards stale FEN flags safely).
- Seed: `python -m app.modules.castling_rights.seed` (15 puzzles covering all
  four options, single-option cases, absent rights, blocked paths incl. b-file,
  check, transit/destination attacks, stale rook/king flags, partial subsets).

## Memorization Board (Exercise 12)

**Memorization Board** — IMPLEMENTED (`chinese-board`, Exercise 12,
صفحه‌ی حفظی. The `chinese-board` slug is kept for routes, API, and DB;
user-facing text always says صفحه‌ی حفظی).
Full spec: `docs/exercises/12-memorization-board.md`.

- Route: `/exercises/chinese-board` with `?mode=practice` (untimed) and
  `?mode=speed` (60s session); card renders both entry buttons directly
  (no intermediate mode screen), same pattern as Exercises 1–10.
- Play loop: dedicated `ChineseBoardPlay` (practice + speed; the component
  keeps its historic name, user-facing text is صفحه‌ی حفظی) over the
  shared `ChessBoard` (fixed White orientation in both phases, SVG pieces
  only): read-only memorize board with a subtle countdown for the
  server-authoritative budget (`position_json.memorization_ms` =
  `piece_count × 1000ms`), a motion-safe fade into an empty rebuild board
  with a 12-piece tap palette + eraser (fixed 44px wrapping tools, free
  placement, replace on tap, no legality rules), and an explicit
  «بررسی صفحه» check; correctness, scoring, and the speed clock stay
  backend-authoritative. Portrait stacks board/controls; landscape keeps
  the height-capped board beside a 368px control column (2-row palette,
  single-line question) so palette + check stay visible without scrolling
  down to 844×390; review boards are width-capped and speed feedback is
  counts-only.
- Position source: shared `puzzles.db` via `positions/repository.py`
  (read-only, FEN only, fallback FENs when absent), exactly like
  Exercises 1/4/5/11; per-puzzle budgets built server-side by
  `chinese_board/generator.py` (any valid FEN eligible — counts are
  naturally bounded by chess at ≤32, ~4s–32s on measured real data —
  answers server-side only).
- Rule: exact `(color, type, square)` reconstruction. Matching is
  exact-first, then same-`(color,type)` wrong-square pairing (ONE error
  per misplaced piece, never missing-plus-extra double-counting), then
  missing, then extra; FEN metadata (side/castling/en-passant/clocks)
  ignored.
- Validator: `backend/app/modules/chinese_board/validator.py` (CORRECT
  only when perfect, else WRONG; malformed/duplicate-square input fails
  safe; client score/count/FEN fields ignored; detail carries disjoint
  correct/wrong/missing/extra descriptors plus square overlays).
- Scoring: registered scorer (`5×correct − 2×(wrong+missing)`, negatives
  kept, no floor).
- Practice: `POST /api/v1/chinese-board/next` issues fresh random
  published puzzles (identical FEN rows reused; `exclude_ids` steers
  variety); the client keeps a current+next prefetch buffer. Checking
  submits through standard `POST /api/v1/attempts`; feedback shows the
  four counts plus the score with a «پاسخ شما»/«پاسخ صحیح» toggle plus
  sounds, then waits for manual «صفحه بعدی» (NO auto-advance) or retry.
- Speed: `chinese_board/sessions.py` + `router.py` (open → prepare ≥20 →
  start 60s clock → memorize → rebuild → check loop with ~600ms feedback
  auto-advance, no manual next → server-rebuilt per-puzzle report;
  per-answer rows reuse `attempts`).
- Seed: `python -m app.modules.chinese_board.seed` (15 verified positions
  spanning 4–32 pieces, study budgets 4000–32000ms).
- QA: `frontend/qa/chinese-board.cjs` (viewport matrix + place/replace/
  erase/check/next passes, pieces-only payload assertion).

## Exercise 4 (spec-track)

**Undefended Pieces** — IMPLEMENTED (`undefended-pieces`). Full spec:
`docs/exercises/04-undefended-pieces.md`.

- Route: `/exercises/undefended-pieces` with `?mode=practice` (untimed)
  and `?mode=speed` (60s session); card renders both entry buttons
  directly (no intermediate mode screen), same pattern as Exercises 1–3.
- Play loop: `frontend/src/components/exercise/UndefendedPiecesPlay.tsx`
  (practice + speed reusing the `PieceGameLayout` shell, timer, hints,
  feedback; NO pre-highlight — the whole board is the question, only the
  user's selections are shown); correctness, scoring, and the speed clock
  stay backend-authoritative.
- Position source: shared `puzzles.db` via `positions/repository.py`
  (read-only, FEN only, fallback FENs when absent), exactly like
  Exercise 1; per-puzzle answers built server-side by
  `undefended_pieces/generator.py` (bounded 25-candidate sampling that
  prefers non-empty positions while keeping zero-target valid, answers
  server-side only).
- Rule: non-King piece with ≥1 valid enemy attacker AND 0 valid friendly
  defenders, from python-chess attack geometry; absolutely pinned pieces
  (`board.is_pinned`, King only) never count as attackers/defenders;
  pieces shielding a Queen still count; Kings never answers but still
  attack/defend.
- Validator: `backend/app/modules/undefended_pieces/validator.py` (exact
  set match incl. empty==empty; duplicates/order-insensitive; malformed
  squares count as wrong).
- Practice: `POST /api/v1/undefended-pieces/next` issues fresh random
  published puzzles (identical FEN rows reused; `exclude_ids` steers
  variety); the client keeps a current+next prefetch buffer. Answers go
  through standard `POST /api/v1/attempts`.
- Speed: `undefended_pieces/sessions.py` + `router.py` (open → prepare
  ≥20 → start 60s clock → submit loop with ~450ms auto-advance, no
  manual next → server-rebuilt per-puzzle report; per-answer rows reuse
  `attempts`).
- Scoring: registered per-square scorer (+5 correct / −1 missed / −2
  wrong, +5 bonus for correctly answered zero-target, negatives kept,
  independent of the CORRECT/PARTIAL/WRONG label).
- Seed: `python -m app.modules.undefended_pieces.seed` (15 puzzles
  covering single/multiple/both-colors/none, all piece types as
  attackers and defenders, blockers, king attack/defense/exclusion, and
  the three mandatory pin regressions; every answer independently
  verified).
