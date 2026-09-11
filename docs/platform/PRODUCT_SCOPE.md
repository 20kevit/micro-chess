# MicroChess — Product Scope

## 1. Document Status

**Status:** Accepted
**Document Type:** Product Scope

This document defines the product scope and long-term direction of MicroChess.

It describes:

* what MicroChess is
* who it serves
* which capabilities belong to the product
* which capabilities are part of the current platform expansion
* which capabilities are future direction
* which capabilities are explicitly out of scope

This document defines product requirements and boundaries, not low-level implementation details.

Technical implementation belongs in:

* `ARCHITECTURE.md`
* `DATA_MODEL.md`
* `API_CONTRACTS.md`
* `SECURITY.md`
* `UX_AND_DESIGN.md`
* domain-specific specifications
* accepted ADRs under `decisions/`

---

# 2. Product Definition

MicroChess is a chess-training platform focused on developing specific chess skills through short, isolated, interactive exercises.

MicroChess is **not** intended to be a complete chess-playing platform.

Its primary purpose is to help players improve individual chess skills through:

* focused exercises
* immediate feedback
* repetition
* progress tracking
* exercise-specific ratings
* gamification
* detailed training history
* performance analysis
* eventually, adaptive training

The product is designed primarily for:

* children
* teenagers
* beginner and intermediate chess players
* chess students
* chess coaches

The experience should remain simple and approachable for young players while providing enough depth for serious training and analysis.

---

# 3. Scope Levels

This document distinguishes three levels of scope.

## 3.1 Current Platform Scope

Capabilities intended to be implemented as part of the current platform expansion and represented by the current Master Plan phases.

These are implementation requirements when their corresponding phase/specification is active.

## 3.2 Future Product Direction

Capabilities that MicroChess is expected to support later.

Future capabilities may influence architectural boundaries and data preservation, but they are **not implementation requirements** unless explicitly promoted into an accepted phase or domain specification.

## 3.3 Explicitly Out of Scope

Capabilities intentionally excluded from the current product direction.

They must not be implemented merely because they appear technically useful or easy to add.

---

# 4. Core Product Philosophy

## 4.1 Child First

The interface should be understandable and engaging for children without becoming childish or visually overwhelming.

The product should work well for:

* children using tablets
* children using phones
* teenagers
* adults
* coaches

Users should not need to understand chess-engine terminology to use the exercises.

---

## 4.2 Skill First

Each exercise should focus on a clearly defined chess skill.

Examples:

* Piece Recognition → recognizing pieces
* Legal Destinations → legal movement
* Captures → identifying captures
* Pin → recognizing pins
* Mental Calculation → calculating without seeing the board

An exercise should not become a complete chess game unless explicitly designed as one.

---

## 4.3 Practice Must Produce Useful Data

Meaningful training activity should produce reliable historical data.

The platform should eventually be able to answer questions such as:

* What does this player struggle with?
* Which exercises are improving?
* Which exercises are too easy?
* Which exercises are too difficult?
* How quickly does the player answer?
* Is accuracy improving?
* Is the player's exercise rating improving?
* How consistent is the player?
* Which skills deteriorate after inactivity?
* Which exercises may correlate with improvement in other exercises?

Data collection must be considered from the beginning so that important historical information is not lost.

---

## 4.4 Gamification Must Support Learning

Gamification is a major product capability.

Rewards should encourage:

* accuracy
* improvement
* consistency
* meaningful practice
* mastery
* healthy streaks
* meaningful milestones

The system should avoid rewarding excessive low-quality activity merely because it increases attempt counts.

---

## 4.5 Progressive Complexity

The product should feel simple at the surface while becoming more powerful as the player's needs grow.

The intended progression is approximately:

```text
Player
  ↓
Exercises
  ↓
Progress
  ↓
Ratings
  ↓
Achievements
  ↓
Analytics
  ↓
Personalized Training
```

Users should not need to understand the underlying platform complexity.

---

# 5. Primary User Types

## 5.1 Player

The player is the primary product user.

A registered player can:

* create an account
* manage a profile
* practice exercises
* use Practice mode
* use Speed mode where available
* earn XP
* earn achievements
* build streaks
* improve exercise-specific ratings
* review training history
* view analytics
* compare progress across time periods
* manage privacy settings
* connect external chess identities
* contact administrators

---

