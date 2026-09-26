# Método de avaliação e tratamento de riscos

## Unidade mínima de análise

Registre cada risco com:

| Campo | Conteúdo |
|---|---|
| Contexto | Processo, funcionalidade e ambiente |
| Ativo | Dado, serviço, conta, segredo ou operação |
| Cenário | Ameaça explorando uma condição ou vulnerabilidade |
| Evidência | Código, configuração, log sanitizado, teste ou documento |
| Impacto | Confidencialidade, integridade, disponibilidade, privacidade e negócio |
| Probabilidade | Justificativa contextual, não impressão isolada |
| Controle atual | Prevenção, detecção, resposta ou recuperação existente |
| Tratamento | Mitigar, evitar, transferir ou aceitar |
| Responsável | Pessoa ou função que executa e pessoa que aceita o risco |
| Validação | Teste e resultado esperado |
| Risco residual | Exposição que permanece depois do tratamento |

## Priorização qualitativa

- **Crítica:** exploração ou falha com impacto grave e exposição imediata; requer contenção e decisão humana urgente.
- **Alta:** impacto material ou alta probabilidade, sem contenção adequada.
- **Média:** risco relevante, mas limitado por contexto ou controles existentes.
- **Baixa:** impacto e exposição reduzidos; pode entrar em melhoria programada.

Não classifique apenas pelo nome da vulnerabilidade. Considere dados, exposição, permissões, caminho de ataque, alcance e possibilidade de recuperação.

## Domínios de avaliação

Use as seis funções do NIST CSF 2.0 como cobertura gerencial:

1. **Governar:** contexto, papéis, políticas, fornecedores e risco.
2. **Identificar:** ativos, dados, dependências, ameaças e lacunas.
3. **Proteger:** acesso, treinamento, dados, plataforma e resiliência.
4. **Detectar:** eventos, anomalias, logs e monitoramento.
5. **Responder:** triagem, comunicação, contenção e análise.
6. **Recuperar:** restauração, validação, comunicação e aprendizado.

Para aplicações web, selecione requisitos verificáveis do OWASP ASVS conforme o risco; não alegue cobertura integral sem mapear e testar requisito por requisito.

## Regras específicas do FinView

- Dados financeiros e pessoais devem ser minimizados e isolados por usuário e empresa.
- Toda operação sensível deve validar autorização no servidor.
- Importações exigem validação de tipo, tamanho, estrutura, conteúdo, duplicidade e confirmação.
- Logs não devem conter segredo nem conteúdo financeiro identificável desnecessário.
- Cálculos financeiros permanecem determinísticos e separados da geração de texto por IA.
- Provedores de IA recebem somente campos aprovados e minimizados.
- Backup somente conta como controle quando a restauração é testada.
- Falhas de IA não podem impedir consulta, correção e exportação de dados.
- Cobranças adicionais exigem transparência de quantidade, preço, confirmação e trilha de auditoria; a skill avalia a segurança do fluxo, não define o preço.

## Saídas possíveis

- diagnóstico de risco;
- requisitos de segurança;
- checklist de revisão;
- plano de tratamento;
- critérios de aceite;
- evidências para go/no-go;
- encaminhamento para produto, jurídico/privacidade ou auditoria.
