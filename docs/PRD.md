# PRD — MicroChess Foundation

## Vision

Mobile-first educational chess exercise platform, primarily for children.
Short, friendly, game-like exercises that teach chess step by step.

## Users

- Children learning chess (primary, touch devices).
- Parents/coaches (later: assignments, progress views).
- Admins/content authors (later: puzzle authoring).

## Scope — foundation only

In scope now:

- Project scaffold (frontend + backend + docs + tests).
- Exercise → Puzzle → Validation → Score → Rating → Feedback pipeline shape.
- Auth basics (register/login/me), exercise catalog read, puzzle read, attempt submit.
- Design system + RTL Persian shell + SVG board.

Out of scope now (explicitly postponed):

- All 20+ exercise types. Piece Recognition is the first vertical slice, spec comes later.
- Full rating system (Glicko-2-style per-exercise rating later).
- Admin panel (FEN/PGN import, hints, activation later).
- TTS provider (boundary only now).
- Analytics/event system (raw `answer_json` stored for later).
- Overall/global rating.

## Key domain rules

- Exercise = activity type. Puzzle = one question. Position = board/data. Attempt = one try.
- Puzzle answer immutable once published.
- Archive, don't hard-delete, when history exists.
- Attempts: correct/partial/wrong/timeout/skipped/abandoned; rated vs practice.
- Practice never affects rating.
- Anonymous progress local-first; transfer after signup; permanent progress needs account.
- Backend authoritative for validation/scoring/rating.

## Non-functional

- Mobile-first, touch-usable, square 8x8 board, board LTR inside RTL page.
- Persian UI now, English/i18n-ready structure.
- REST/HTTP only for MVP. No WebSockets.
- SQLite now, PostgreSQL-ready layer.
