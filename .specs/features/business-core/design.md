# Business Core Design

**Spec**: `.specs/features/business-core/spec.md`
**Status**: Approved

## Architecture Overview

O modelo novo será a fonte dos fluxos ativos. `MonthlyIncome` e `Expense` permanecem intactos como legado. Uma data migration cria empresas, categorias e movimentações com referências únicas aos registros antigos.

## Components

### Domain models

- `Business`: proprietário e identidade mínima.
- `ManagerialCategory`: nome por empresa e grupo gerencial estável.
- `FinancialTransaction`: entrada ou saída positiva, com estado, origem e referência legada.
- `FinancialGoal`: recebe vínculo opcional com empresa durante a transição.

### Business context

- `current_business(user)`: resolve ou cria a empresa padrão.
- `category_for_name(business, name, group)`: resolve categoria sem inferir grupo de despesa.
- Queries de leitura e mutação sempre filtram `business__owner=user`.

### Migration

- Cria uma empresa por usuário.
- Converte renda em entrada e despesa em saída.
- Preserva tabelas antigas.
- Reverse remove dados gerados pela migration.

## Risks & Concerns

| Concern | Location | Impact | Mitigation |
|---|---|---|---|
| Views concentram regra e consulta | `gastos/views.py` | Regressão ampla | Helpers pequenos e testes de integração |
| Categorias pessoais não equivalem às empresariais | registros legados | Indicadores incorretos | Grupo não classificado por padrão |
| Banco já possui dados | `db.sqlite3` | Perda/duplicação | Referências legadas únicas e teste de migration |
| Árvore possui alterações do usuário | worktree | Sobrescrita acidental | Alterações cirúrgicas e diff por arquivo |

## Tech Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Compatibilidade | Manter tabelas legadas | Rollback seguro |
| Fonte ativa | `FinancialTransaction` | Evitar dual-write |
| Permissão | Proprietário | Escopo aprovado |
| Categoria antiga | Não classificada | Sem inferência contábil |
