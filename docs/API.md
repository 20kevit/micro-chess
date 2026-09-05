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
  - `result` in correct/partial/wrong/timeout/skipped/abandoned.
  - `rating_delta` is `null` until Glicko-2 lands; practice attempts never set it.
  - Errors: `puzzle_not_available` (404 for missing/unpublished/archived).

## Piece Recognition (Exercise 1)

- `POST /api/v1/piece-recognition/next` → fresh random practice `PuzzleOut`
  (published row, no `answer_json`).
- `POST /api/v1/piece-recognition/sessions` `{duration_s?}` (default 60) →
  `{session_id, exercise_slug, status, duration_s, started_at, expires_at, remaining_ms}`.
- `POST /api/v1/piece-recognition/sessions/{id}/next` → session `PuzzleOut`;
  `410 session_expired` after the server clock passes `expires_at`.
- `POST /api/v1/piece-recognition/sessions/{id}/submit`
  `{puzzle_id, answer: {selected_squares: []}, hints_used?: [], started_at?}` →
  `{attempt: AttemptOut, feedback_key, detail, session: summary}`.
  Only puzzles issued to the session are accepted (404 otherwise);
  client-supplied FEN/target/solution fields are ignored.
- `GET /api/v1/piece-recognition/sessions/{id}` → summary
  `{session_id, status, duration_s, started_at, expires_at, remaining_ms,
  attempted, correct, partial, wrong, score}` (auto-expires).
- `POST /api/v1/piece-recognition/sessions/{id}/finish` → final summary.
- Errors: `session_not_found` (404), `session_expired` (410),
  `puzzle_not_in_session`/`puzzle_not_available` (404).
