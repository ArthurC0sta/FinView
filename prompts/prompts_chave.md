# FinView AI - Prompts Utilizados

Este documento consolida os principais prompts utilizados durante a construção do FinView AI, com destaque para a construção do prompt destinado à análise dos gastos pela IA.

## 1. Front-end do Projeto

Prompt principal:

```text
Crie o front-end completo de uma aplicação web chamada FinView AI, uma plataforma inteligente de organização financeira pessoal com IA.
```

Resumo:

- Criar uma experiência visual de fintech moderna.
- Usar layout escuro, glassmorphism, cards translúcidos, dashboard financeiro e painel lateral de IA.
- Prever páginas de landing, login, cadastro, entrada mensal, cadastro de gastos, dashboard e perfil.
- Simular gráficos, indicadores financeiros e recomendações inteligentes.

## 2. Deploy no Render

Prompts principais:

```text
deixa o código pronto pra deploy no render pf
```

```text
já deixa tudo configurado
```

Objetivo:

- Preparar o Django para produção.
- Configurar `build.sh`, `render.yaml`, Gunicorn, WhiteNoise, PostgreSQL e variáveis de ambiente.
- Garantir que o Render execute `collectstatic` e `migrate`.

## 3. Integração com Groq AI

Prompt principal:

```text
me ajuda a configura a integração com a groq AI, API_KEY tá salvo no arquivo .env
```

Objetivo:

- Ler `GROQ_API_KEY` ou `API_KEY` a partir do ambiente.
- Instanciar cliente Groq.
- Criar função de geração de resposta financeira.
- Integrar a resposta ao painel lateral da aplicação.

## 4. Identificação da Análise Gerada por IA

Prompt principal:

```text
o resultado da analise da IA, está no painel dica? Se sim, informa que analise foi gerada por IA
```

Objetivo:

- Deixar transparente para o usuário que o conteúdo do painel foi gerado por IA.
- Alterar o texto visual para `Análise gerada por IA`.

## 5. Amarração da IA ao Objetivo Financeiro

Prompt principal:

```text
a analise do gasto está alinhado com o objetivo? se não, vamos fazer essa amarração
```

Objetivo:

- Usar o objetivo financeiro escolhido no cadastro como parte do contexto da IA.
- Fazer a análise deixar de ser genérica e passar a responder ao objetivo do usuário.

## 6. Construção do Prompt de Análise dos Gastos

A análise da IA foi construída em três camadas.

### 6.1. Prompt de sistema

Local: `gastos/ia.py`

```text
Voce e o assistente financeiro do FinView AI.
Responda em portugues do Brasil, com tom direto e util.
Use somente os dados financeiros enviados pelo sistema.
Sempre relacione a analise ao objetivo financeiro do usuario quando ele for informado.
Responda em topicos curtos, sem texto corrido longo.
Se os dados forem insuficientes, diga o que falta cadastrar.
Evite prometer resultados e nao trate isso como consultoria financeira profissional.
```

Função:

- Define o papel da IA.
- Limita a resposta aos dados do sistema.
- Obriga uma resposta curta e em tópicos.
- Evita promessa de resultado financeiro.
- Orienta a IA a usar o objetivo financeiro quando disponível.

### 6.2. Contexto financeiro enviado pelo sistema

Local: `gastos/views.py`, função `ai_context_for_month`.

Campos enviados:

```text
Usuario
Objetivo financeiro
Mes de referencia
Renda cadastrada
Total de despesas
Saldo
Percentual comprometido
Categorias
Prioridades
Metas financeiras
```

No caso das metas financeiras, o contexto inclui:

```text
nome da meta
valor alvo
valor ja guardado
valor restante
progresso percentual
valor necessario por mes
```

Função:

- Entregar para a IA um resumo objetivo da situação financeira.
- Evitar que a IA invente dados.
- Permitir análise cruzada entre renda, gastos, objetivo e metas.

### 6.3. Prompt da interface

Locais:

