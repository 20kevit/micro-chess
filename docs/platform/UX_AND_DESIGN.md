# MicroChess Platform — UX & Design

## 1. Document Status

**Status:** Accepted
**Document Type:** Target UX & Design Specification
**Scope:** Platform-wide interaction, responsive behavior, accessibility, visual principles, navigation, and player experience

This document defines platform-level UX rules for MicroChess.

It complements:

* `PRODUCT_SCOPE.md`
* `ARCHITECTURE.md`
* `SECURITY.md`
* `DESIGN_SYSTEM.md`
* exercise-specific UX specifications

Exercise-specific interaction rules take precedence when they are more specific.

This document describes the **target experience**.

It does not describe current implementation status.

---

# 2. UX Principles

MicroChess is:

* child-first
* chess-skill focused
* Persian-first
* mobile-first
* simple before complex
* friendly without being childish
* feedback-driven
* fast to use
* accessible
* visually clear
* data-informed without exposing unnecessary complexity

Every important screen should help the user understand:

```text
What should I do?
        ↓
What happened?
        ↓
What should I do next?
```

Prefer clarity over decoration.

---

# 3. Product Feel

The product should feel:

* friendly
* modern
* clean
* energetic
* trustworthy
* focused
* appropriate for children and teenagers
* credible for parents, coaches, and serious players

Avoid:

* excessive gradients
* excessive shadows
* noisy backgrounds
* unnecessary animation
* overly childish visual language
* dense enterprise-style interfaces for players
* visual effects that compete with the exercise

Existing design tokens and components are authoritative.

Do not introduce one-off colors, spacing, typography, or component patterns when an existing system component already fits.

---

# 4. Language and Direction

MicroChess is i18n-ready from the beginning.

Current default:

```text
Language: Persian
Direction: RTL
```

Rules:

* user-facing text is Persian
* translation keys must not depend on hard-coded Persian wording
* layouts must support RTL correctly
* numbers must remain readable
* mixed Persian/Latin content must preserve correct bidi behavior
* future languages must be possible without redesigning the interface

Chess-specific content may retain its native direction and notation.

For example:

```text
Application UI → RTL
Chess notation / board behavior → chess-native
```

---

# 5. Responsive Design

The platform must support:

* desktop
* tablet
* mobile portrait
* mobile landscape

Responsive behavior should be based on available space, not device labels alone.

The UI should reflow rather than require horizontal scrolling.

Representative viewport sizes must be checked whenever significant UI changes are made.

---

# 6. Exercise Screen Rule

Exercise screens have a stricter requirement than ordinary application screens.

> The active exercise experience must fit within the visible viewport without normal page scrolling whenever reasonably possible.

This includes:

* board
* question/instruction
* answer controls
* feedback
* progress
* timer
* primary action

The chessboard receives the highest visual priority.

Do not solve layout problems by blindly using:

```css
overflow: hidden;
```

Instead:

* calculate available viewport space
* resize the board
* collapse secondary information
* adapt control placement
* reduce nonessential UI
* preserve the primary interaction

Dashboards, analytics pages, and administration pages may scroll normally.

---

# 7. Navigation Principles

Navigation should remain simple for players.

Authenticated players should have clear access to:

* Home/Dashboard
* Exercises
* Progress
* Profile

Additional destinations such as Settings and Support may be placed in secondary navigation.

Admin and Coach interfaces may use denser navigation because their workflows are inherently more complex.

Navigation must reflect authorization, but visual hiding is not a security mechanism.

---

# 8. Mobile Navigation

Mobile navigation must be designed deliberately rather than treated as a collapsed desktop sidebar.

## Player

Primary destinations should normally include:

```text
Home
Exercises
Progress
Profile
```

Lower-frequency destinations may include:

* Settings
* Support
* Privacy
* Account actions

## Coach

Conceptually:

```text
Home
Students
Assignments
Progress
Profile
```

## Parent

Conceptually:

```text
Home
Children
Progress
Profile
```

## Admin

Conceptually:

```text
Dashboard
Users
Content
Analytics
More
```

These are conceptual groups, not mandatory route names.

The implementation must derive available navigation from authorization.

---

# 9. Active Exercise Navigation

During active gameplay, application navigation must not compete with the exercise.

Prioritize:

```text
Board
Question / Instruction
Answer Controls
Feedback
Timer / Progress
```

The normal application navigation may be:

* minimized
* replaced with a compact back/exit action
* temporarily hidden

Leaving an active session must use an explicit action when progress may be lost.

Navigation state must not unexpectedly reset active exercise state.

---

# 10. Exercise Discovery

