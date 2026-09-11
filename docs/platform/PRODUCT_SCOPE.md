# MicroChess — Product Scope

## 1. Document Status

**Status:** Accepted
**Document Type:** Product Scope
**Scope:** Product identity, users, capabilities, boundaries, experience principles, and long-term direction

This document defines **what MicroChess is and what product capabilities belong to it**.

It does not define low-level implementation details.

Technical behavior belongs in:

* `ARCHITECTURE.md`
* `DATA_MODEL.md`
* `API_CONTRACTS.md`
* `SECURITY.md`
* `UX_AND_DESIGN.md`
* domain specifications
* accepted ADRs

Implementation order belongs in:

* `MASTER_PLAN.md`
* phase specifications

Current repository reality belongs in:

* `IMPLEMENTATION_STATE.md`

---

# 2. Product Definition

MicroChess is a chess-training platform focused on developing individual chess skills through short, isolated, interactive exercises.

It is designed to make chess improvement:

* focused
* measurable
* motivating
* repeatable
* understandable

MicroChess is **not** a complete chess-playing platform.

Its core product loop is:

```text
Choose a skill
    ↓
Practice
    ↓
Receive feedback
    ↓
Repeat
    ↓
Measure progress
    ↓
Improve
```

The long-term product adds:

```text
Ratings
    ↓
Gamification
    ↓
Analytics
    ↓
Personalized training
```

---

# 3. Product Mission

MicroChess exists to help players improve individual chess skills rather than simply accumulate games.

The platform should make it easy for a player to understand:

* what skill is being trained
* whether the answer was correct
* how well the player is performing
* whether the player is improving
* which skills need more practice
* what to practice next

The complexity required to support these capabilities belongs inside the platform.

The user experience should remain simple.

---

# 4. Primary Audience

MicroChess is designed primarily for:

* children
* teenagers
* beginner chess players
* intermediate chess players
* chess students
* chess coaches
* parents supporting young players

Adults and stronger players should also be able to use the platform without the product becoming unnecessarily complicated.

---

# 5. Core Product Philosophy

## 5.1 Child First

The experience should be understandable to a child without being childish.

The interface should:

* minimize unnecessary complexity
* use clear language
* provide immediate feedback
* reduce cognitive overload
* work naturally on tablets and phones
* make progress visible

The product must remain useful for teenagers, adults, coaches, and serious learners.

---

## 5.2 Skill First

Each exercise focuses on a clearly defined chess skill.

Examples include:

* recognizing pieces
* identifying legal destinations
* identifying captures
* recognizing undefended pieces
* giving check
* escaping check
* finding paths
* identifying pins
* comparing material
* visualizing positions
* calculating without seeing the board

Exercises should remain focused on their intended skill.

An exercise should not become a general chess game unless explicitly designed as one.

---

## 5.3 Practice Should Produce Useful Evidence

Meaningful training activity should contribute to reliable historical data.

The platform should eventually be able to answer questions such as:

* What does this player struggle with?
* Which skills are improving?
* Which exercises are too easy?
* Which exercises are too difficult?
* How quickly does the player answer?
* Is accuracy improving?
* Is the exercise rating improving?
* How consistent is the player?
* Which skills deteriorate after inactivity?

Historical training data is therefore a core product asset.

---

## 5.4 Gamification Supports Learning

Gamification is intended to encourage meaningful training.

The product may reward:

* accuracy
* improvement
* consistency
* meaningful practice
* mastery
* healthy streaks
* milestones
* achievement

The system should avoid rewarding low-quality activity merely because it increases attempt counts.

---

## 5.5 Progressive Complexity

The product should feel simple initially and become more powerful as the player's needs grow.

The intended progression is:

```text
Player
  ↓
Exercises
  ↓
Progress
  ↓
Ratings
  ↓
Gamification
  ↓
Analytics
  ↓
Personalized Training
```

Users should not need to understand the underlying system architecture.

---

# 6. Product Scope Levels

This document distinguishes three scope levels.

## 6.1 Current Platform Scope

Capabilities that belong to the current platform roadmap.

They become implementation requirements when their corresponding phase or domain specification is active.

---

## 6.2 Future Product Direction

Capabilities that MicroChess is intended to support later.

Future direction may influence:

* architectural boundaries
* data preservation
* product decisions

but is **not implementation authorization**.

A future capability becomes implementation work only when explicitly promoted into an accepted phase or specification.

---

## 6.3 Explicitly Out of Scope

Capabilities deliberately excluded from the current product direction.

They must not be implemented merely because they appear technically useful.

---

# 7. User Types

## 7.1 Player

