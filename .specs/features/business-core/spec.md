# Business Core Specification

## Problem Statement

O FinView armazena receitas, despesas e metas diretamente por usuário. O produto precisa de uma base empresarial sem perder os dados existentes nem quebrar os fluxos atuais.

## Goals

- [x] Criar empresa, categorias gerenciais e movimentações unificadas.
- [x] Migrar os dados existentes de forma reversível e idempotente.
- [x] Operar dashboard, mensal, despesas, metas e IA pela empresa do usuário.

## Out of Scope

| Feature | Reason |
|---|---|
| Papéis e múltiplas empresas | Incremento posterior |
| Importação de arquivos | Fora do corte de segunda-feira |
| Remoção das tabelas legadas | Necessárias para compatibilidade e rollback |
| Deploy | Aceite local |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| Empresa atual | Uma empresa padrão por usuário | Corte aprovado | y |
| Autorização | Proprietário da empresa | Papéis foram adiados | y |
| Categoria legada | Nome preservado e grupo não classificado | Evita inferência contábil indevida | y |
| Escrita legada | Sem dual-write | Evita duas fontes ativas | y |

**Open questions:** none.

## User Stories

### P1: Base empresarial

**User Story**: Como usuário autenticado, quero operar os dados da minha empresa para manter isolamento e contexto empresarial.

**Acceptance Criteria**:

1. WHEN um usuário existente receber a migration THEN o sistema SHALL criar exatamente uma empresa padrão para ele.
2. WHEN receitas e despesas legadas forem migradas THEN o sistema SHALL criar movimentações equivalentes sem alterar os registros legados.
3. WHEN a migration reversa for executada THEN o sistema SHALL remover apenas os dados empresariais gerados e preservar os registros legados.
4. IF a transformação for executada novamente THEN o sistema SHALL impedir duplicação por referência legada.

### P1: Operação financeira

**User Story**: Como proprietário, quero registrar e consultar entradas e saídas pela empresa para manter o dashboard coerente.

**Acceptance Criteria**:

1. WHEN uma entrada for cadastrada THEN o sistema SHALL persistir uma movimentação positiva, realizada e vinculada à empresa atual.
2. WHEN uma despesa for criada, editada ou excluída THEN o sistema SHALL alterar apenas uma saída pertencente à empresa atual.
3. WHEN o dashboard for consultado THEN o sistema SHALL calcular os totais com movimentações da empresa e do período selecionado.
4. IF um usuário tentar acessar uma movimentação de outra empresa THEN o sistema SHALL responder 404 e preservar o registro.
5. WHEN uma despesa fixa for materializada em outro mês THEN o sistema SHALL criar no máximo uma ocorrência equivalente.

### P1: Metas e IA

**User Story**: Como proprietário, quero manter metas e análises ligadas à empresa sem regressão dos recursos atuais.

**Acceptance Criteria**:

1. WHEN uma meta for criada THEN o sistema SHALL vinculá-la ao usuário e à empresa atual.
2. WHEN o contexto da IA for produzido THEN o sistema SHALL usar as movimentações e metas da empresa atual.
3. IF não houver movimentações ou metas THEN o sistema SHALL retornar os estados vazios já suportados.

## Edge Cases

- IF o usuário ainda não possuir empresa THEN o sistema SHALL criá-la de forma determinística ao resolver o contexto atual.
- IF uma categoria informada não existir THEN o sistema SHALL criar uma categoria personalizada no grupo não classificado.
- IF o valor de uma movimentação for zero ou negativo THEN o sistema SHALL rejeitar a persistência.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| BCORE-01 | Base empresarial | Implementation | Verified |
| BCORE-02 | Migração reversível | Implementation | Verified |
| BCORE-03 | Operação financeira | Implementation | Verified |
| BCORE-04 | Isolamento | Implementation | Verified |
| BCORE-05 | Metas e IA | Implementation | Verified |

**Coverage:** 5 total, 5 mapped, 0 unmapped.

## Success Criteria

- [x] Todos os registros atuais são representados no novo modelo sem perda.
- [x] Os fluxos atuais operam pelo modelo empresarial.
- [x] Check, migrations e suíte completa passam localmente.
