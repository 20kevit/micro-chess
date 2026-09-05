# MicroChess Design System

Shared visual language for all exercises (implemented in `frontend/src/`,
tokens in `index.css`). Future exercises reuse these primitives — never
restyle per page.

## Principles

- Playful but polished educational-game aesthetic; never cheap/cartoonish.
- Mobile-first, touch-usable, Persian/RTL; chessboard islands are `dir="ltr"`.
- Subtle, purposeful motion only; the chessboard never animates.
- Backend decides correctness; the UI only renders and transports answers.

## Typography

- Font: `Vazirmatn` first, fallback `system-ui, -apple-system, "Segoe UI", sans-serif`.
- Loading (mandatory, not optional): self-hosted via `@fontsource/vazirmatn`
  imported in `index.css` — weights 400 (body), 700 (bold UI), 900 (display
  headings), `font-display: swap`, arabic+latin subsets. Never declare the
  family without bundling the asset; never add a per-component font
  workaround — fix the shared mechanism instead.
- Encoding contract: sources UTF-8, API JSON UTF-8, HTML
  `<html lang="fa" dir="rtl">` + `<meta charset="UTF-8">`; board islands
  `dir="ltr"` with Latin square names.
- Page title (`PageHeader`): `text-2xl font-black`, stone-900.
- Subtitle/question: `text-sm`, stone-500 (board questions come from `prompt_fa`).
- Buttons: `text-base font-bold`. Badges/captions: `text-xs font-bold`.
- Numbers shown to children use Persian digits (`toLocaleString("fa-IR")`);
  algebraic square names stay Latin inside `dir="ltr"` spans.

## Colors (semantic roles → tokens → Tailwind)

| Role | Token | Tailwind | Use |
|---|---|---|---|
| primary | `--mc-primary` | violet-600 | main actions, active mode, timer bar |
| primary strong | `--mc-primary-strong` | violet-700 | pressed, emphasis text |
| primary soft | `--mc-primary-soft` | violet-100 | badges, soft fills |
| secondary/accent | `--mc-accent` | amber-300 | secondary buttons (e.g. practice entry, retry, clear) |
| success | `--mc-success` / soft | green-600 / green-50 | correct banner, correct ring, correct count |
| error | `--mc-error` / soft | red-600 / red-50 | wrong banner, wrong ring, wrong count |
| warning | `--mc-warning` / soft | amber-600 / amber-50 | missed banner, missed ring, missed count |
| info | `--mc-info` | sky-600 | task target marker (never an answer hint) |
| background | `--mc-bg` | #f6f4ff | app background |
| surface | `--mc-surface` | white | cards, timer panel |
| text | `--mc-text` | stone-900-ish | headings, body |
| muted | `--mc-muted` | stone-500 | subtitles, captions |

Board squares: light amber-100 / dark emerald-600 (unchanged legacy).

## Components (`components/ui/` + `components/chess/` + `components/exercise/`)

- `Button` — variants `primary | secondary | ghost`; `min-h-[44px]`,
  `rounded-2xl`, bold. Full-width (`w-full`) for main actions on mobile.
- `Card` — `rounded-3xl bg-white p-4 shadow-md shadow-violet-100`.
- `PageHeader` — title + optional subtitle; `FeedbackText` maps backend
  `feedback_key` → Persian (unknown keys fall back to generic error).
- `Badge` — status pill (mode, counts, `comingSoon`).
- `AppShell` — max-w-3xl column, header, content `px-4`, bottom nav on
  mobile / static on desktop.
- `ChessBoard` — SVG pieces only (never Unicode glyphs); square states:
  `selected` (violet ring), `correct` (green), `missed` (amber dashed),
  `wrong` (red), `target` (sky, task piece only — never answer data).
- Exercise cards (`ExercisesPage`) — number pill, title, description; cards
  with entry `modes` render one button per mode (practice=secondary,
  speed=primary) plus a one-line description each.
- Feedback states — `ResultBanner` (tone by result) + `FeedbackLegend`
  (`✓` درست انتخاب کردی / `✕` این مهره هدف نبود / `!` این مهره را جا انداختی)
  + correct-answer line + explanation. Never color alone.
- Timer — bordered panel with label, Persian seconds, correct-count badge,
  and progress bar (`role="timer"`, `aria-live="polite"`).
- Preparing progress — same panel pattern: label + Persian `n / 20` counter
  + progress bar; shown while the speed buffer fills (clock not running).
- Session summary — stat tiles (attempted/correct/partial/wrong/score/
  average) + accuracy line; empty state when nothing was answered.
- Report entries — tone-coded list rows (green/amber/red by result) with
  prompt, result label, score, missed/wrong counts, and correct squares.
- Empty states — `Badge(comingSoon)` + `exercises.empty` text.
- Loading states — `common.loading` text; error card with `common.retry`.

## Interaction

- hover/active — Tailwind `transition` + `active:` darkening on buttons.
- focus — global `:focus-visible` 3px primary outline (accessibility).
- selected — violet ring on board squares; violet fill on option buttons.
- disabled — board `disabled` while submitting / after submit; buttons
  `disabled` while busy (no double-submit).
- correct/incorrect — ring + banner + legend row (triple-coded, not color-only).

## Spacing

Tailwind scale; convention: `gap-2/mt-2` between related controls,
`mt-3/mt-4` between sections, `p-4` card padding, `px-4` page gutters.

## Border radius

- Buttons/inputs: `rounded-2xl` (`--mc-radius-sm`).
- Cards/board/timer: `rounded-2xl/3xl` (`--mc-radius-lg`).
- Badges/pills: `rounded-full`.

## Shadows / elevation

- `--mc-shadow-sm` buttons, `--mc-shadow-md` cards + board (`shadow-md
  shadow-violet-100`). Timer/summary reuse card elevation.

## Animation

- `transition` on buttons, `transition-[width]` on the timer bar only.
- `prefers-reduced-motion: reduce` disables transitions globally.

## Board viewport rule (hard requirement)

`viewport → page padding → max board width → square board`. Enforcement:

1. `ChessBoard` root is `w-full` + `aspect-square` grid (never fixed px).
2. Play screens wrap it in `mx-auto w-full min-w-0 max-w-[520px]`
   (centers, caps desktop width, shrinks on mobile).
3. `body { overflow-x: clip }` guards against accidental overflow.
4. Squares use `touch-action: manipulation`, min 44px targets.

## i18n

All UI text via `t("key")` (`src/i18n/`); Persian in `fa.ts`, English later.
Square names and SAN stay Latin; counts use Persian digits.