The player is the primary product user.

A registered player should eventually be able to:

* create an account
* manage a profile
* discover exercises
* practice exercises
* use Practice mode
* use Speed mode where supported
* review feedback
* track progress
* build exercise-specific ratings
* review training history
* earn XP
* earn achievements
* build streaks
* view mastery
* view analytics
* compare performance over time
* manage privacy settings
* connect external chess identities
* contact support

---

## 7.2 Guest Player

A guest can use the core training experience without creating an account.

Guest activity may include:

* exercise attempts
* feedback
* scores
* temporary progress
* temporary training history
* temporary ratings
* temporary gamification state where supported

Guest data should remain sufficient for safe migration into a registered account.

Guest is a temporary access state, not a long-term product identity and not a product role.

---

## 7.3 Coach

Coach functionality is part of the product direction.

A coach should eventually be able to:

* manage authorized students
* maintain student relationships
* create or manage assignments
* create training plans
* monitor progress
* review performance
* identify weaknesses
* track improvement
* organize students into groups/classes where justified
* provide notes or feedback where explicitly supported
* compare authorized students

Coach access must always be scoped to authorized relationships.

---

## 7.4 Parent

Parent functionality is part of the product direction.

A parent should eventually be able to:

* manage relationships with one or more children
* view authorized progress
* monitor training activity
* receive appropriate reports
* manage explicitly authorized settings

A parent does not automatically receive unrestricted access to student data.

---

## 7.5 Administrator

Administrators operate and manage the platform.

The administration product should eventually support:

* user management
* role management
* account-status management
* exercise management
* puzzle management
* content lifecycle management
* generator management
* analytics
* audit review
* support handling
* operational information

Administrative access is privileged and must remain subject to the security model.

---

# 8. Account Product Scope

Initial account creation is intentionally lightweight.

Initial registration requires:

* username
* password

Initial registration does not require:

* email
* phone number
* real name
* FIDE ID
* Lichess account
* Chess.com account

Additional profile information can be added later.

This minimizes friction and unnecessary data collection.

Detailed account behavior belongs in:

```text
accounts/
```

---

# 9. Player Profile Scope

Registered players should have a useful profile.

Possible profile capabilities include:

* username
* display name
* avatar
* bio
* preferred language
* optional age-related information
* optional location information
* privacy settings

Personal information is optional unless a later accepted product requirement makes it necessary.

The profile must remain separate from authentication credentials.

---

# 10. External Chess Identities

MicroChess may support external chess identities including:

* FIDE
* Lichess
* Chess.com

External identities are optional.

They may eventually support:

* displaying external ratings
* comparing external and MicroChess skill
* estimating initial difficulty
* player segmentation
* progression analysis

External ratings are separate from MicroChess exercise ratings.

Self-reported external ratings are unverified unless an explicit verification mechanism exists.

External accounts are not required for core MicroChess training.

---

# 11. Exercise Product

Exercises are the central product unit.

An exercise represents a specific chess skill and defines the experience required to practice it.

An exercise may specify:

* name and description
* category
* availability
* supported modes
* difficulty
* rating behavior
* scoring behavior
* XP behavior
* content source
* product metadata

Exercise-specific behavior remains specific to the exercise.

The platform should provide shared infrastructure without forcing every exercise into the same interaction model.

---

# 12. Exercise Experience

The exercise experience should follow a simple loop:

```text
Select exercise
      ↓
Receive question
      ↓
Interact
      ↓
Submit answer
      ↓
Receive feedback
      ↓
Continue / finish
```

The platform may layer:

* score
* timing
* rating
* XP
* mastery
* history

onto this experience without changing the fundamental interaction model.

---

# 13. Exercise Modes

## Practice

Practice mode prioritizes learning.

It may:

* be untimed
* provide detailed feedback
* allow repetition
* emphasize understanding
* reduce competitive pressure

---

## Speed

Speed mode prioritizes timed performance.

It may:

* use a time limit
* measure response time
* use specialized scoring
* use streak-based mechanics
* use specialized content

Not every exercise must support both modes.

Mode support is an exercise-level product decision.

---

# 14. Exercise Ratings

MicroChess should not reduce skill to one global rating.

Applicable exercises or skill areas should have independent ratings.

For example:

```text
Piece Recognition       1180
Legal Destinations      1245
Captures                1310
Pins                    1090
Mental Calculation      1375
```

The rating product should support:

* current rating
* rating history
* rating changes
* provisional state where applicable
* future rating improvements without destroying historical data

The rating algorithm belongs to:

```text
training/RATINGS.md
```

---

# 15. Training History

Training history is a core product capability.

