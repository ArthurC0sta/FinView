# STATE

## Decisions

### AD-001
- **Decision**: O FinView atenderá empresas e priorizará a gestão financeira do negócio, sem misturar finanças pessoais no mesmo fluxo ou dashboard.
- **Reason**: O público definido é formado por profissionais autônomos formalizados ou em processo de formalização, MEIs e microempresas que precisam compreender faturamento, custos, despesas, margens, caixa e metas empresariais.
- **Evidence**: `docs/FUNDAMENTACAO_DECISOES.md#decisão-ad-001--foco-empresarial-e-separação-financeira`.
- **Trade-off**: O produto deixa de evoluir, neste ciclo, como aplicativo generalista de finanças pessoais e exigirá adaptação gradual dos conceitos atuais de renda, despesa e objetivo financeiro.
- **Scope**: Rebranding, modelos de dados, ferramentas financeiras, perfil de decisão, análises de IA, navegação, documentação e critérios de avaliação do futuro modelo próprio.
- **Date**: 2026-09-24
- **Status**: active

### AD-002
- **Decision**: O FinView oferecerá experiências Essencial, Gerencial e Completa conforme o perfil de gestão e a maturidade do negócio, mantendo um plano de ação em todos os níveis.
- **Reason**: Usuários em diferentes estágios precisam de profundidades distintas, mas todos devem receber orientação prática para transformar o diagnóstico financeiro em ações.
- **Evidence**: `docs/FUNDAMENTACAO_DECISOES.md#decisão-ad-002--três-níveis-com-plano-de-ação-universal`.
- **Definition**: `docs/NIVEIS_E_FERRAMENTAS.md`.
- **Trade-off**: A aplicação precisará manter critérios de perfil, apresentação progressiva e planos de ação adequados a três níveis, aumentando o esforço de produto, conteúdo e testes.
- **Scope**: Pesquisa de perfil, ferramentas disponíveis, dashboard, análises de IA, planos de ação, rebranding e futura definição de mensalidades.
- **Date**: 2026-09-24
- **Status**: active

### AD-003
- **Decision**: Toda decisão de produto ou regra de análise deverá registrar fonte, tipo de evidência, inferência realizada e necessidade de validação; decisões contábeis usarão prioritariamente fontes profissionais e oficiais.
- **Reason**: A rastreabilidade evita apresentar escolhas comerciais como normas contábeis e permite revisar decisões quando normas, mercado ou evidências mudarem.
- **Evidence**: `docs/FUNDAMENTACAO_DECISOES.md#política-de-evidências`.
- **Trade-off**: O planejamento e a manutenção documental exigirão revisão de fontes e registro explícito de limitações antes da aprovação das funcionalidades.
- **Scope**: Especificações, documentação executiva, skill contábil, regras de cálculo, recomendações de IA, rebranding, pesquisa de perfil, planos comerciais e arquitetura técnica.
- **Date**: 2026-09-24
- **Status**: active

### AD-004
- **Decision**: A pesquisa de perfil será dividida em dois blocos: maturidade do negócio e preferências de uso. Somente a maturidade do negócio poderá influenciar a recomendação entre Essencial, Gerencial e Completa; as preferências de uso apenas adaptarão a apresentação das análises.
- **Reason**: Dados objetivos sobre a gestão do negócio e preferências subjetivas de comunicação possuem finalidades diferentes. Separá-los reduz classificações indevidas e torna a recomendação do nível mais explicável.
- **Evidence**: `docs/FUNDAMENTACAO_DECISOES.md#decisão-ad-004--separação-do-perfil-de-negócio-e-das-preferências-de-uso`.
- **Definition**: `docs/PESQUISA_PERFIL_NEGOCIO.md`.
- **Trade-off**: O onboarding terá dois blocos e exigirá controles para informar finalidade, permitir revisão das respostas e explicar a recomendação produzida.
- **Scope**: Onboarding, perfil do usuário, recomendação de nível, personalização das respostas da IA, privacidade e testes de experiência.
- **Date**: 2026-09-24
- **Status**: active

