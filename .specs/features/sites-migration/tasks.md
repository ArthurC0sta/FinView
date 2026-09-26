# FinView Sites Migration Tasks

## Execution Protocol

Implementar com `tlc-spec-driven`, sem push ou deploy até autorização específica.

**Design**: `.specs/features/sites-migration/design.md`
**Status**: In Progress

## Test Coverage Matrix

> Generated from the approved plan and strong defaults. Guidelines: `AGENTS.md`, TLC execution contract.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Domain services | unit | All specified branches and boundaries | `sites-app/test/*.test.ts` | `npm test` |
| Worker routes | integration | Happy, auth, ownership and failure paths | `sites-app/test/worker.test.ts` | `npm test` |
| D1 schema | integration | Clean migration and constraints | `sites-app/test/schema.test.ts` | `npm test` |
| Client | build | Typecheck, build and accessibility smoke | `sites-app/src/client/` | `npm run check` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Unit changes | `cd sites-app && npm test` |
| Full | Worker and storage changes | `cd sites-app && npm run check` |
| Build | Phase completion | `cd sites-app && npm run validate` |

## Execution Plan

```text
T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7 -> T8
```

## Task Breakdown

### T1: Scaffold the Sites application

**What**: Criar toolchain, bindings e build reproduzível.
**Where**: `sites-app/package.json`
**Depends on**: None
**Requirement**: SITE-05
**Done when**: instalação, typecheck e build terminam com código zero.
**Tests**: build
**Gate**: build

### T2: Create the D1 schema

**What**: Criar migration idempotente com todas as tabelas e constraints.
**Where**: `sites-app/migrations/0001_initial.sql`
**Depends on**: T1
**Requirement**: SITE-01, SITE-02, SITE-03
**Done when**: banco local limpo recebe a migration e constraints críticas são verificadas.
**Tests**: integration
**Gate**: full

### T3: Implement email-code authentication

**What**: Implementar OTP, Resend, sessões e autorização por empresa.
**Where**: `sites-app/src/services/auth.ts`
**Depends on**: T2
**Requirement**: SITE-01
**Done when**: expiração, limite de tentativas, reuso, logout e isolamento passam.
**Tests**: unit
**Gate**: quick

### T4: Implement financial operations

**What**: Implementar empresa, perfil, movimentações, metas e resumo do dashboard.
**Where**: `sites-app/src/services/finance.ts`
**Depends on**: T3
**Requirement**: SITE-02
**Done when**: CRUD escopado e totais em centavos passam nos testes.
**Tests**: unit
**Gate**: quick

### T5: Implement Groq provider

**What**: Implementar análise e classificação estruturada via fetch.
**Where**: `sites-app/src/services/groq.ts`
**Depends on**: T4
**Requirement**: SITE-04
**Done when**: roteamento, sanitização, timeout e JSON inválido passam com mocks.
**Tests**: unit
**Gate**: quick

### T6: Implement the import pipeline

**What**: Implementar parsers, lote, revisão e confirmação idempotente.
**Where**: `sites-app/src/services/imports.ts`
**Depends on**: T5
**Requirement**: SITE-03
**Done when**: fixtures aceitas/rejeitadas, R2 removido e confirmação atômica passam.
**Tests**: integration
**Gate**: full

### T7: Expose the Worker API

**What**: Criar rotas, validação de origem, headers e entrega de assets.
**Where**: `sites-app/src/worker.ts`
**Depends on**: T6
**Requirement**: SITE-01, SITE-02, SITE-03, SITE-04
**Done when**: rotas públicas e privadas passam nos testes de contrato.
**Tests**: integration
**Gate**: full

### T8: Port the Command Center client and package candidate

**What**: Implementar landing, login, onboarding, dashboard, despesas, metas, importações e perfil responsivos.
**Where**: `sites-app/src/client/`
**Depends on**: T7
**Requirement**: SITE-05
**Done when**: build, suíte completa, auditoria de segredos e empacotamento passam.
**Tests**: build
**Gate**: build

## Phase Execution Map

| Task | Depends On | Diagram Shows | Status |
| --- | --- | --- | --- |
| T1 | None | start | Match |
| T2 | T1 | T1 -> T2 | Match |
| T3 | T2 | T2 -> T3 | Match |
| T4 | T3 | T3 -> T4 | Match |
| T5 | T4 | T4 -> T5 | Match |
| T6 | T5 | T5 -> T6 | Match |
| T7 | T6 | T6 -> T7 | Match |
| T8 | T7 | T7 -> T8 | Match |

## Test Co-location Validation

| Task | Layer | Matrix Requires | Task Says | Status |
| --- | --- | --- | --- | --- |
| T1 | Config | build | build | OK |
| T2 | Schema | integration | integration | OK |
| T3-T5 | Services | unit | unit | OK |
| T6-T7 | Storage/routes | integration | integration | OK |
| T8 | Client | build | build | OK |
