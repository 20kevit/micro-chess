# MicroChess Platform — UX & Design Specification

## 1. Purpose

This document defines the platform-level UX rules for MicroChess.

It complements:

* `DESIGN_SYSTEM.md`
* exercise-specific UX documentation
* `ARCHITECTURE.md`
* `SECURITY.md`
* `PRODUCT_SCOPE.md`

It does not redefine existing exercise-specific visual rules.

When an exercise document defines a more specific interaction, the exercise document takes precedence.

---

## 2. Product UX Principles

MicroChess is:

* child-first
* chess-skill focused
* Persian-first
* mobile-first
* simple before complex
* visually friendly without becoming childish
* feedback-driven
* fast to use
* accessible
* data-informed without exposing unnecessary complexity to players

The interface should help the player answer:

1. What should I do?
2. What happened?
3. What should I do next?

Avoid unnecessary UI, configuration, decoration, and terminology.

---

## 3. Language and Direction

The platform is i18n-ready from the beginning.

Current default:

```text
language: Persian
direction: RTL
```

Rules:

* User-facing text is Persian.
* Translation keys must not be hard-coded around Persian wording.
* Layout must support RTL correctly.
* Chessboard coordinates, notation, and chess interaction remain LTR/board-native where appropriate.
* Numbers must remain readable in both RTL and LTR contexts.
* Mixed Persian/Latin content must not produce broken bidi layout.

Future languages must be possible without redesigning the UI.

---

## 4. Visual Identity

The platform should feel:

* friendly
* modern
* clean
* energetic
* trustworthy
* appropriate for children, teenagers, parents, and coaches

Do not use:

* excessive gradients
* excessive shadows
* visually noisy backgrounds
* unnecessary animations
* overly childish cartoon UI
* dense enterprise-style dashboards for players

Existing tokens and components in `DESIGN_SYSTEM.md` are authoritative.

Do not introduce one-off colors, spacing, typography, or component styles when an existing design token/component is appropriate.

---

## 5. Responsive Design

The platform MUST work on:

* desktop
* tablet
* mobile portrait
* mobile landscape

The UI must reflow rather than requiring horizontal scrolling.

Responsive behavior must be based on available space rather than only device names.

Test representative viewport sizes, including narrow mobile screens and desktop screens.

---

## 6. Exercise Screen Rule

Exercise screens have a special requirement:

> The complete active exercise experience should fit within the visible viewport whenever reasonably possible.

Normal page scrolling must not be required during gameplay.

This applies to:

* board
* question/instruction
* answer controls
* feedback
* progress
* timer
* primary action

Do not solve layout problems by blindly applying:

```css
overflow: hidden;
```

Instead:

* calculate available viewport space
* resize the board
* collapse secondary information
* adapt control placement
* use responsive layouts
* preserve the primary interaction

The chessboard receives the highest visual priority.

---

## 7. Navigation

Authenticated users should have clear access to:

* Home/Dashboard
* Exercises
* Progress
* Profile
* Settings

Additional navigation may appear according to role.

Player navigation should remain simple.

Admin and Coach interfaces may use denser navigation because their workflows are inherently more complex.

Mobile navigation may use a compact menu/navigation pattern.

---

## 8. Dashboard

The Player dashboard should answer:

* What should I practice?
* How am I progressing?
* What did I recently do?
* What is my current goal?
* What should I do next?

Recommended primary areas:

```text
Continue Training
Recommended Exercises
Progress
Daily Goal / Streak
Recent Activity
Achievements
```

Do not turn the dashboard into an analytics report.

Detailed analytics belong in dedicated views.

---

## 9. Exercise Discovery

The exercise catalog should:

* show all available exercises
* clearly distinguish available and unavailable exercises
* indicate `به‌زودی` for exercises not yet implemented
* make the exercise purpose understandable
* avoid requiring chess terminology knowledge when possible
* support future filtering/search without making the default screen complicated

An unavailable exercise must not appear playable.

---

## 10. Exercise Start Flow

A player should reach gameplay with minimal steps:

```text
Exercise
  ↓
Mode selection (if applicable)
  ↓
Start
  ↓
Training
```

Do not add unnecessary configuration before every attempt.

Practice and Speed should be clearly differentiated where both exist.

---

## 11. Feedback

Feedback must be:

* immediate
* understandable
* visually clear
* actionable when appropriate
* consistent across exercises

