# EV ChargeOps - Product Requirements Document

**Versão:** 0.3

**Status:** aprovado para implementação

**Data:** 30 de agosto de 2026

**Problem frame:** [problem-frame.md](problem-frame.md)

**Success metrics:** [success-metrics.md](success-metrics.md)

**Tech spec:** [../technical/ev-chargeops-architecture.md](../technical/ev-chargeops-architecture.md)

## 1. Visão do produto

O EV ChargeOps é uma camada de operação e inteligência para recarga compartilhada em condomínios e edifícios corporativos. A plataforma transforma registros heterogêneos de carregamento em sessões auditáveis, atribui consumo a unidades, calcula rateio, detecta anomalias, prevê consumo e segmenta perfis de uso, além de acompanhar cobranças.

## 2. Objetivo desta entrega

Demonstrar uma fatia vertical funcional na qual dados reais observados no SEMS+ percorrem ingestão, normalização, atribuição, tarifa, rateio, módulos de IA e pagamento sandbox, mantendo explícita a procedência de cada informação e as limitações da amostra.

## 3. Personas e permissões

### Gestor

- Importa lotes e acompanha erros.
- Gerencia unidades, moradores e vínculos demonstrativos.
- Revisa sessões e anomalias.
- Fecha períodos e emite faturas.
- Cria cobranças sandbox e acompanha status.
- Visualiza métricas consolidadas do condomínio.

### Morador

- Visualiza somente sua unidade, sessões e faturas.
- Consulta composição da cobrança e procedência dos dados.
- Visualiza QR Code e status do pagamento sandbox.
- Recebe insights relacionados ao próprio consumo.

### Operador técnico

- Consulta lotes, registros brutos, falhas de normalização e trilha de auditoria.
- Não altera sessões faturadas sem uma operação de correção registrada.

No protótipo, uma mesma conta administrativa poderá exercer Gestor e Operador Técnico. A separação de papéis permanece no modelo de autorização.

## 4. Escopo funcional

### 4.1 Organização e identidade

- Uma organização representa o condomínio ou empresa.
- Uma organização possui locais, carregadores, unidades e usuários.
- A primeira demonstração terá uma organização e um local ativos, mas todas as entidades operacionais serão isoladas por `organizationId`.
- O login será fornecido pelo Supabase Auth e a autorização aplicada pelo FastAPI.

### 4.2 Ingestão

- O gestor seleciona a origem e envia um arquivo CSV.
- A aplicação apresenta pré-visualização antes de persistir sessões.
- Cada importação gera um lote com origem, checksum, nome do arquivo, horário e resultado.
- Registros inválidos são rejeitados individualmente com código, campo e mensagem de erro.
- Reimportar o mesmo lote ou a mesma sessão não cria duplicatas.
- O registro bruto é preservado para auditoria.

### 4.3 Sessões e atribuição

- Dados da origem são convertidos para um modelo canônico.
- Sessões podem permanecer sem usuário ou unidade.
- O gestor pode atribuir uma sessão a uma unidade, registrando ator, data e justificativa.
- A interface diferencia identidade confirmada, atribuída e desconhecida.
- Energia, horários e origem não são alterados pela atribuição.

### 4.4 Tarifa e rateio

- O sistema armazena tarifas versionadas por vigência e procedência.
- O cálculo identifica quais faixas tarifárias intersectam cada sessão.
- A fatura contém energia individual, tarifa aplicada, taxa de infraestrutura, perdas e total.
- Reexecutar o cálculo com os mesmos dados e regras produz o mesmo resultado.
- Uma fatura emitida preserva um snapshot das regras e tarifas usadas.

### 4.5 Insights e IA

- O sistema compara energia, duração, potência média derivada e potência nominal.
- Regras identificam valores impossíveis, incompatíveis ou significativamente diferentes do histórico disponível.
- Cada anomalia contém severidade, explicação, evidência e regra aplicada.
- Uma previsão estima consumo ou demanda para um horizonte definido, informando amostra, erro de validação e incerteza.
- Uma segmentação agrupa perfis por frequência, consumo, duração e horário predominante, informando dataset e parâmetros usados.
- Resultados de IA registram versão, parâmetros, procedência do dataset e métricas de avaliação suficientes para reprodução.
- Dados insuficientes geram resultado inconclusivo ou limitação explícita; não serão mascarados com precisão artificial.
- Recomendações de horário usam tarifa e, quando disponível, contexto solar; não enviam comandos ao carregador.

