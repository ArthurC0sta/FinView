# FinView Sites Migration Specification

## Problem Statement

O FinView atual depende de Django, WSGI, PostgreSQL e armazenamento local, componentes que não são executados diretamente no runtime do Sites. A aplicação precisa de uma implementação TypeScript isolada, com D1, R2 e integrações HTTP, sem remover o sistema Django durante a homologação.

## Goals

- [ ] Disponibilizar todas as jornadas atuais em uma aplicação compatível com Sites.
- [ ] Isolar dados financeiros por usuário e empresa em um banco D1 novo.
- [ ] Autenticar usuários com código de uso único enviado pela Resend.
- [ ] Processar importações e análises de IA sem expor segredos no cliente.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Migração do banco Django atual | O produto começará com um D1 vazio por decisão do responsável. |
| Remoção ou alteração do Django | O sistema atual será preservado como contingência. |
| Domínio próprio | A primeira publicação usará o domínio fornecido pelo Sites. |
| Cobrança e transações financeiras | Não fazem parte do piloto e não são permitidas neste corte. |
| OCR de PDF | Apenas PDFs com camada textual serão aceitos. |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Acesso | Cadastro público por e-mail e código | Escolha explícita do responsável | y |
| Provedor de e-mail | Resend por API HTTPS | Escolha explícita e compatível com Worker | y |
| Persistência | D1 novo, sem importação do legado | Escolha explícita do responsável | y |
| Arquivos | R2 temporário; remoção após extração | Minimiza retenção de conteúdo financeiro | y |
| Sessão | Cookie seguro por oito horas | Mantém o contrato atual sem armazenar token no navegador | y |
| Valores monetários | Centavos inteiros | Evita erro de ponto flutuante no SQLite/D1 | y |
| Publicação | Primeiro deploy privado; acesso público somente após gates | Todo URL implantado é produção | y |

**Open questions:** none - all resolved or logged above.

## User Stories

### P1: Autenticação e empresa

**User Story**: As a visitante, I want entrar por código enviado ao meu e-mail so that eu possa usar o FinView sem senha.

**Acceptance Criteria**:

1. WHEN um e-mail válido solicitar acesso THEN the system SHALL responder com estado aceito sem revelar a existência da conta.
2. WHEN um código válido for confirmado dentro de 10 minutos THEN the system SHALL criar ou localizar o usuário, garantir uma empresa principal e emitir sessão segura por oito horas.
3. IF um código ultrapassar cinco tentativas, for reutilizado ou estiver expirado THEN the system SHALL rejeitar a autenticação com resposta 401.
4. WHILE uma rota financeira estiver autenticada, the system SHALL limitar toda leitura e mutação à empresa pertencente ao usuário da sessão.
5. WHEN o usuário sair THEN the system SHALL revogar a sessão e expirar o cookie.

**Independent Test**: solicitar e confirmar um código sintético, consultar `/api/me` e provar que um segundo usuário não acessa a empresa criada.

### P1: Gestão financeira

**User Story**: As a proprietário, I want manter movimentações, metas e perfil empresarial so that eu possa acompanhar meu caixa.

**Acceptance Criteria**:

1. WHEN uma movimentação válida for criada THEN the system SHALL persistir valor positivo em centavos, natureza, estado, categoria e data na empresa autenticada.
2. WHEN o dashboard for consultado com um mês THEN the system SHALL retornar entradas realizadas, saídas realizadas e saldo do período calculados deterministicamente.
3. WHEN uma meta válida for criada ou atualizada THEN the system SHALL impedir valor guardado negativo ou superior ao alvo.
4. WHEN a avaliação de perfil for concluída THEN the system SHALL calcular o nível por regras determinísticas e manter preferências fora da pontuação.

**Independent Test**: cadastrar entradas, saídas e meta e comparar os totais retornados pelo dashboard.

### P1: Importações assistidas

