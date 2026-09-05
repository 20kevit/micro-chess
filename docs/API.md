# API (foundation)

Base URL: `http://localhost:8000`. All module routes under `/api/v1`.

## Health

- `GET /health` → `{"status": "ok"}`

## Auth

- `POST /api/v1/auth/register` `{email, password, display_name?}` → `{access_token, token_type}` (201)
- `POST /api/v1/auth/login` `{email, password}` → `{access_token, token_type}`
- `GET /api/v1/users/me` (Bearer) → `{id, email, display_name, created_at}`
- Errors: `email_taken` (400), `invalid_credentials` (401), `auth_required` (401)

## Exercises

- `GET /api/v1/exercises` → `[{slug, title_fa, title_en, description, is_active}]` (active only)

## Puzzles (read-only for MVP)

- `GET /api/v1/puzzles?exercise=<slug>` → published + non-archived puzzles
- Response omits `answer_json` (backend authoritative). Admin authoring comes later.
- `GET /api/v1/puzzles/{id}` → single puzzle (education stays accessible later); 404 `puzzle_not_available`

Example:

```json
[
  {
    "id": 1,
    "exercise_slug": "piece-recognition",
    "fen": null,
    "position_json": {},
    "hint_json": {},
    "initial_rating": 1200.0,
    "is_published": true,
    "is_archived": false,
    "published_at": "2026-01-01T00:00:00"
  }
]
```

## Attempts

- `POST /api/v1/attempts`
  - Auth: optional for `practice`; required for `rated` (`auth_required_for_rated` 401).
  - Body: `{puzzle_id, answer: {selected_squares: []}, mode, client_result?, hints_used?: [], started_at?}`
  - `client_result` short-circuits validation for terminal states; otherwise the exercise validator runs.
  - Response: `{id, puzzle_id, exercise_slug, mode, result, score, feedback_key, rating_delta, detail, hints_used, started_at, duration_ms, created_at}`
  - `detail` is `{correct: [], missed: [], wrong: []}` for piece-recognition.
  - `score` is authoritative and backend-computed (per-square 5/−1/−2 for
    piece-recognition and legal-destinations via their registered scorers,
    else correct=1.0/partial=0.5/0); never trusted from the client; may be
    negative.
  - `result` in correct/partial/wrong/timeout/skipped/abandoned.
  - `rating_delta` is `null` until Glicko-2 lands; practice attempts never set it.
  - Errors: `puzzle_not_available` (404 for missing/unpublished/archived).

## Piece Recognition (Exercise 1)

Lifecycle: open (`preparing`, no clock) → prepare ≥20 → start (60s clock)
→ submit loop → finish/report.

- `POST /api/v1/piece-recognition/next` `{exclude_ids?: []}` → fresh random
  practice `PuzzleOut` (published row, no `answer_json`; identical rows reused).
- `POST /api/v1/piece-recognition/sessions` `{duration_s?}` (default 60) →
  `{session_id, exercise_slug, status: "preparing", duration_s, started_at,
  expires_at: null, remaining_ms, buffered}`.
- `POST /api/v1/piece-recognition/sessions/{id}/puzzles` `{count}` (default 20,
  cap 60) → `PuzzleOut[]` for the buffer/refill; `410 session_expired` after expiry.
- `POST /api/v1/piece-recognition/sessions/{id}/start` → active session with
  running clock; `409 buffer_not_ready` below 20 buffered puzzles.
- `POST /api/v1/piece-recognition/sessions/{id}/next` → single session `PuzzleOut`.
- `POST /api/v1/piece-recognition/sessions/{id}/submit`
  `{puzzle_id, answer: {selected_squares: []}, hints_used?: [], started_at?}` →
  `{attempt: AttemptOut, feedback_key, detail, session: summary}`.
  Only puzzles issued to the session are accepted (404 otherwise);
  client-supplied FEN/target/solution/score fields are ignored;
  `409 session_not_started` before the clock starts.
- `GET /api/v1/piece-recognition/sessions/{id}` → summary
  `{session_id, status, duration_s, started_at, expires_at, remaining_ms,
  buffered, attempted, correct, partial, wrong, score}` (auto-expires).
- `GET /api/v1/piece-recognition/sessions/{id}/report` → `{session, entries[]}`
  rebuilt from stored attempts: per-puzzle prompt/result/score/correct/missed/wrong.
- `POST /api/v1/piece-recognition/sessions/{id}/finish` → final summary.
- Errors: `session_not_found` (404), `session_not_started` (409),
  `session_expired` (410), `buffer_not_ready` (409),
  `puzzle_not_in_session`/`puzzle_not_available` (404).

## Legal Destinations (Exercise 2)

Same lifecycle and contract as Exercise 1 (open → prepare ≥20 → start
60s clock → submit loop → finish/report), under `/api/v1/legal-destinations`:

- `POST /api/v1/legal-destinations/next` `{exclude_ids?: []}` → fresh
  random white-only practice `PuzzleOut` (no `answer_json`; the target
  square in `position_json.from` is public task data, destinations are not).
- `POST /api/v1/legal-destinations/sessions` → `preparing` session (60s default).
- `POST /api/v1/legal-destinations/sessions/{id}/puzzles` `{count}` →
  buffer/refill puzzles (cap 60); `POST .../start` requires ≥20.
- `POST /api/v1/legal-destinations/sessions/{id}/submit` →
  `{attempt, feedback_key, detail, session}`; per-square 5/−1/−2 scoring
  with the +5 zero-target bonus; only session-issued puzzles accepted.
- `GET .../sessions/{id}` → summary; `GET .../report` → authoritative
  per-puzzle report rebuilt from stored attempts;
  `POST .../finish` → final summary. Same error codes as Exercise 1.
- Full spec: `docs/exercises/02-legal-destinations.md`.