### 4.6 Pagamento

- Uma fatura emitida pode criar uma ordem Pix no Mercado Pago sandbox.
- A aplicação armazena o identificador externo e o estado da ordem.
- Webhooks válidos atualizam o pagamento de forma idempotente.
- Nenhuma credencial real ou pagamento em produção fará parte da demonstração.

### 4.7 Experiência

- O dashboard do gestor mostra energia, sessões, cobertura de atribuição, faturas, anomalias e pagamentos.
- O dashboard deriva energia, custo estimado e cobertura somente das sessões canônicas; identificadores brutos do carregador não representam moradores ou unidades.
- Pendências do período abrem uma fila operacional filtrada, na qual a unidade e a justificativa são registradas sem alterar energia, horários ou procedência observados.
- Após confirmar uma importação, o gestor recebe um handoff explícito para continuar o fechamento ou iniciar outro lote.
- A navegação principal representa destinos recorrentes (`Visão geral` e `Sessões`), enquanto a importação SEMS+ permanece em `Configurações > Fontes de dados`.
- A visão do morador mostra consumo, sessões, composição da fatura e recomendações.
- Toda tela que combina dados reais e demonstrativos apresenta sua procedência.

## 5. Fluxo principal

1. Gestor autentica e abre o local do LAB FIAP.
2. Gestor importa um CSV do SEMS+.
3. Sistema valida, normaliza e deduplica o lote.
4. Gestor revisa sessões sem identificação e as associa a unidades demonstrativas.
5. Sistema obtém ou reutiliza uma tarifa ANEEL válida, identificando sua referência.
6. Gestor fecha o período e gera faturas.
7. Sistema sinaliza anomalias antes da emissão.
8. Gestor emite a fatura e cria uma cobrança Pix sandbox.
9. Um webhook de teste atualiza o pagamento.
10. Gestor e morador consultam suas respectivas visões.

## 6. Requisitos funcionais

| ID | Requisito | Critério de aceite |
|---|---|---|
| FR-01 | Autenticar usuários | Token válido identifica usuário e organização; token ausente ou inválido recebe 401 |
| FR-02 | Autorizar por papel e organização | Usuário não acessa dados de outra organização ou ações fora do papel |
| FR-03 | Criar lote de importação | Arquivo aceito produz lote com checksum, origem e status |
| FR-04 | Pré-visualizar importação | Antes da confirmação, exibe contagens de válidos, inválidos e duplicados |
| FR-05 | Normalizar sessão SEMS+ | Campos observados são convertidos para o modelo canônico sem perder o registro bruto |
| FR-06 | Garantir idempotência | Reimportação não cria segunda sessão para a mesma chave natural |
| FR-07 | Explicar rejeição | Registro inválido apresenta código, campo e motivo acionável |
| FR-08 | Atribuir sessão | Gestor vincula sessão a usuário/unidade e a operação fica auditada |
| FR-09 | Expor confiança de identidade | Cada sessão mostra `confirmed`, `assigned` ou `unknown` |
| FR-10 | Versionar tarifa | Tarifa registra valores, vigência, fonte e data de captura |
| FR-11 | Calcular rateio | Fatura aplica energia, taxa de infraestrutura e perdas conforme regra versionada |
| FR-12 | Preservar cálculo emitido | Alterações posteriores de tarifa não mudam faturas já emitidas |
| FR-13 | Detectar anomalias | Fixtures anômalos definidos no plano de testes geram flags explicáveis |
| FR-14 | Prever consumo ou demanda | Sistema apresenta horizonte, base de cálculo, erro de validação e incerteza da previsão |
| FR-15 | Criar Pix sandbox | Fatura elegível gera ordem de teste, QR Code e identificador externo |
| FR-16 | Processar webhook idempotente | Eventos repetidos não duplicam transições ou lançamentos |
| FR-17 | Exibir dashboard do gestor | Métricas respeitam organização, local e período selecionados |
| FR-18 | Exibir visão do morador | Morador vê somente unidades, sessões e faturas autorizadas |
| FR-19 | Exibir procedência | Campos relevantes identificam fonte real, atribuída ou simulada |
| FR-20 | Exportar evidência | Gestor exporta resumo do período com sessões, regras, faturas e fontes |
| FR-21 | Segmentar perfis de uso | Sistema agrupa usuários por atributos documentados e expõe parâmetros, métricas e procedência do dataset |
| FR-22 | Reproduzir execução de IA | Cada execução registra algoritmo, versão, parâmetros, seed quando aplicável e referência imutável do dataset |