Correct and incorrect states must not depend on color alone.

Use combinations of:

* color
* text
* icons
* position/state
* appropriate motion

Avoid excessive celebration after every trivial action.

Feedback should support learning rather than interrupt it.

---

## 12. Error States

Every major screen should have meaningful:

* loading state
* empty state
* error state
* retry/recovery path

Errors should be understandable to the user.

Do not expose:

* stack traces
* SQL errors
* internal identifiers
* implementation details

Technical details belong in logs.

---

## 13. Forms

Forms must provide:

* clear labels
* appropriate input types
* visible validation
* useful Persian error messages
* preserved valid input after validation failure
* keyboard-friendly interaction

Required fields must be obvious.

Do not rely exclusively on placeholder text as a label.

---

## 14. Touch and Interaction

Interactive controls must be comfortable on touch devices.

Avoid:

* tiny buttons
* controls placed too close together
* hover-only functionality
* interactions requiring precise mouse movement

Where a drag interaction exists, provide an alternative when practical.

Chess interactions must remain usable with touch.

---

## 15. Accessibility

Accessibility is part of the primary design, not a separate mode.

The target is **WCAG 2.2 AA where applicable**.

Minimum requirements:

* semantic HTML
* keyboard navigation
* visible focus states
* meaningful accessible names
* correct form labels
* sufficient text/UI contrast
* no color-only meaning
* reduced-motion support
* responsive text/layout
* appropriate screen-reader semantics

Dynamic feedback that matters to the user should have an accessible representation.

Do not claim full accessibility compliance unless it has actually been tested.

---

## 16. Chessboard Accessibility

The chessboard is a special interactive component.

Where practical, provide:

* accessible board label
* identifiable squares
* keyboard-operable alternatives
* textual result/feedback
* state information not dependent solely on color

Accessibility must never compromise normal touch usability.

If an exercise cannot provide a fully equivalent board interaction for assistive technology, document the limitation rather than falsely claiming full support.

---

## 17. Motion

Animation is optional enhancement, never a requirement for understanding.

Respect:

```text
prefers-reduced-motion
```

When reduced motion is enabled:

* remove unnecessary transitions
* reduce decorative movement
* preserve state/result information
* never remove essential feedback

Avoid animation during time-sensitive gameplay unless it provides real value.

---

## 18. Loading and Performance UX

The user should see meaningful progress quickly.

Prefer:

* lightweight initial UI
* lazy loading for non-critical content
* small payloads
* cached static assets
* progressive rendering where useful

Do not block the entire application while loading unrelated data.

Exercise gameplay must prioritize responsiveness over decorative content.

---

## 19. Role-Based UX

The UI must reflect authorization.

### Player

Focus on:

* training
* progress
* goals
* achievements
* profile

### Coach

Focus on:

* students
* groups/classes
* assignments
* progress
* training insights

### Parent

Focus on:

* linked children
* progress
* reports
* relevant notifications

### Admin

Focus on:

* users
* exercises
* puzzles
* generators
* analytics
* support
* system management

Hiding a button is not authorization.

Backend authorization remains authoritative.

---

## 20. Privacy UX

Private information must not be exposed by default.

The UI should clearly distinguish:

* public profile information
* private profile information
* personal training data
* related-user data
* administrative data

Do not display another user's private information merely because the current user can reach the relevant page.

---

## 21. Gamification UX

Gamification should encourage meaningful practice.

The UI may expose:

* XP
* levels
* streaks
* daily/weekly goals
* achievements
* badges
* personal records
* exercise mastery
* leaderboards

Avoid:

* manipulative urgency
* excessive notifications
* meaningless point farming
* visual overload

Learning quality has priority over engagement metrics.

---

## 22. Analytics UX

Player analytics should be understandable without requiring statistical knowledge.

Prefer:

```text
Accuracy
Attempts
Practice Time
Active Days
Rating
Rating Change
Exercise Progress
Streak
```

Charts should answer a question rather than exist merely because charts are available.

Detailed administrative analytics may expose substantially more information.

---

## 23. Empty States

Empty states should explain:

1. what is missing
2. why it matters
3. what the user can do next

Examples:

```text
No training history yet.
Start your first exercise to see your progress here.
```

Do not use empty states as dead ends.

---

## 24. Responsive Validation

Every major UI change must be checked at minimum against:

```text
mobile portrait
mobile landscape
tablet
desktop
```

