# Financial Goals Repair Context

**Gathered:** 2026-09-18
**Spec:** `.specs/features/financial-goals-repair/spec.md`
**Status:** Ready for implementation

---

## Feature Boundary

Complete the financial-goals vertical slice already documented in FinView: persistence, calculations, authenticated create/list/delete endpoints, goals page, dashboard summary, AI context, and regression tests.

---

## Implementation Decisions

### Data and lifecycle

- New goals start with active status.
- Target amount is positive; saved amount is non-negative and cannot exceed target.
- Deadline is optional and cannot be earlier than the current local date when a goal is created.
- Separate goals may share the same name and values.

### Authorization and failure behavior

- Login is required for every goals endpoint.
- Goal lookup for deletion is always scoped by `request.user`.
- Invalid forms render the goals page with submitted values and field-level errors.
- Deletion accepts POST only and preserves the object for all rejected requests.

### Presentation

- The goals page uses the current app shell and visual vocabulary.
- Active goals appear on the dashboard and in AI context.
- The goals page lists every status so inactive goals remain visible.

### Agent's Discretion

- Exact spacing and card composition within the existing design system.
- Choice labels, provided their stored values remain stable and readable in Portuguese.

### Declined / Undiscussed Gray Areas -> Assumptions

- Editing, status transitions, deposits, notifications, and bank integrations remain out of scope.

---

## Specific References

- `docs/ESTRUTURA_PROJETO_FINVIEW_AI.md`, sections for `FinancialGoal` and the documented goals flow.
- Existing `gastos/views.py` goal helper and endpoint skeletons.

---

## Deferred Ideas

- Goal editing and explicit pause/complete actions.
- Deposit history per goal.