**User Story**: As a proprietário, I want revisar dados extraídos de arquivos so that eu possa confirmar movimentações sem digitação repetitiva.

**Acceptance Criteria**:

1. WHEN um CSV, XLS, OFX/OFC, PDF textual ou CNAB 240/400 válido de até 10 MiB e 1.000 linhas for enviado THEN the system SHALL criar lote e linhas temporárias no D1.
2. IF o arquivo estiver vazio, malformado, criptografado, digitalizado, com assinatura incompatível ou exceder os limites THEN the system SHALL rejeitá-lo com motivo e remover o objeto bruto.
3. WHEN a extração terminar THEN the system SHALL remover o arquivo bruto do R2 e manter somente metadados e linhas estruturadas.
4. WHEN linhas não classificadas forem encontradas THEN the system SHALL limitar sugestões da IA às categorias ativas da empresa.
5. WHEN o usuário confirmar as linhas selecionadas THEN the system SHALL criar movimentações de forma atômica e idempotente.

**Independent Test**: importar fixture, revisar linhas, confirmar duas vezes e observar uma única movimentação por linha.

### P1: Análise consultiva

**User Story**: As a proprietário, I want receber uma explicação objetiva dos meus dados so that eu possa decidir a próxima ação.

**Acceptance Criteria**:

1. WHEN uma análise for solicitada THEN the system SHALL enviar à Groq somente resumo agregado, contexto empresarial necessário e metas ativas.
2. IF a Groq estiver indisponível ou exceder 20 segundos THEN the system SHALL retornar mensagem segura sem bloquear as demais funcionalidades.
3. WHEN descrições forem classificadas THEN the system SHALL usar saída JSON estruturada e descartar categorias inexistentes.

**Independent Test**: simular sucesso, timeout e categoria inválida sem realizar chamadas externas.

### P1: Interface e publicação

**User Story**: As a visitante, I want usar o FinView em desktop e celular so that eu possa operar o negócio com clareza.

**Acceptance Criteria**:

1. WHEN a aplicação abrir THEN the system SHALL oferecer landing pública e redirecionar rotas privadas sem sessão para o login.
2. WHILE a viewport tiver 390 por 844 pixels, the system SHALL organizar contexto, caixa, alertas e ações em coluna sem rolagem horizontal.
3. WHEN o build de produção for gerado THEN the system SHALL conter Worker, assets e configuração de bindings sem valores secretos.
4. IF os gates locais não passarem THEN the system SHALL impedir a criação de versão candidata para deploy.

**Independent Test**: executar build, testes e auditoria visual local antes de qualquer operação remota.

## Edge Cases

- IF duas solicitações concorrentes criarem o mesmo e-mail THEN the system SHALL manter um único usuário normalizado.
- IF uma mutação vier de origem diferente do Site THEN the system SHALL responder 403.
- IF uma linha importada já tiver sido confirmada THEN the system SHALL ignorar nova confirmação dessa linha.
- IF a IA devolver JSON inválido THEN the system SHALL manter a classificação manual disponível.
- IF um lote pertencer a outra empresa THEN the system SHALL responder 404.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| SITE-01 | Autenticação e empresa | Tasks | Implementing |
| SITE-02 | Gestão financeira | Tasks | Implementing |
| SITE-03 | Importações assistidas | Tasks | Implementing |
| SITE-04 | Análise consultiva | Tasks | Implementing |
| SITE-05 | Interface e publicação | Tasks | Implementing |

**Coverage:** 5 total, 5 mapped to tasks, 0 unmapped.

## Success Criteria

- [ ] Usuário cria sessão, empresa, movimentação e meta em um D1 vazio.
- [ ] Usuários diferentes não acessam dados entre si.
- [ ] Importações confirmadas são atômicas e idempotentes.
- [ ] Build e testes locais passam sem segredos no bundle.
- [ ] Versão candidata pode ser empacotada para Sites sem alterar o Django.