Exercise screens additionally require verification that:

* the board remains usable
* primary controls remain visible
* no unexpected page scroll appears
* feedback remains visible
* timer remains visible when applicable
* text does not overlap controls

---

## 25. UX Testing Requirements

UI implementation is not complete when it merely renders.

Important flows must be tested for:

* successful interaction
* invalid input
* loading
* failure
* retry
* narrow viewport
* touch interaction
* keyboard interaction where applicable
* authorization differences
* empty data
* long text
* Persian/RTL layout

Exercise-specific acceptance criteria remain authoritative.

---

## 26. Implementation Rules

Agents implementing UX MUST:

1. inspect existing components before creating new ones
2. reuse existing design tokens
3. reuse existing layout primitives
4. preserve existing exercise behavior
5. avoid speculative component systems
6. avoid duplicating shared UI logic
7. keep routes/pages thin
8. keep business rules outside presentation components
9. verify responsive behavior
10. run the relevant frontend tests/build/type checks

Do not rewrite the frontend architecture merely to improve visual consistency.

---

## 27. Definition of Done

A platform UI feature is complete when:

* required states exist
* Persian/RTL behavior works
* responsive layouts work
* authorization is respected
* accessibility basics are implemented
* loading/error/empty states are handled
* existing design system is reused
* exercise screens preserve viewport-first behavior where applicable
* relevant tests pass
* no unrelated UI is unnecessarily changed

---

## 28. Final UX Rule

MicroChess should always prefer:

```text
clarity
  >
decoration

learning
  >
engagement tricks

simple interaction
  >
configuration

responsive adaptation
  >
forced scrolling

accessible behavior
  >
visual-only behavior

existing design system
  >
one-off styling
```

The interface should feel simple to the child while remaining structurally capable of supporting serious players, coaches, parents, and administrators.

## 7.1 Mobile Navigation Behavior

Mobile navigation MUST be explicitly designed rather than treated as a collapsed desktop navigation.

### Player Mobile Navigation

For authenticated Players, the primary mobile navigation should expose the most frequently used destinations:

```text
Home
Exercises
Progress
Profile
```

Additional destinations such as Settings should be accessible from Profile or a secondary menu.

The primary navigation MUST:

* remain reachable from the main application screens
* clearly indicate the current destination
* use Persian labels/icons appropriate to the destination
* remain usable in portrait and landscape
* avoid excessive navigation items
* preserve the current exercise/session state when navigating away where the product flow permits

### Exercise Screen

During active gameplay, navigation MUST NOT compete with the exercise.

The exercise screen should prioritize:

```text
Board
Question / Instruction
Answer Controls
Feedback
Timer / Progress
```

The primary application navigation may be hidden, minimized, or replaced by a compact back/exit control during active gameplay.

Leaving an active session MUST use an explicit action when doing so could cause progress loss.

### Coach, Parent, and Admin

Mobile navigation for other roles should expose only the destinations relevant to that role.

Examples:

```text
Coach:
Home
Students
Assignments
Progress
Profile

Parent:
Home
Children
Progress
Profile

Admin:
Dashboard
Users
Content
Analytics
More
```

These are conceptual navigation groups, not mandatory final route names.

The implementation MUST derive available navigation from authorization rather than merely hiding unauthorized pages visually.

### Navigation Drawer / Secondary Menu

A secondary menu may contain lower-frequency destinations such as:

* Settings
* Help / Support
* Privacy
* About
* Administrative tools
* Account actions

The secondary menu should not become a dumping ground for primary workflows.

### Mobile Navigation State

Navigation state MUST behave predictably across:

* route changes
* browser back/forward
* page refresh
* authentication changes
* role changes
* responsive breakpoint changes

Opening or closing a mobile navigation menu MUST NOT unexpectedly reset page state.

### Accessibility

Mobile navigation MUST provide:

* an accessible menu/control label
* keyboard accessibility where applicable
* visible focus state
* clear current-page indication
* appropriate focus management when a drawer/dialog opens
* a way to close an opened navigation surface
* no interaction that depends exclusively on hover

### Implementation Rule

Do not introduce a new navigation framework solely for mobile.

Reuse the existing routing and layout architecture.

Mobile navigation is a presentation concern; authorization remains server-side and capability-based.

The final navigation structure MUST be validated on narrow mobile portrait and landscape viewports.