Relevant historical information may include:

* player or guest identity
* exercise
* puzzle/content
* mode
* session
* question instance where applicable
* answer
* correctness
* score
* response time
* rating before
* rating change
* rating after
* XP earned
* timestamp
* relevant difficulty
* relevant content/configuration version

Historical records are valuable for:

* progress
* ratings
* analytics
* gamification
* future personalized training

Historical facts should not be casually overwritten.

Detailed behavior belongs in:

```text
training/ATTEMPTS_AND_HISTORY.md
```

---

# 16. Player Progress

The product should make progress understandable.

Player-facing progress may include:

* exercise completion
* attempt count
* accuracy
* response time
* training frequency
* rating progression
* mastery
* streak
* recent performance
* personal records

Basic player progress belongs to the player experience.

Full cross-player/platform analytics are a separate product capability.

---

# 17. Player Dashboard

A registered player's dashboard should eventually provide a useful summary rather than expose every available metric.

Possible areas:

### Overview

* recent activity
* current streak
* XP
* level
* achievements
* recent rating changes

### Skill Profile

* exercise ratings
* strengths
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
* long-term trends

### Gamification

* XP
* levels
* streaks
* achievements
* badges
* milestones

### Recommendations

Future adaptive recommendations may be shown when the adaptive-training capability exists.

---

# 18. Analytics Product Scope

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
* exercise comparison

## Exercise Analytics

May include:

* usage
* attempts
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
* repeated failures
* observed difficulty
* content-quality indicators

## Platform Analytics

May include:

* total users
* active users
* sessions
* attempts
* retention/activity indicators
* exercise usage
* platform trends

Detailed analytics behavior belongs in:

```text
training/ANALYTICS.md
admin/ADMIN_ANALYTICS.md
```

---

# 19. Analytics Periods

Player-facing analytics should eventually support:

* 7 days
* 30 days
* 90 days
* all time
* custom date range

Where useful, equivalent-period comparisons should be available.

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

Possible comparison metrics include:

* accuracy
* attempts
* training time
* rating
* rating change
* response time
* active days
* completion
* XP
* streak

---

# 20. Gamification Product Scope

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

Gamification exists to reinforce meaningful learning.

It should not turn the platform into an activity-counting game.

Detailed rules belong in:

```text
training/GAMIFICATION.md
```

---

# 21. Mastery

Mastery should communicate a player's current relationship with an exercise.

Canonical states:

```text
NOT_STARTED
LEARNING
PRACTICING
PROFICIENT
MASTERED
```

Mastery may eventually use:

* accuracy
* repetition
* rating
* consistency
* recent performance
* difficulty

Mastery is a product signal, not a replacement for raw training history.

---

# 22. Administration Product Scope

Administration is a first-class product area.

It should eventually support:

## Users

* search
* filtering
* permitted profile inspection
* role management
* account status management

## Exercises

* metadata
* availability
* ordering
* supported modes
* difficulty settings
* rating configuration
* scoring configuration
* XP configuration
* visibility

## Puzzles

* browse
* search
* filter
* inspect
* create
* edit
* validate
* review
* approve
* publish
* retire
* inspect performance

## Generators

* generator management
* configuration
* generation
* validation
* review
* approval
* publication

## Platform

* analytics
* audit review
* support
* operational indicators

Administration must not bypass the product's domain rules.

---

# 23. Content Lifecycle

Content should follow an explicit lifecycle:

```text
Draft
  ↓
Created / Generated
  ↓
Validated
  ↓
Reviewed
  ↓
Approved
  ↓
Published
  ↓
Active
  ↓
Retired
```

Saving a puzzle must not automatically publish it.

Generating a puzzle must not automatically make it active.

Content lifecycle is part of the product's quality model.

---

# 24. Manual Puzzle Creation

Administrators should be able to create supported puzzle types manually.

Manual content creation must respect:

* exercise-specific validation
* answer validation
* difficulty metadata
* rating metadata
* lifecycle status
* preview/review requirements

Detailed behavior belongs in:

```text
admin/PUZZLE_MANAGEMENT.md
```

---

# 25. Puzzle Generators

Puzzle generation is a major content capability.

Expected workflow:

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

Generation may specify:

* exercise
* generator
* constraints
* target difficulty
* target rating/range
* quantity

Generated content must pass the same quality boundaries as manually created content.

A trusted generator does not bypass review or approval.

Detailed behavior belongs in:

```text
admin/GENERATORS.md
```

---

# 26. Difficulty Calibration

The long-term product should compare declared difficulty with observed player performance.

Example:

```text
Declared Rating: 1400
Observed Performance: 1285
Attempts: 4210
Accuracy: 79%
```

Eventually the platform may recommend:

* adjusted difficulty
* adjusted target rating
* content retirement
* content review

This is a future capability.

The current platform only needs to preserve sufficient historical data to make it possible later.

---

# 27. Support

The current product direction includes a basic in-platform support mechanism.

The initial support experience should remain simple:

```text
Player
  ↓
Support Request
  ↓
Administrator Review
  ↓
Response
  ↓
Resolution
```

Support may include:

* ticket creation
* ticket status
* administrator response
* ticket history

External communication channels are not required for the core support product.

Future channels may include:

* email
* push notifications
* Telegram
* other delivery mechanisms

---

# 28. Coach Product Direction

The long-term coach product may support:

* coach accounts
* student relationships
* invitations
* groups
* classes
* assignments
* training plans
* progress monitoring
* performance review
* notes
* reports

The platform should establish clean relationship boundaries before implementing advanced coach functionality.

Coach access must always be explicitly authorized.

Detailed behavior belongs in:

```text
relationships/COACH_STUDENT.md
```

---

# 29. Parent Product Direction

The long-term parent product may support:

* multiple children
* child progress
* training activity
* reports
* notifications
* explicit child-related permissions

Parent access must always be controlled by explicit authorization and privacy rules.

Detailed behavior belongs in:

```text
relationships/PARENT_STUDENT.md
```

---

# 30. Adaptive Training

Adaptive training is a future product capability.

Potential features include:

* recommended exercises
* recommended difficulty
* weak-skill detection
* adaptive puzzle selection
* personalized training plans
* difficulty adjustment
* skill progression models
* coach-assisted recommendations

The initial adaptive system should not require machine learning.

The first implementation may use deterministic and explainable rules based on existing training data.

Adaptive training should build on existing authoritative history rather than creating a separate competing data model.

---

# 31. Notifications

Notifications are future product functionality.

Potential notifications include:

* training reminders
* streak reminders
* achievement notifications
* assignment notifications
* parent notifications
* system notifications

Notifications are not required for the core exercise experience.

Delivery channels are future implementation decisions.

---

# 32. Future Authentication

Possible future capabilities include:

* email verification
* password recovery
* MFA
* passkeys
* social login
* additional identity providers

These capabilities must not unnecessarily increase initial registration friction.

They are future direction unless promoted into active scope.

---

# 33. Privacy and Data Minimization

MicroChess should collect only information that provides meaningful product value.

Initial registration intentionally avoids requiring:

* email
* phone
* real name
* external identities

Public-facing features should expose only information appropriate to their purpose.

Examples:

* leaderboards should normally use usernames/display names
* external identities are optional
* related-user access must be permission-controlled
* sensitive personal information must not be exposed merely because a relationship exists

Detailed privacy and security requirements belong in:

```text
SECURITY.md
```

---

# 34. Accessibility

The product should support:

* keyboard navigation
* touch interaction
* sufficient contrast
* clear feedback
* appropriately sized controls
* readable typography
* screen-reader compatibility where practical
* reduced-motion preferences where appropriate

Accessibility must coexist with the child-friendly experience.

Detailed requirements belong in:

```text
UX_AND_DESIGN.md
```

---

# 35. Internationalization

MicroChess must be i18n-ready from the beginning.

Primary language:

```text
Persian
```

The product should support future additional languages without fundamental redesign.

The UI must correctly support:

* RTL languages
* LTR languages
* mixed-direction content

Chessboard coordinates and chess notation must preserve appropriate chess-specific directionality inside RTL interfaces.

---

# 36. Responsive Product Requirements

MicroChess must support:

* desktop
* tablet
* mobile portrait
* mobile landscape

The exercise experience has a strict requirement:

> Every exercise/play screen must fit completely within the visible viewport without normal vertical page scrolling.

This applies to supported viewport sizes and orientations.

Dashboards, analytics pages, and administration pages may use normal scrolling when content requires it.

---

# 37. Current Exercise Catalog

The official product exercise catalog is:

|  # | Exercise                | Slug                      |
| -: | ----------------------- | ------------------------- |
|  1 | Piece Recognition       | `piece-recognition`       |
|  2 | Legal Destinations      | `legal-destinations`      |
|  3 | Captures                | `captures`                |
|  4 | Undefended Pieces       | `undefended-pieces`       |
|  5 | Give Check              | `give-check`              |
|  6 | Get Out of Check        | `get-out-of-check`        |
|  7 | Pathfinding             | `pathfinding`             |
|  8 | Pathfinding Obstacles   | `pathfinding-obstacles`   |
|  9 | Balance Scale           | `balance-scale`           |
| 10 | Heavier Side            | `heavier-side`            |
| 11 | Pin                     | `pin`                     |
| 12 | Chinese Board           | `chinese-board`           |
| 13 | Is Checkmate?           | `is-checkmate`            |
| 14 | Blindfold Square Vision | `blindfold-square-vision` |
| 15 | Blindfold Calculation   | `blindfold-calculation`   |
| 16 | Opening Traps           | `opening-traps`           |
| 17 | Reverse Opening         | `reverse-opening`         |
| 18 | Trapped Pieces          | `trapped-pieces`          |

The catalog may expand later.

The catalog number is a product identifier.

It must not be confused with:

* database ordering
* exercise ID
* implementation status

Current implementation status belongs in:

```text
IMPLEMENTATION_STATE.md
```

---

# 38. Exercise Expansion

Adding a new exercise should:

* define one clear skill
* fit the existing exercise architecture
* preserve server-authoritative correctness
* support meaningful training data
* follow the shared product experience
* avoid unnecessary platform-specific infrastructure

A new exercise should not require rewriting unrelated exercises.

---

# 39. Explicitly Out of Scope

The following are outside the current core MicroChess product unless explicitly promoted into an accepted specification:

* full online chess gameplay
* real-time multiplayer chess
* arbitrary user-game engine analysis
* tournament management
* chess federation management
* payments
* subscription billing
* marketplace
* video courses
* live video classes
* social feed
* public messaging platform
* full social network
* advertising platform

These may be considered independently in the future.

---

# 40. What MicroChess Is Not

MicroChess is not:

* a full chess client
* a chess engine
* a tournament manager
* a chess federation system
* a generic LMS
* a video course platform
* a social network
* an advertising platform
* a replacement for FIDE
* a replacement for Lichess
* a replacement for Chess.com

External chess services are optional integrations, not dependencies for the core training experience.

---

# 41. Product Outcome Questions

The product should eventually provide meaningful answers to major user questions.

## Player

* What am I good at?
* What do I need to improve?
* Am I improving?
* Which exercises should I practice?
* How has my rating changed?
* How consistent am I?
* How does my recent performance compare with earlier periods?

## Coach

* Which skills does this student need to work on?
* Is the student improving?
* Which exercises are causing difficulty?
* Is the student practicing consistently?

## Parent

* Is the child practicing?
* Is the child progressing?
* Which skills are improving?
* Where might additional support be useful?

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

# 42. Product Evolution Principle

MicroChess should evolve from a simple training experience into a sophisticated training platform without requiring a fundamental product redesign.

The product should therefore preserve reliable foundations for:

* identity
* guest identity
* profiles
* training history
* exercise-specific ratings
* rating history
* gamification history
* exercise metadata
* puzzle metadata
* content lifecycle
* analytics source data
* administrative permissions
* relationships
* privacy boundaries

Preserving these foundations does not mean implementing every future capability immediately.

Future features should build on them rather than bypass them.

---

# 43. Scope Change Rule

A major new capability must be explicitly evaluated before becoming implementation work.

The proposal should answer:

1. What user problem does it solve?
2. Which user benefits?
3. Does it support the MicroChess mission?
4. Is it current scope or future direction?
5. What product capabilities does it depend on?
6. What data does it require?
7. Does it affect existing product boundaries?
8. Does it introduce unnecessary complexity?
9. Does it weaken any existing product principle?
10. Does it require an ADR?

A feature mentioned as future direction is not automatically implementation scope.

---

# 44. Product Completeness

The long-term target platform should provide:

```text
Core Exercises
+
Guest Training
+
Accounts
+
Player Profiles
+
External Chess Identities
+
Training History
+
Exercise Ratings
+
Progress
+
Gamification
+
Administration
+
Content Management
+
Puzzle Generation
+
Analytics
+
Coach/Student Relationships
+
Parent/Student Relationships
+
Adaptive Training Foundation
```

The implementation roadmap determines when each capability is built.

Product scope determines that these capabilities belong to the product.

---

# 45. Final Product Direction

The long-term MicroChess vision is:

> **A child-friendly, data-driven chess skill training platform that measures individual chess abilities, makes improvement visible and motivating, and eventually adapts training to each player's needs.**

The product should feel:

```text
Simple to a child
     +
Useful to a parent
     +
Powerful to a coach
     +
Meaningful to a serious player
     +
Operationally manageable for administrators
```

The complexity belongs inside the platform.

The experience should remain focused on one core promise:

> **Practice a chess skill, understand the result, see the improvement, and know what to practice next.**