The exercise catalog should:

* show available exercises
* clearly distinguish unavailable exercises
* indicate `به‌زودی` for exercises that are not yet available
* communicate the purpose of each exercise
* avoid unnecessary chess terminology
* remain simple on the default screen
* remain extensible for future filtering/search

An unavailable exercise must never appear playable.

---

# 11. Exercise Start Flow

Starting an exercise should require minimal interaction.

Typical flow:

```text
Exercise
   ↓
Mode selection, when applicable
   ↓
Start
   ↓
Training
```

Do not introduce unnecessary configuration before every attempt.

Practice and Speed should be clearly differentiated when both are supported.

---

# 12. Dashboard

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

The dashboard should summarize progress.

It should not become an analytics report.

Detailed analytics belong in dedicated views.

---

# 13. Feedback

Feedback should be:

* immediate
* understandable
* visually clear
* consistent
* actionable when appropriate

Correctness must not rely on color alone.

Use combinations of:

* color
* text
* icons
* position/state
* controlled motion

Avoid excessive celebration for trivial actions.

Feedback should support learning rather than interrupt it.

---

# 14. Loading, Empty, and Error States

Every major screen must have meaningful:

* loading state
* empty state
* error state
* recovery/retry path

Empty states should explain:

1. what is missing
2. why it matters
3. what the user can do next

Example:

```text
هنوز تمرینی انجام نداده‌ای.
اولین تمرینت را شروع کن تا پیشرفتت را اینجا ببینی.
```

Do not create dead-end empty states.

Technical details must never be exposed to users, including:

* stack traces
* SQL errors
* internal identifiers
* implementation details

---

# 15. Forms

Forms must provide:

* clear labels
* appropriate input types
* visible validation
* useful Persian error messages
* preserved valid input after failure
* keyboard-friendly interaction
* obvious required fields

Do not rely exclusively on placeholder text as a label.

---

# 16. Touch Interaction

Interactive controls must be comfortable on touch devices.

Avoid:

* tiny controls
* tightly packed buttons
* hover-only functionality
* interactions requiring unnecessary precision

Where drag interaction exists, provide an alternative when practical.

Chess interactions must remain usable on touch devices.

---

# 17. Accessibility

Accessibility is part of the primary experience.

Target:

> WCAG 2.2 AA where applicable.

Minimum expectations include:

* semantic HTML
* keyboard navigation
* visible focus
* meaningful accessible names
* correct labels
* sufficient contrast
* no color-only meaning
* reduced-motion support
* responsive text/layout
* appropriate screen-reader semantics

Do not claim full accessibility compliance unless it has been tested.

---

# 18. Chessboard Accessibility

The chessboard is a specialized interactive component.

Where practical, provide:

* accessible board labeling
* identifiable squares
* keyboard-compatible alternatives
* textual result/feedback
* state information not based only on color

Touch usability must remain strong.

If a fully equivalent accessible board interaction is not possible for a particular exercise, document the limitation rather than claiming complete support.

---

# 19. Motion

Animation is optional enhancement.

It must never be required to understand:

* state
* correctness
* progress
* navigation
* results

Respect:

```text
prefers-reduced-motion
```

When reduced motion is enabled:

* remove unnecessary transitions
* reduce decorative movement
* preserve essential feedback
* avoid motion that obscures interaction

Avoid animation during time-sensitive gameplay unless it has clear functional value.

---

# 20. Performance UX

The UI should become useful quickly.

Prefer:

* lightweight initial rendering
* small API payloads
* lazy loading for noncritical content
* cached static assets
* progressive rendering where useful

Do not block the whole application while unrelated data is loading.

Exercise gameplay prioritizes responsiveness over decorative content.

---

# 21. Role-Based UX

The interface should reflect the user's authorized capabilities.

## Player

Focus on:

* training
* exercises
* progress
* goals
* achievements
* profile

## Coach

Focus on:

* students
* assignments
* progress
* training insights

## Parent

Focus on:

* children
* progress
* reports

## Admin

Focus on:

* users
* exercises
* puzzles
* generators
* analytics
* support
* operational management

Frontend visibility must not replace backend authorization.

---

# 22. Privacy UX

The UI should clearly distinguish:

* public profile information
* private profile information
* personal training data
* related-user data
* administrative data

Private information must not be displayed merely because a page is reachable.

The amount of visible information should be limited to the user's authorized scope.

---

# 23. Gamification UX

Gamification may expose:

* XP
* levels
* streaks
* daily/weekly goals
* achievements
* badges
* personal records
* mastery
* leaderboards

Avoid:

