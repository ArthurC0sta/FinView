# Financial Goals Repair Specification

## Problem Statement

The current application cannot start because the views import and use `FinancialGoal`, while the model, migration, routes, and template are absent. The repair must deliver the financial-goals flow already described by the project documentation without changing unrelated expense and income behavior.

## Goals

- [x] Start the Django application without import or URL configuration errors.
- [x] Let an authenticated user create, view, and delete only their own financial goals.
- [x] Expose calculated goal progress to the goals page, dashboard, and AI context.
- [x] Keep invalid goal data out of the database and show actionable validation errors.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Editing an existing goal | The documented flow only requires creation, listing, and deletion. |
| Automatic deposits or bank integrations | No transaction ledger or external integration exists in this project. |
| Production deployment or migration | This repair is limited to local code and isolated validation. |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Goal visibility | Show active goals on dashboard and AI context; show all goals on the goals page | Matches the existing helper names and keeps paused or completed goals manageable | y |
| Monetary bounds | Target must be greater than zero; saved amount must be between zero and target | Prevents undefined percentages and impossible progress | y |
| Deadline | Optional; when present, it may be today or later | Supports goals without a deadline and avoids already-expired new goals | y |
| Goal lifecycle | New goals start active; status changes are not part of this repair | The existing create view does not expose status controls | y |
| Authorization | All goal endpoints require login and object operations are scoped to the authenticated user | Matches the project's existing session boundary | y |
| Concurrent duplicate submissions | Separate goals are allowed | The domain has no stable deduplication key and repeated goals can be legitimate | y |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Manage measurable financial goals

**User Story**: As an authenticated user, I want to create and review measurable financial goals so that I can compare my monthly balance with the amount I need to save.

**Why P1**: The current incomplete implementation prevents the entire Django application from starting.

**Acceptance Criteria**:

1. WHEN an authenticated user submits valid goal data THEN the system SHALL persist the goal for that user and redirect to the goals page.
2. IF a goal name is blank, its target is not greater than zero, its saved amount is negative or greater than the target, or its deadline is in the past THEN the system SHALL reject the submission, keep the submitted values visible, and display field errors.
3. WHEN a goal is displayed THEN the system SHALL calculate remaining amount, progress percentage capped from 0 through 100, months remaining, and required monthly amount from its persisted values.
4. WHILE a user is authenticated, the system SHALL list that user's goals without exposing goals owned by another user.
5. IF an unauthenticated user requests the goals page THEN the system SHALL redirect to the login page without persisting data.

**Independent Test**: Create a goal through the HTTP endpoint, load the goals page, and assert the owner, values, calculations, and validation behavior.

### P1: Delete an owned financial goal

**User Story**: As an authenticated user, I want to remove one of my goals so that obsolete goals no longer affect my financial analysis.

**Why P1**: Deletion is part of the documented route contract and must enforce object ownership.

**Acceptance Criteria**:

1. WHEN an authenticated user sends POST for a goal they own THEN the system SHALL delete that goal and redirect to the goals page.
2. IF a user sends POST for a goal owned by another user THEN the system SHALL return HTTP 404 and preserve the goal.
3. IF a user requests deletion with a method other than POST THEN the system SHALL return HTTP 405 and preserve the goal.

**Independent Test**: Exercise the deletion route as owner and non-owner and assert the status code and database state.

### P1: Surface active goals in financial analysis

**User Story**: As an authenticated user, I want my active goals reflected in the dashboard and AI context so that financial guidance considers my priorities.

**Why P1**: The existing dashboard and AI helpers already depend on this information.

**Acceptance Criteria**:

1. WHILE a goal has active status, the system SHALL include it in the dashboard goals context and the AI financial context.
2. WHILE a goal has paused or completed status, the system SHALL exclude it from the dashboard goals context and the AI financial context.
3. WHEN no active goal exists THEN the system SHALL render the dashboard and AI context without an exception and state that no financial goals are registered.

**Independent Test**: Create active and inactive goals, build both contexts, and assert inclusion and exclusion by name.

---

## Edge Cases

- IF a goal has no deadline THEN the system SHALL report no monthly requirement instead of dividing by an undefined period.
- WHEN a goal deadline is in the current month THEN the system SHALL use one month for the required monthly amount calculation.
- WHEN the saved amount equals the target THEN the system SHALL report zero remaining and 100 percent progress.
- IF an invalid goal choice is submitted THEN the system SHALL reject the submission with a field error.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| GOAL-01 | P1: Manage measurable financial goals | Execute | Verified |
| GOAL-02 | P1: Delete an owned financial goal | Execute | Verified |
| GOAL-03 | P1: Surface active goals in financial analysis | Execute | Verified |
| GOAL-04 | Edge cases and validation | Execute | Verified |

**Coverage:** 4 total, 4 mapped to implementation and tests, 0 unmapped.

---

## Success Criteria

- [x] `python manage.py check` exits with status 0.
- [x] `python manage.py makemigrations --check --dry-run` reports no pending model changes.
- [x] All Django tests pass against an isolated test database.
- [x] The goals page renders with working create and delete flows for the authenticated owner.
