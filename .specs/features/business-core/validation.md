# Business Core Validation

## Validation: PASS

Validação independente executada pelo fallback standalone previsto no TLC, pois a política desta sessão não permitiu delegar a um subagente. A autoria foi confrontada com requisitos, testes positivos, migração real controlada e mutações negativas em cópias temporárias.

## Evidências por requisito

| Requisito | Evidência de implementação | Evidência de teste | Resultado |
|---|---|---|---|
| BCORE-01 | `gastos/models.py:20`, `gastos/models.py:41`, `gastos/models.py:76` | `gastos/tests.py:34` | PASS |
| BCORE-02 | `gastos/migrations/0006_business_core_schema.py:10`, `gastos/migrations/0006_business_core_schema.py:88` | `gastos/test_migrations.py:10` | PASS |
| BCORE-03 | `gastos/views.py:145`, `gastos/views.py:489`, `gastos/views.py:588` | `gastos/tests.py:105`, `gastos/tests.py:182` | PASS |
| BCORE-04 | `gastos/views.py:145`, `gastos/views.py:820`, `gastos/views.py:865` | `gastos/tests.py:148` | PASS |
| BCORE-05 | `gastos/views.py:324`, `gastos/views.py:346`, `gastos/views.py:651` | `gastos/tests.py:222` | PASS |

## Gates executados

- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma alteração detectada.
- Suíte Django completa: 35 testes aprovados em 45,548 s.
- `git diff --check`: aprovado.
- Banco limpo: coberto pela suíte de migrations e pela criação do banco de testes.
- Cópia do banco atual: 3 usuários, 3 empresas, 6 categorias, 7 movimentações, 2 receitas legadas e 5 despesas legadas.
- Rollback controlado: preservou 3 usuários, 2 receitas, 5 despesas e 0 metas; reaplicação voltou a produzir exatamente 3 empresas e 7 movimentações.

## Sensor de discriminação

Três mutações foram aplicadas somente em cópias temporárias e todas foram detectadas:

1. remoção do filtro de proprietário: teste de isolamento falhou porque o registro de outra empresa foi excluído;
2. troca de entrada por saída no cálculo do dashboard: teste falhou com total incorreto;
3. desativação da verificação de recorrência: teste falhou ao encontrar duas ocorrências.

## Limites confirmados

Esta validação comprova o aceite local do corte. Não comprova deploy, operação em produção, papéis, múltiplas empresas, importações ou as demais features adiadas.