* manipulative urgency
* meaningless point farming
* excessive celebration
* visual overload
* excessive notifications

Learning quality has priority over engagement metrics.

---

# 24. Analytics UX

Player analytics should be understandable without statistical expertise.

Prefer meaningful metrics such as:

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

Charts should answer a user question.

Do not add charts merely because charts are available.

Administrative analytics may be substantially more detailed.

---

# 25. Player Progress UX

Progress should emphasize change over time.

Useful views may include:

* current exercise rating
* rating history
* accuracy
* response time
* active days
* exercise mastery
* recent attempts
* training streak
* personal records

The interface should distinguish:

```text
Current State
```

from:

```text
Historical Progress
```

Do not make the user infer this distinction from ambiguous visuals.

---

# 26. Exercise Feedback Hierarchy

During an exercise, information should generally be prioritized as:

```text
1. What must I do?
2. Main interaction
3. Immediate result
4. Progress/timing
5. Secondary explanation
6. Optional detail
```

Secondary content should not reduce the usability of the main interaction.

---

# 27. Design-System Rule

`DESIGN_SYSTEM.md` is authoritative for:

* colors
* typography
* spacing
* component tokens
* borders
* radii
* shadows
* standard UI components

Do not redefine these in feature-specific pages unless a genuine exception is required.

Do not introduce one-off styling to solve a problem already solved by the design system.

---

# 28. Frontend Architecture Constraints

UX implementation must respect the existing frontend architecture.

Agents MUST:

1. inspect existing components before creating new ones
2. reuse design-system components
3. reuse layout primitives
4. preserve existing exercise behavior
5. avoid speculative component frameworks
6. avoid duplicated UI logic
7. keep presentation components focused
8. keep business rules outside presentation components
9. verify responsive behavior
10. run relevant type checks, tests, and builds

Do not rewrite the frontend architecture merely to improve visual consistency.

---

# 29. UI State Requirements

Important user-facing flows should explicitly handle:

```text
Initial
Loading
Success
Empty
Validation Error
Authorization Error
Server Error
Retry
Completed
```

Not every screen requires every state.

The required states depend on the feature.

---

# 30. Authorization UX

The UI should avoid presenting actions the current user cannot perform.

However:

> Hiding a button is not authorization.

The backend remains authoritative.

When authorization changes during a session, the UI should recover gracefully from the server's authoritative response.

---

# 31. Responsive Validation

Every significant UI change must be checked at:

```text
Mobile Portrait
Mobile Landscape
Tablet
Desktop
```

Exercise screens additionally require verification that:

* the board remains usable
* primary controls remain visible
* feedback remains visible
* timers remain visible where applicable
* text does not overlap controls
* normal page scrolling does not appear
* touch interaction remains usable

---

# 32. RTL Validation

Every significant UI change involving text/layout must be checked for:

* RTL alignment
* mixed Persian/Latin text
* numbers
* punctuation
* icons
* directional controls
* form alignment
* navigation
* modal/drawer behavior

Chessboard orientation must remain independent of ordinary RTL layout behavior.

---

# 33. UX Testing

Important flows should be tested for:

* successful interaction
* invalid input
* loading
* failure
* retry
* empty data
* narrow viewport
* touch interaction
* keyboard interaction where applicable
* authorization differences
* long text
* Persian/RTL behavior
* reduced motion where relevant

Exercise-specific acceptance criteria remain authoritative for individual exercises.

---

# 34. UX Implementation Scope

This document defines platform UX.

It does not authorize implementation of:

* future screens
* future roles
* future notifications
* future adaptive training
* future analytics views

merely because their UX could be described here.

The active phase determines implementation scope.

---

# 35. UX Definition of Done

A platform UI feature is complete when applicable:

1. required states exist
2. Persian/RTL behavior works
3. responsive behavior works
4. authorization is respected
5. accessibility basics are implemented
6. loading/empty/error states are handled
7. the existing design system is reused
8. exercise viewport rules are preserved where applicable
9. relevant tests pass
10. existing unrelated UI is not unnecessarily changed

Rendering successfully is not sufficient evidence of completion.

---

# 36. Final UX Priorities

MicroChess should prefer:

```text
Clarity
    >
Decoration

Learning
    >
Engagement Tricks

Simple Interaction
    >
Configuration

Responsive Adaptation
    >
Forced Scrolling

Accessible Behavior
    >
Visual-Only Behavior

Existing Design System
    >
One-Off Styling

Immediate Useful Feedback
    >
Unnecessary Animation
```

The interface should feel simple to a child while remaining credible and powerful enough for serious players, coaches, parents, and administrators.