## 7. Requisitos não funcionais

| ID | Requisito |
|---|---|
| NFR-01 | TypeScript será usado no frontend e client da API; Python será usado no backend e módulos de IA |
| NFR-02 | O domínio não importará SDKs de Supabase, Mercado Pago, ANEEL ou GoodWe |
| NFR-03 | Toda escrita relevante registrará ator, instante e organização |
| NFR-04 | Segredos existirão somente em variáveis de ambiente ou secret manager |
| NFR-05 | Valores monetários serão armazenados em centavos inteiros; energia, em decimal com precisão definida no banco |
| NFR-06 | Instantes serão armazenados em UTC e apresentados no fuso do local |
| NFR-07 | Importações, cálculos e webhooks serão idempotentes |
| NFR-08 | A API publicará contrato OpenAPI e erros estruturados |
| NFR-09 | Testes de domínio não dependerão de rede ou serviços externos |
| NFR-10 | Nenhum fluxo enviará comandos ao equipamento do LAB FIAP |
| NFR-11 | Módulos analíticos dependerão de modelos canônicos e ports, não de payloads GoodWe, DataFrames ou acesso direto ao banco |
| NFR-12 | Execuções de IA com componentes estocásticos usarão seed controlada nos testes e registrarão os parâmetros da demonstração |

## 8. Fora do escopo

- Integração GoodWe sem credenciais oficiais.
- Automação permanente da interface do SEMS+.
- Controle remoto, OCPP ou Modbus.
- Pagamentos reais.
- Reserva de vagas e filas de carregamento.
- Aplicativos móveis nativos.
- Treinamento de modelos complexos, inferência generativa crítica ou serviço de IA separado no primeiro incremento.

## 9. Riscos e respostas

| Risco | Resposta de produto |
|---|---|
| Formato real do export difere do observado | Isolar parser no adapter e manter fixture versionado por formato |
| Histórico é curto para previsão | Exibir erro e incerteza; retornar inconclusivo quando a amostra não sustentar a estimativa |
| Dados reais não identificam usuários suficientes para clustering | Usar atribuições ou fixtures simulados com procedência visível e não apresentar os segmentos como comportamento real da planta |
| Identidade não vem do SEMS+ | Atribuição manual explícita com nível de confiança |
| Tarifa pública não reproduz a conta completa | Rotular como estimativa base e registrar componentes usados |
| Sandbox externo fica indisponível | Preservar request/response de teste sanitizado e demonstrar retry controlado |
| Escopo cresce para controle do carregador | Manter controle remoto como non-goal desta entrega |

## 10. Definition of done do incremento demonstrável

- O fluxo principal funciona de ponta a ponta com fixtures reais e demonstrativos identificados.
- Todos os critérios de aceite FR-01 a FR-22 possuem teste automatizado ou roteiro de demonstração rastreável.
- O cálculo reproduz o conjunto esperado e permanece igual em reexecuções.
- A reimportação não cria duplicatas.
- A demonstração inclui uma anomalia explicada, uma previsão com incerteza, uma segmentação reproduzível e uma ordem Pix sandbox.
- README, PRD, métricas, Tech Spec e ADRs refletem o comportamento entregue.