## 5.2 Guest Player

A guest can use the core exercise experience without creating an account.

Guest activity may include:

* exercise attempts
* scores
* temporary progress
* temporary training state
* session information

Guest data should be retained sufficiently to support migration into a registered account.

Guest functionality must not create a separate long-term product identity.

Guest migration rules are defined in:

`accounts/SESSIONS_AND_GUESTS.md`

---

## 5.3 Coach

Coach functionality is part of the product direction.

A coach should eventually be able to:

* manage students
* create groups
* assign exercises
* assign training plans
* monitor progress
* review performance
* add notes
* compare authorized students
* identify weaknesses
* track improvement

The current platform should establish the identity and relationship foundations required for these capabilities without prematurely implementing the complete coach product.

---

## 5.4 Parent

Parent functionality is part of the product direction.

A parent should eventually be able to:

* manage relationships with one or more children
* view authorized progress information
* receive reports
* monitor training activity
* manage explicitly authorized child-related settings

Parent access must always be permission-controlled.

A parent must never automatically receive unrestricted access to all student data.

---

## 5.5 Administrator

Administrators manage the platform and its content.

The administration product should eventually support:

* user management
* role management
* exercise management
* puzzle management
* generator management
* analytics
* account-status management
* audit review
* support handling
* relevant operational information

Administrative functionality is a first-class product area.

---

# 6. Account Scope

Account creation is intentionally lightweight.

Initial registration requires only:

* username
* password

Registration does not initially require:

* email
* phone number
* real name
* FIDE ID
* Lichess account
* Chess.com account

Additional information may be added later through the profile.

The detailed authentication rules belong in:

`accounts/AUTHENTICATION.md`

---

# 7. Player Profile Scope

A registered player should have a useful profile.

## Identity

* username
* display name
* avatar
* bio

## Optional Personal Information

The product may support optional personal information where it provides clear value and is covered by explicit privacy rules.

Possible examples include:

* name
* age-related information
* country
* city
* preferred language

None of these should be required for initial registration unless a future accepted requirement explicitly changes that decision.

## External Chess Identities

The profile may contain:

* FIDE identity
* FIDE rating information
* Lichess identity
* Lichess rating information
* Chess.com identity
* Chess.com rating information

External ratings remain separate from MicroChess ratings.

Player-supplied external information is considered self-reported unless independently verified.

Detailed profile rules belong in:

`accounts/USER_PROFILES.md`

---

# 8. External Chess Profiles

Initial supported external identities:

* FIDE
* Lichess
* Chess.com

External identities may eventually support:

* initial level estimation
* external rating comparison
* MicroChess rating comparison
* player segmentation
* difficulty analysis
* progression comparison

External chess services are optional integrations and must not be required for core MicroChess training.

---

# 9. Exercise Scope

Exercises are the central training units of MicroChess.

An exercise has a stable product identity and may define:

* display information
* category
* availability
* supported modes
* difficulty
* rating behavior
* scoring behavior
* XP behavior
* content source
* product metadata

The shared exercise architecture must support different interaction models without requiring unrelated infrastructure for every exercise.

Exercise-specific rules remain defined by the exercise itself and its domain specification.

---

# 10. Exercise Modes

## 10.1 Practice

Practice mode is primarily for learning.

It may:

* be untimed
* provide feedback
* allow repeated attempts
* prioritize learning over competition

## 10.2 Speed

Speed mode is primarily for timed performance.

It may:

* use a time limit
* track response time
* use specialized scoring
* use streak-based progression
* use specialized content

Not every exercise must support both modes.

Mode availability is an exercise-level product decision.

---

# 11. Exercise-Specific Ratings

MicroChess should not reduce player skill to one global rating.

Applicable exercises or skill areas have independent ratings.

For example:

```text
Piece Recognition       1180
Legal Destinations      1245
Captures                1310
Pins                    1090
Mental Calculation      1375
```

The rating system must preserve:

* current rating
* rating history
* rating changes
* provisional state where applicable

The data should remain sufficient to support future rating improvements and recalculation.

The exact rating algorithm belongs in:

`training/RATINGS.md`

---

# 12. Training History

MicroChess must preserve meaningful training history.

Relevant historical information may include:

* player or guest identity
* exercise
* puzzle/content
* mode
* attempt
* result
* correctness
* score
* response time
* rating before
* rating change
* rating after
* XP earned
* session
* timestamp
* relevant difficulty information
* relevant content/configuration information