### AD-005
- **Decision**: O FinView recomendará um nível com justificativa, mas permitirá que o usuário contrate outro nível após comparar recursos, limites e preço; a recomendação não será uma contratação automática.
- **Reason**: A maturidade do negócio deve orientar a escolha sem retirar a autonomia do usuário nem transformar uma classificação estimada em barreira comercial.
- **Evidence**: `docs/FUNDAMENTACAO_DECISOES.md#decisão-ad-005--recomendação-explicada-com-escolha-do-usuário`.
- **Definition**: `docs/PESQUISA_PERFIL_NEGOCIO.md#recomendação-e-escolha-do-plano`.
- **Trade-off**: O produto deverá explicar diferenças, alertar sobre possíveis limitações e manter a recomendação separada do plano contratado, aumentando o cuidado de interface, persistência e suporte.
- **Scope**: Resultado da pesquisa, comparação de planos, contratação, troca de plano, dashboard, análises de IA e histórico de perfil.
- **Date**: 2026-09-24
- **Status**: active

### AD-006
- **Decision**: O produto manterá o nome FinView, atenderá autônomos, MEIs, microempresas e negócios ainda não formalizados de qualquer ramo, e terá como proposta organizar as finanças, aumentar a previsibilidade e apoiar o crescimento sustentável.
- **Reason**: A proposta amplia o mercado potencial sem abandonar o núcleo comum de gestão financeira empresarial; ramo de atuação e forma de atuação serão coletados para contextualizar análises e recomendações.
- **Evidence**: `docs/FUNDAMENTACAO_DECISOES.md#decisão-ad-006--posicionamento-amplo-com-contextualização-do-negócio`.
- **Definition**: `docs/DECISOES_PRODUTO.md#decisões-aprovadas-d01-d06`.
- **Trade-off**: Atender diferentes atividades aumenta a necessidade de categorias, perguntas e regras configuráveis e impede presumir que todos os negócios possuem a mesma operação.
- **Scope**: Marca, comunicação, onboarding, perfil do negócio, indicadores, análises de IA, pesquisa de maturidade e expansão comercial.
- **Date**: 2026-09-24
- **Status**: active

### AD-007
- **Decision**: Decisões técnicas e reversíveis poderão ser tomadas pela atuação Dev Sênior; decisões contábil-gerenciais serão propostas pela skill contábil; estratégia, preço, marca e aceitação de risco permanecerão sob aprovação do responsável pelo produto; matérias formais fiscais, contábeis, jurídicas e de privacidade exigirão validação profissional aplicável.
- **Reason**: A divisão reduz a quantidade de aprovações operacionais sem transferir para modelos de IA autoridade comercial, legal ou responsabilidade técnica profissional.
- **Evidence**: `docs/DECISOES_PRODUTO.md#governança-das-próximas-decisões`.
- **Trade-off**: As skills ganham autonomia dentro de limites documentados, mas deverão devolver para aprovação qualquer alteração de escopo, compromisso comercial ou risco relevante.
- **Scope**: Planejamento, UX/UI, arquitetura, regras gerenciais, documentação, implementação, validação e evolução do produto.
- **Date**: 2026-09-24
- **Status**: active

### AD-008
- **Decision**: A primeira etapa de entrada de dados oferecerá lançamento manual, importação de planilha e importação de extrato; integrações bancárias, sistemas externos e Open Finance permanecerão como evolução futura.
- **Reason**: Os três canais iniciais cobrem diferentes graus de organização sem introduzir imediatamente a dependência, o custo e a complexidade regulatória e operacional de integrações financeiras externas.
- **Evidence**: `docs/DECISOES_PRODUTO.md#d15--entrada-de-dados`.
- **Trade-off**: A primeira etapa exigirá validação de arquivos, prevenção de duplicidade e conciliação assistida, mas ainda dependerá de participação do usuário para importar e revisar dados.
- **Scope**: Onboarding, lançamentos, importações, conciliação, segurança, arquitetura e roadmap de integrações.
- **Date**: 2026-09-24
- **Status**: active

