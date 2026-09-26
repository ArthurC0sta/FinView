# Business Core Tasks

## Execution Protocol

Executar com `tlc-spec-driven` e `senior-fullstack-mentor`. O usuário proibiu commits neste corte; por isso os gates e estados serão registrados sem criar histórico Git.

**Design**: `.specs/features/business-core/design.md`
**Status**: Verified

## Test Coverage Matrix

> Guidelines found: mandatory global skill preflight and existing `django.test.TestCase` patterns in `gastos/tests.py`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
|---|---|---|---|---|
| Models/domain | unit | Constraints, properties and ownership | `gastos/tests.py` | `.venv/bin/python manage.py test gastos` |
| Migration/data | integration | Forward, idempotency intent and legacy preservation | `gastos/test_migrations.py` | `.venv/bin/python manage.py test gastos.test_migrations` |
| Views/queries | integration | Happy path, isolation and empty states | `gastos/tests.py` | `.venv/bin/python manage.py test gastos` |
| Schema/admin/docs | none | Build gate | n/a | build gate |

## Gate Check Commands

| Gate Level | When to Use | Command |
|---|---|---|
| Quick | Domain changes | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python manage.py test gastos` |
| Full | Migration and views | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python manage.py test` |
| Build | Phase completion | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python manage.py check && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python manage.py makemigrations --check --dry-run && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python manage.py test` |

## Execution Plan

### Phase 1: Domain and migration

`T1 → T2 → T3`

### Phase 2: Product integration

`T4 → T5 → T6`

## Task Breakdown

### T1: Define enterprise domain models
**Status**: Done
**What**: Add business, category, transaction and goal-business relationship.
**Where**: `gastos/models.py`
**Depends on**: None
**Requirement**: BCORE-01, BCORE-03
**Tests**: unit
**Gate**: quick

### T2: Create reversible data migration
**Status**: Done
**What**: Create schema and migrate every legacy record idempotently.
**Where**: `gastos/migrations/0006_business_core_schema.py`
**Depends on**: T1
**Requirement**: BCORE-01, BCORE-02
**Tests**: integration
**Gate**: full

### T3: Register enterprise models
**Status**: Done
**What**: Expose the new models in Django admin.
**Where**: `gastos/admin.py`
**Depends on**: T2
**Requirement**: BCORE-01
**Tests**: none
**Gate**: build

### T4: Adapt active product flows
**Status**: Done
**What**: Switch dashboard, monthly, expenses, recurrence, goals and AI context to business transactions.
**Where**: `gastos/views.py`
**Depends on**: T3
**Requirement**: BCORE-03, BCORE-04, BCORE-05
**Tests**: integration
**Gate**: full

### T5: Cover enterprise behavior
**Status**: Done
**What**: Add model, CRUD, dashboard, recurrence, goal and isolation assertions.
**Where**: `gastos/tests.py`
**Depends on**: T4
**Requirement**: BCORE-01, BCORE-03, BCORE-04, BCORE-05
**Tests**: integration
**Gate**: full

### T6: Record the approved delivery cut
**Status**: Done
**What**: Add estimates, delivered slice and deferred items to the consolidated scope.
**Where**: `output/escopo.txt`
**Depends on**: T5
**Requirement**: BCORE-01
**Tests**: none
**Gate**: build

## Phase Execution Map

`T1 → T2 → T3 → T4 → T5 → T6`

## Task Granularity Check

| Task | Scope | Status |
|---|---|---|
| T1 | One domain model module | OK |
| T2 | One migration | OK |
| T3 | One admin module | OK |
| T4 | One view module | OK |
| T5 | One test module | OK |
| T6 | One scope artifact | OK |

## Diagram-Definition Cross-Check

| Task | Depends On | Diagram Shows | Status |
|---|---|---|---|
| T1 | None | Start | Match |
| T2 | T1 | T1 → T2 | Match |
| T3 | T2 | T2 → T3 | Match |
| T4 | T3 | T3 → T4 | Match |
| T5 | T4 | T4 → T5 | Match |
| T6 | T5 | T5 → T6 | Match |

## Test Co-location Validation

| Task | Layer | Matrix Requires | Task Says | Status |
|---|---|---|---|---|
| T1 | Models | unit | unit | OK |
| T2 | Migration | integration | integration | OK |
| T3 | Admin | none | none | OK |
| T4 | Views | integration | integration | OK |
| T5 | Tests | integration | integration | OK |
| T6 | Docs | none | none | OK |