Historical records must not be casually overwritten.

Training history is a primary source for progress analysis, rating history, analytics, and future personalization.

Detailed rules belong in:

`training/ATTEMPTS_AND_HISTORY.md`

---

# 13. Player Dashboard

Registered players should eventually have a comprehensive but understandable dashboard.

It may provide:

### Overview

* recent activity
* current streak
* XP
* level
* achievements
* recent rating changes

### Skill Profile

* exercise ratings
* strongest areas
* weaker areas
* improvement areas
* rating progression

### Activity

* recent sessions
* attempts
* training time
* active days

### Progress

* daily
* weekly
* monthly
* long-term

### Analytics

* accuracy
* response time
* rating trends
* exercise comparison
* period comparison

### Gamification

* XP progress
* level progress
* streaks
* achievements
* badges
* milestones

The dashboard should prioritize useful information rather than expose every available metric at once.

---

# 14. Analytics Scope

Analytics is a first-class product capability.

## Player Analytics

May include:

* performance
* progress
* rating
* accuracy
* response speed
* consistency
* engagement

## Exercise Analytics

May include:

* usage
* accuracy
* completion
* response time
* rating distribution
* performance trends
* observed difficulty

## Puzzle Analytics

May include:

* attempts
* accuracy
* response time
* observed difficulty
* repeated failures
* content quality indicators

## Platform Analytics

May include:

* users
* active users
* sessions
* attempts
* retention/activity indicators
* exercise usage
* performance trends

Detailed analytics definitions belong in:

`training/ANALYTICS.md`

and:

`admin/ADMIN_ANALYTICS.md`

---

# 15. Time-Based Analytics

Analytics should support:

* last 7 days
* last 30 days
* last 90 days
* all time
* custom date range

Where meaningful, analytics should support comparison with an equivalent previous period.

Examples:

```text
Last 7 days
vs
Previous 7 days
```

```text
Last 30 days
vs
Previous 30 days
```

Comparison metrics may include:

* accuracy
* attempts
* training time
* rating
* rating change
* response time
* active days
* exercise completion
* XP
* streak

---

# 16. Gamification Scope

MicroChess should support:

* XP
* levels
* streaks
* daily goals
* weekly goals
* achievements
* badges
* milestones
* personal records
* exercise mastery
* challenges
* leaderboards

Gamification must support meaningful training rather than activity farming.

Detailed rules belong in:

`training/GAMIFICATION.md`

---

# 17. Administration and Content Scope

Administration is a major product area.

## User Management

Administrators should eventually be able to:

* search users
* filter users
* inspect permitted profile information
* manage account status
* manage roles
* review relevant progress information

## Exercise Management

Administrators should be able to manage appropriate exercise-level configuration, including:

* metadata
* availability
* ordering
* difficulty configuration
* rating configuration
* supported modes
* scoring
* XP
* visibility

## Puzzle Management

Administrators should be able to:

* browse
* search
* filter
* inspect
* create
* edit
* validate
* review
* publish
* retire
* inspect performance

Content must have an explicit lifecycle so that saving or generating a puzzle does not automatically make it active.

---

# 18. Manual Puzzle Creation

Administrators should be able to manually create puzzles for supported exercises.

Manual creation must respect:

* exercise-specific validation
* answer validation
* difficulty metadata
* rating metadata
* content status
* preview/review requirements

A saved draft must not automatically become active content.

Detailed content rules belong in:

`admin/PUZZLE_MANAGEMENT.md`

---

# 19. Puzzle Generators

Puzzle generation is a first-class content capability.

The intended workflow is:

```text
Select Exercise
      ↓
Select Generator
      ↓
Configure Parameters
      ↓
Generate Candidates
      ↓
Validate
      ↓
Deduplicate
      ↓
Review
      ↓
Approve
      ↓
Publish
```

Administrators should eventually be able to specify:

* exercise
* generator
* generation constraints
* target difficulty
* target rating/range
* quantity

Generated content must pass exercise-specific validation.

Generation metadata should remain available for content traceability.

Generated content must never bypass review and approval merely because it was produced by a trusted generator.

Detailed requirements belong in:

`admin/GENERATORS.md`

---

# 20. Difficulty Calibration — Future Direction