### AD-009
- **Decision**: O fluxo de caixa realizado será a visão financeira padrão; análises por competência serão adicionadas quando existirem datas de ocorrência, vencimentos, contas a pagar e contas a receber suficientemente confiáveis.
- **Reason**: A visão de caixa é mais imediatamente verificável para negócios com controles iniciais, enquanto competência exige dados adicionais e não pode ser inferida apenas do extrato bancário.
- **Evidence**: `docs/DECISOES_PRODUTO.md#d17---regime-das-análises` e `skills/consultor-contabil-pequenos-negocios/references/diagnostico.md`.
- **Trade-off**: O produto terá de manter e explicar duas perspectivas sem chamar variação de caixa de lucro nem apresentar uma visão gerencial como escrituração formal.
- **Scope**: Lançamentos, importações, dashboard, contas a pagar e receber, indicadores, análises da IA e relatórios.
- **Date**: 2026-09-24
- **Status**: active

### AD-010
- **Decision**: A recomendação inicial de nível será produzida por regras determinísticas, versionadas e explicáveis; a IA poderá explicar o resultado, mas não definir nem alterar a pontuação.
- **Reason**: Regras visíveis permitem testar consistência, revisar vieses e informar ao usuário quais respostas influenciaram a recomendação.
- **Evidence**: `docs/PESQUISA_PERFIL_NEGOCIO.md#modelo-inicial-de-pontuação`.
- **Trade-off**: O modelo inicial será menos flexível do que uma classificação gerada por IA e precisará ser recalibrado com dados do piloto.
- **Scope**: Pesquisa de maturidade, recomendação de nível, histórico, explicações da IA, testes e métricas do produto.
- **Date**: 2026-09-24
- **Status**: active

### AD-011
- **Decision**: O piloto adotará os preços mensais de R$ 79, R$ 149 e R$ 299 para Essencial, Gerencial e Completa, com teste de 30 dias sem cartão, opção anual equivalente a 10 mensalidades e políticas de mudança ou encerramento que preservem consulta e exportação dos dados.
- **Reason**: A política permite testar disposição a pagar e custo operacional sem contratação automática, perda de dados ou dependência imediata de um provedor de pagamento.
- **Evidence**: `docs/FUNDAMENTACAO_DECISOES.md#decisão-ad-011---política-comercial-do-piloto`.
- **Definition**: `docs/DECISOES_PRODUTO.md#decisões-comerciais-d36-d43`.
- **Trade-off**: Preços e benefícios comerciais ficam claros para o piloto, mas ainda exigem validação de margem, revisão jurídica e escolha posterior do provedor antes da cobrança real.
- **Scope**: Comparação de planos, teste, assinatura, upgrade, downgrade, cancelamento, limites, suporte, documentação e futuro checkout.
- **Date**: 2026-09-24
- **Status**: active

### AD-012
- **Decision**: O FinView adotará privacidade por finalidade e minimização: dados identificáveis de clientes não serão usados para treinamento ou fine-tuning; a Dev Sênior implementará controles e fluxos aprovados, enquanto bases legais, retenção definitiva, exceções de exclusão e responsabilidades formais dependerão de validação jurídica ou do responsável por privacidade.
- **Reason**: A separação permite avançar tecnicamente sem atribuir à skill autoridade para definir obrigações legais ou ampliar silenciosamente o uso de dados financeiros.
- **Evidence**: `docs/FUNDAMENTACAO_DECISOES.md#decisão-ad-012---limites-de-privacidade-e-autoridade-técnica`.
- **Definition**: `docs/DECISOES_PRODUTO.md#privacidade-e-dados-d44-d51`.
- **Trade-off**: O produto poderá construir inventário, segurança, exportação e trilhas de auditoria, mas não poderá lançar o tratamento em produção antes das definições jurídicas e organizacionais pendentes.
- **Scope**: Cadastro, perfil, movimentações, IA, logs, exportação, exclusão, atendimento ao titular, fornecedores e segurança.
- **Date**: 2026-09-24
- **Status**: active