- `static/assets/js/app.js`
- `gastos/views.py`

Prompt atual:

```text
Analise se os gastos e receitas do mes estao alinhados ao objetivo financeiro e as metas cadastradas do usuario. Responda em ate 5 topicos curtos, cada um iniciado por "-": situacao, meta, viabilidade, ponto de atencao e acao pratica.
```

Função:

- Solicitar uma análise prática do mês.
- Considerar receitas e despesas juntas.
- Relacionar a análise ao objetivo financeiro e às metas.
- Padronizar a resposta em tópicos curtos.

Estrutura esperada da resposta:

```text
- Situacao: resumo da renda, gastos e saldo.
- Meta: relação com a meta financeira cadastrada.
- Viabilidade: se o ritmo atual permite atingir a meta.
- Ponto de atencao: categoria, prioridade ou comportamento que exige revisão.
- Acao pratica: recomendação objetiva para o próximo passo.
```

## 7. Evolução do Prompt de Análise

Versão inicial:

```text
Analise se os gastos do mes estao alinhados ao objetivo financeiro do usuario.
```

Limitação:

- Olhava principalmente para gastos.
- Dependia do objetivo financeiro, mas ainda não avaliava metas concretas.

Versão atual:

```text
Analise se os gastos e receitas do mes estao alinhados ao objetivo financeiro e as metas cadastradas do usuario.
```

Melhoria:

- Considera receitas, despesas, saldo e metas.
- Permite uma resposta mais estratégica.
- Ajuda o usuário a entender como chegar em metas como guardar `R$ 6.000,00`.

## 8. Metas Financeiras

Prompt principal:

```text
no site, vamos implementar uma relação de metas do usuário
```

Exemplo discutido:

```text
Eu tenho uma meta de guarda 6.000 reais, a ia vai analisar os meus gastos, receitas e como eu posso chegar na minha meta.
```

Resultado:

- Criação do model `FinancialGoal`.
- Página de metas.
- Card de meta no dashboard.
- Inclusão das metas no contexto da IA.
- Prompt de análise atualizado para considerar metas cadastradas.

## 9. Visualização da Resposta da IA

Prompt principal:

```text
Na visualização da informação, o texto tá mal distribuído, a melhor coisa seria ordernar em tópicos
```

Objetivo:

- Transformar respostas longas em lista de tópicos.
- Melhorar a leitura dentro do painel lateral de IA.

## 10. Máscara Monetária

Prompt principal:

```text
quando digitamos valores, a separação de casas decimais não está acontecendo
```

Exemplo:

```text
se eu digitar 1500, ele não ajusta para 1.500,00
```

Objetivo:

- Padronizar entrada de valores monetários no formato brasileiro.
- Converter o valor para formato numérico antes de enviar ao backend.

## 11. Correção de Erro 500 em Produção

Prompt principal:

```text
Eu tenho um valor de mil reais cadastrados, se eu colocar mais 500 reais como renda variável, ele da erro 500
```

Objetivo:

- Corrigir erro ao cadastrar múltiplas rendas no mesmo mês.
- Criar migration para remover restrição única antiga.
- Criar fallback para somar renda caso o banco antigo ainda bloqueie múltiplos registros.

## 12. Documentação e Apresentação

Prompts principais:

```text
precisamos explicar toda a estrutura do projeto (gere um pdf para isso)
```

```text
faça um prompt para desenhar um fluxograma da aplicação (fluxo do sitema e fluxo do user)
```

```text
consegue gera uma apresentação tbm?
```

Objetivo:

- Criar documentação técnica.
- Gerar PDF com estrutura do projeto.
- Gerar fluxogramas.
- Gerar apresentação do projeto.

## 13. Uso do Codex

Prompt principal:

```text
foi citado a utilizado do codex como ferramenta principal? (informar o modelo de linguagem tbm)
```

Resultado:

- Registro do Codex como ferramenta principal de apoio ao desenvolvimento.
- Modelo informado: Codex, agente baseado em GPT-5.