MicroChess should eventually compare declared difficulty with observed player performance.

For example:

```text
Declared Rating: 1400
Observed Rating: 1285
Attempts: 4210
Accuracy: 79%
```

The system may eventually recommend adjusted difficulty or rating values.

This is a **future capability**.

The current platform should preserve sufficient historical information to support it later, but does not need to implement automated calibration unless an accepted phase explicitly requires it.

---

# 21. Support

The current product direction includes a basic in-platform support/contact mechanism.

The initial support capability should remain simple:

* player creates a support request
* administrators can review it
* administrators can respond
* request status can be managed

The initial implementation does not require external communication channels.

Future delivery channels may include:

* email
* push notifications
* Telegram
* other communication channels

Detailed support behavior belongs in the relevant domain specification.

---

# 22. Coach / Student Direction — Future

The long-term coach product may support:

* coach accounts
* student relationships
* invitations
* groups
* classes
* assignments
* training plans
* progress monitoring
* notes
* reports

The platform should establish relationship boundaries without prematurely implementing the complete coach product.

Detailed relationship behavior belongs in:

`relationships/COACH_STUDENT.md`

---

# 23. Parent / Student Direction — Future

The long-term parent product may support:

* multiple children
* child progress
* training activity
* reports
* notifications
* explicitly authorized permissions

Parent access must always be governed by explicit authorization and privacy rules.

Detailed behavior belongs in:

`relationships/PARENT_STUDENT.md`

---

# 24. Adaptive Training — Future

MicroChess should eventually support personalized training.

Potential capabilities include:

* recommended exercises
* recommended difficulty
* weak-skill detection
* personalized training plans
* adaptive puzzle selection
* difficulty adjustment
* skill progression models
* coach-assisted recommendations

These capabilities are future product direction.

Current implementation should preserve reliable training history and analytics without introducing machine-learning infrastructure prematurely.

---

# 25. Notifications — Future

Future notification capabilities may include:

* training reminders
* streak reminders
* achievement notifications
* coach assignments
* parent notifications
* system notifications

Notification delivery channels are future concerns and are not part of the current core training experience.

---

# 26. Future Authentication — Future

Future authentication capabilities may include:

* email verification
* account recovery
* MFA
* passkeys
* social login
* additional identity providers

These must not increase initial registration friction unless explicitly brought into current scope.

---

# 27. Privacy and Data Minimization

MicroChess should collect only information that provides meaningful product value.

The following are intentionally not required for initial registration:

* email
* phone
* real name
* external chess identities

Personal information should have explicit privacy rules.

Public-facing features should avoid exposing private information unnecessarily.

Examples:

* leaderboards should normally use usernames/display names
* external identities should be optional
* related-user access must be permission-controlled
* sensitive information must not be exposed merely because a relationship exists

Detailed security and privacy rules belong in:

`SECURITY.md`

---

# 28. Accessibility

MicroChess should support accessible interaction through:

* keyboard navigation
* touch interaction
* sufficient contrast
* clear feedback
* appropriately sized interactive targets
* readable typography
* screen-reader compatibility where practical
* reduced-motion preferences where appropriate

Accessibility requirements must coexist with the child-friendly design.

Detailed UX requirements belong in:

`UX_AND_DESIGN.md`

---

# 29. Internationalization

MicroChess must remain i18n-ready.

Current primary language:

```text
Persian
```

The product must support future additional languages without redesigning the application.

The UI must correctly handle:

* RTL languages
* LTR languages
* mixed-direction content

Chessboard coordinates and chess notation must preserve appropriate LTR behavior inside RTL interfaces.

---

# 30. Responsive Product Requirements

MicroChess must support:

* desktop
* tablet
* mobile portrait
* mobile landscape

The exercise experience has a particularly strict requirement:

> Every exercise/play screen must fit completely within the visible viewport without normal vertical page scrolling.

This requirement applies across supported viewport sizes and orientations.

Responsive layout must be used rather than blindly hiding overflow.

Detailed UX requirements belong in:

`UX_AND_DESIGN.md`

---

# 31. Current Exercise Catalog

The official exercise roadmap is:

|  # | Exercise               | Slug                      |
| -: | ---------------------- | ------------------------- |
|  1 | تشخیص مهره             | `piece-recognition`       |
|  2 | مقصدهای قانونی         | `legal-destinations`      |
|  3 | گرفتن مهره‌ها          | `captures`                |
|  4 | مهره‌های بی‌دفاع       | `undefended-pieces`       |
|  5 | کیش دادن               | `give-check`              |
|  6 | رفع کیش                | `get-out-of-check`        |
|  7 | مسیریابی               | `pathfinding`             |
|  8 | مسیریابی با مانع       | `pathfinding-obstacles`   |
|  9 | ترازو                  | `balance-scale`           |
| 10 | کدام طرف سنگین‌تر است؟ | `heavier-side`            |
| 11 | آچمز                   | `pin`                     |
| 12 | صفحه‌ی حفظی            | `chinese-board`           |
| 13 | آیا مات است؟           | `is-checkmate`            |
| 14 | خانه‌یابی ذهنی         | `blindfold-square-vision` |
| 15 | محاسبه‌ی ذهنی          | `blindfold-calculation`   |
| 16 | گشایش ذهنی             | `opening-traps`           |
| 17 | گشایش معکوس            | `reverse-opening`         |
| 18 | مهره‌ی گرفتار          | `trapped-pieces`          |

The roadmap number is a product identifier and must not be confused with database ordering.

Current implementation status is maintained in:

`IMPLEMENTATION_STATE.md`

The exercise catalog may expand in the future.

---

# 32. Explicitly Out of Scope

The following are not part of the current core platform expansion unless explicitly promoted into an accepted specification:

* full online chess gameplay
* real-time multiplayer chess
* arbitrary user-game engine analysis
* tournament management
* chess federation management
* online payments
* subscription billing
* marketplace
* video courses
* live video classes
* social feed
* public messaging platform
* full social network
* advertising platform

These capabilities may be considered separately in the future.

---

# 33. What MicroChess Is Not

MicroChess is not:

* a replacement for a full chess client
* a chess engine
* a tournament manager
* a social network
* a generic educational LMS
* a video course platform
* a chess federation database
* a replacement for FIDE
* a replacement for Lichess
* a replacement for Chess.com

External chess services are optional integrations, not dependencies for core training.

---

# 34. Product Outcome Questions

The product should eventually be able to answer meaningful questions for each major user.

## Player

* What am I good at?
* What do I need to improve?
* Am I improving?
* Which exercises should I practice?
* How has my exercise rating changed?
* How consistent am I?
* How does my recent performance compare with previous periods?

## Coach

* Which skills does this student need to work on?
* Is the student improving?
* Which exercises are causing difficulty?
* Is the student practicing consistently?

## Administrator

* Which exercises are effective?
* Which exercises are too easy?
* Which exercises are too difficult?
* Which puzzles are problematic?
* How are users progressing?
* Where are users dropping out?
* Which content should be improved?

## Future Adaptive Training

* What should this player practice next?
* At what difficulty?
* Why is that recommendation appropriate?

These are product outcomes, not implementation algorithms.

---

# 35. Product Evolution Principle

MicroChess should evolve from a simple training experience into a sophisticated training platform without requiring a fundamental product redesign.

The platform should therefore preserve reliable foundations for:

* user identity
* player profiles
* guest identity
* training history
* exercise-specific ratings
* rating history
* analytics source data
* gamification history
* exercise metadata
* puzzle metadata
* content lifecycle
* administrative permissions
* relationships
* privacy boundaries

These foundations do not require implementing every future capability immediately.

Future capabilities should build on them rather than bypass them.

---

# 36. Scope Change Rule

New major capabilities must be explicitly evaluated before implementation.

A proposed capability should answer:

* What user problem does it solve?
* Which user type benefits?
* Does it support the MicroChess mission?
* Is it current scope or future direction?
* What data does it require?
* What architectural impact does it have?
* Does it introduce unnecessary complexity?
* Can it be implemented without weakening existing product principles?

Architecturally significant decisions should be recorded in an appropriate ADR.

A feature must not become an implementation requirement merely because it is mentioned as future direction in this document.

---

# 37. Final Product Direction

The long-term MicroChess vision is:

> **A child-friendly, data-driven chess skill training platform that measures individual chess abilities, makes improvement visible and motivating, and eventually adapts training to each player's needs.**

The product should feel simple to a child while being powerful enough for serious analysis by players, coaches, and administrators.

The complexity belongs inside the platform.

The user experience should remain simple.