### AD-013
- **Decision**: A evolução da IA seguirá uma arquitetura de provedores separados do Django, começando por skill local e recuperação de conhecimento; um modelo aberto executado em serviço próprio somente substituirá a API após benchmark de qualidade, segurança, latência, custo e operação.
- **Reason**: Treinar um modelo do zero não é proporcional ao estágio do produto, e acoplar inferência pesada ao processo web comprometeria disponibilidade e capacidade de reversão.
- **Evidence**: `docs/ARQUITETURA_IA.md#decisões-d52-d71` e `docs/FUNDAMENTACAO_DECISOES.md#decisão-ad-013---evolução-controlada-da-arquitetura-de-ia`.
- **Trade-off**: A aplicação continuará dependente da API atual durante a preparação da camada de provedores e dos benchmarks; o modelo próprio exigirá infraestrutura, monitoramento e manutenção adicionais.
- **Scope**: Integração de IA, prompts, RAG, privacidade, avaliação, infraestrutura, observabilidade, fallback, deploy e rollback.
- **Date**: 2026-09-24
- **Status**: active

### AD-014
- **Decision**: O MVP será entregue por marcos verificáveis e somente avançará para piloto controlado depois de gates técnicos, contábeis, de privacidade e operação; cobrança real, integrações bancárias e modelo próprio ficam fora do primeiro corte.
- **Reason**: A base atual precisa ser estabilizada e as novas jornadas dependem de dados confiáveis, validação profissional e evidências operacionais antes da ampliação do público.
- **Evidence**: `docs/ROADMAP_MVP_LANCAMENTO.md#decisões-d72-d84` e `docs/FUNDAMENTACAO_DECISOES.md#decisão-ad-014---lançamento-por-gates-e-piloto-controlado`.
- **Trade-off**: O piloto terá escopo menor e progressivo, mas permitirá medir utilidade, custos e riscos sem apresentar funcionalidades planejadas como concluídas.
- **Scope**: Arquitetura, segurança, dados, perfil, níveis, UX/UI, diagnóstico, plano de ação, piloto, suporte, monitoramento e lançamento.
- **Date**: 2026-09-24
- **Status**: active

### AD-015
- **Decision**: Cada plano terá franquias incluídas e permitirá adicionais configuráveis de usuários, empresas, importações, armazenamento e análises de IA, sempre com preço e impacto total apresentados antes da confirmação.
- **Reason**: A necessidade varia por empresa; adicionais preservam flexibilidade sem obrigar todos os clientes a contratar a maior capacidade.
- **Evidence**: `docs/DECISOES_PRODUTO.md#franquias-e-adicionais-d85-d89` e `docs/NIVEIS_E_FERRAMENTAS.md#franquias-e-adicionais-configuráveis`.
- **Trade-off**: O produto ganha flexibilidade comercial, mas precisará de medição auditável, alertas, teto de consumo e uma política de preços validada por custo, mercado e revisão jurídica.
- **Scope**: Planos, painel administrativo do cliente, medição, alertas, cobrança futura, suporte e auditoria.
- **Date**: 2026-09-24
- **Status**: active

## Handoff

### AD-016
- **Decision**: O primeiro corte do backend empresarial adota uma empresa padrão por usuário, categorias gerenciais e movimentações unificadas como fonte ativa, mantendo receitas e despesas antigas somente como legado reversível e sem dual-write.
- **Reason**: A vertical slice cria a base empresarial com isolamento e preserva o banco atual sem antecipar papéis, múltiplas empresas, importações ou indicadores dependentes de dados ainda ausentes.
- **Evidence**: `.specs/features/business-core/spec.md` e `.specs/features/business-core/validation.md`.
- **Trade-off**: Durante a transição coexistem tabelas legadas somente para rollback; novos fluxos operam exclusivamente por `FinancialTransaction`.
- **Scope**: Empresa, categorias, movimentações, migração, dashboard, mensal, despesas, recorrência, metas e contexto da IA.
- **Date**: 2026-09-25
- **Status**: active
