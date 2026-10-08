# EV ChargeOps - Product Requirements Document

**Versão:** 0.4

**Status:** aprovado para implementação

**Data:** 30 de agosto de 2026

> A preparação da entrega foi atualizada em 08/10/2026. Consulte a [Sprint 2](../sprints/sprint-02/README.md) para prazo, apresentação online e evidências atuais.

**Problem frame:** [problem-frame.md](problem-frame.md)

**Success metrics:** [success-metrics.md](success-metrics.md)

**Tech spec:** [../technical/ev-chargeops-architecture.md](../technical/ev-chargeops-architecture.md)

## 0. O que mudou na versão 0.4 e por quê

A versão 0.3 previa tarifa, rateio, anomalia, previsão, segmentação e pagamento Pix no mesmo
incremento. O planejamento de agosto considerava a entrega em 20 de setembro e dois pitches curtos. O enunciado recebido em outubro fixa o prazo em 13/10/2026; o autor informou autorização para apresentação somente online. Seis
capacidades rasas não sustentam nenhum dos dois; uma trilha completa e auditável sustenta os
dois.

Esta versão recorta o escopo em **invoice-first**: da telemetria à fatura explicável, ponta a
ponta, com o que sobra empurrado para P1.

| Mudança | Motivo |
|---|---|
| Pagamento Pix (Mercado Pago sandbox) sai do escopo | O playbook oficial descreve a cobrança como *repasse na taxa condominial*, não como pagamento avulso. A fatura é o entregável; o gateway não acrescenta ao problema condominial |
| Previsão e segmentação vão para P1 | Ambas dependem de histórico. Nenhuma protege a integridade da fatura, que é o eixo do recorte |
| Detecção de anomalia vira parecer de fechamento, e permanece no P0 | É a única capacidade analítica que atua **antes** da fatura e pode bloquear a emissão. É a IA como motor lógico que a rubrica exige, não como penduricalho |
| A fórmula de rateio da Sprint 1 passa a ser contrato de implementação | Ela já foi entregue e avaliada, tem exemplo resolvido; energia e perdas são preservadas, com a divergência de taxa por unidade documentada na seção 4.4. Substituir a constante de `R$ 0,94/kWh` hoje presente no frontend |
| A unidade é o alvo da atribuição; o morador aparece pelo vínculo ativo | A Sprint 1 assumiu identidade por RFID. O campo invalidou a premissa: o carregador da FIAP não tem cartões configurados, o `Card ID` repete o serial do equipamento em **todas as 145 sessões de oito meses**, a coluna `RFID Card Name` vem vazia e a OpenAPI da GoodWe não expõe nenhum campo de identidade. A premissa mudou, não o planejamento |
| Um cartão registrado atribui sozinho; o gestor sobrepõe quando decide | O equipamento suporta RFID e o relatório reserva colunas para o portador. O que não existe no dado do fabricante é a ligação entre cartão, unidade e cobrança. O cadastro de cartões faz essa ponte uma vez, e a atribuição automática passa a valer para todas as recargas seguintes; `session_assignments.origin` mantém as duas origens distinguíveis para auditoria |
| A visão do morador é a própria fatura, alcançada por impersonate | Um artefato serve os dois papéis, com autorização como filtro. Evita construir duas telas e evita troca de login no meio do pitch |
| Entra o agregado de energia do carregador como total de controle | Permite reconciliar a energia faturada contra o número do próprio fabricante, em vez de comparar a importação consigo mesma |

A Sprint 1 permanece válida como entregue. O que mudou foi o que o acesso real ao SEMS+ e à
documentação da OpenAPI revelaram depois dela.

## 1. Visão do produto

O EV ChargeOps é uma camada de operação e inteligência para recarga compartilhada em
condomínios e edifícios corporativos. A plataforma transforma registros heterogêneos de
carregamento em sessões auditáveis, atribui consumo a unidades, calcula rateio, detecta
anomalias e emite faturas explicáveis, preservando a procedência de cada informação.

## 2. Objetivo desta entrega

Demonstrar uma fatia vertical funcional na qual a telemetria real observada no SEMS+ percorre
ingestão, normalização, atribuição à unidade, tarifa versionada, rateio, parecer explicável,
aprovação do fechamento, fatura por unidade e PDF auditável, com a visão do morador alcançada
a partir da mesma fatura.

```text
SEMS+ real ou cenário demonstrativo identificado
  → importação auditável
  → atribuição às unidades
  → tarifa e rateio versionados
  → parecer explicável da IA
  → aprovação do fechamento
  → fatura por unidade
  → PDF auditável
  → visão do morador
```

## 3. Personas e permissões

### Gestor (síndico)

- Importa lotes e acompanha erros.
- Revisa recargas sem identidade e as atribui a unidades.
- Revisa o parecer analítico antes da emissão.
- Fecha períodos e emite faturas.
- Visualiza a fatura como o morador a vê, por impersonate auditado.
- Visualiza métricas consolidadas do condomínio.

### Morador

- Visualiza somente sua unidade, recargas e faturas.
- Consulta a composição da cobrança e a procedência dos dados.
- Baixa a fatura em PDF.

No incremento atual não existe login de morador. O papel permanece no modelo de autorização e
é exercido pelo gestor via impersonate, com escopo de unidade e somente leitura. Criar uma
porta de entrada própria para o morador não altera o modelo.

### Operador técnico

- Consulta lotes, registros brutos, falhas de normalização e trilha de auditoria.
- Não altera recargas faturadas sem uma operação de correção registrada.

No protótipo, uma mesma conta administrativa exerce Gestor e Operador Técnico. A separação de
papéis permanece no modelo de autorização.

## 4. Escopo funcional

### 4.1 Organização e identidade

- Uma organização representa o condomínio ou empresa.
- Uma organização possui locais, carregadores, unidades e usuários.
- A primeira demonstração terá uma organização e um local ativos, mas todas as entidades
  operacionais serão isoladas por `organizationId`.
- O login será fornecido pelo Supabase Auth e a autorização aplicada pelo FastAPI.
- O gestor pode assumir um contexto de morador restrito a uma unidade. Esse contexto usa o
  mesmo resolver de autorização e o mesmo escopo de repositório de um morador real, é somente
  leitura e gera evento de auditoria.

### 4.2 Ingestão

Duas fontes distintas, com procedência separada e sem mistura silenciosa.

**Recargas (faturáveis).** O gestor seleciona a origem e envia um arquivo CSV.

- A aplicação apresenta pré-visualização antes de persistir recargas.
- Cada importação gera um lote com origem, checksum, nome do arquivo, horário e resultado.
- Registros inválidos são rejeitados individualmente com código, campo e mensagem de erro.
- Reimportar o mesmo lote ou a mesma recarga não cria duplicatas.
- O registro bruto é preservado para auditoria.

**Agregado do carregador (total de controle, não faturável).** Energia por dia informada pelo
próprio equipamento.

- Nenhuma linha do agregado vira recarga, é atribuída a uma unidade ou entra em uma fatura.
- Serve exclusivamente para reconciliar a energia faturada contra o número do fabricante.
- A interface identifica a origem em todas as telas onde o valor aparece.

### 4.3 Recargas e atribuição

- Dados da origem são convertidos para um modelo canônico.
- Recargas podem permanecer sem unidade.
- O gestor atribui uma recarga a uma unidade, registrando ator, data e justificativa.
- A interface diferencia identidade confirmada, atribuída e desconhecida.
- Energia, horários e origem não são alterados pela atribuição.
- O `Card ID` bruto é evidência, nunca identidade confirmada.

### 4.4 Tarifa e rateio

O modelo é o definido e avaliado na Sprint 1, adotado aqui como contrato de implementação:

```text
fatura(unidade, mês) = energia_individual + taxa_infra + rateio_perdas

  energia_individual = Σ (energia_kwh da recarga × tarifa do posto horário)
  taxa_infra         = valor fixo cobrado uma vez de cada unidade que
                       carregou no mês
  rateio_perdas      = percentual sobre energia_individual, proporcional ao consumo
```

- O sistema armazena tarifas versionadas por vigência, fonte e data de captura.
- Os valores de referência da Sprint 1 são ponta `R$ 1,25/kWh`, intermediário `R$ 0,95/kWh` e
  fora de ponta `R$ 0,78/kWh`, taxa de infraestrutura de `R$ 25,00` por unidade ativa no mês e
  perdas de `4%` sobre a energia individual.
- O cálculo identifica qual faixa tarifária se aplica a cada recarga.
- Valores monetários são calculados e armazenados em centavos inteiros.
- Reexecutar o cálculo com os mesmos dados e a mesma versão de regra produz o mesmo resultado.
- Uma fatura emitida preserva um snapshot imutável das regras e tarifas usadas.

Casos excepcionais, conforme a Sprint 1:

- **Recarga interrompida.** Cobra-se a energia efetivamente entregue; a recarga permanece
  registrada com seu status para auditoria.
- **Unidade sem consumo no mês.** Fatura zerada, sem taxa de infraestrutura. A política é
  estritamente pay-per-use.
- **Dois veículos na mesma unidade.** As recargas somam na mesma unidade, que é o alvo durável
  da cobrança. Quando houver identidade confiável por veículo, o detalhe pode ser exibido sem
  alterar a responsabilidade financeira.

  **Divergência registrada em relação à Sprint 1.** A Sprint 1 faturava por usuário RFID, então
  a unidade U102, com dois veículos, pagava a taxa de infraestrutura duas vezes (R$ 50,00). No
  modelo por unidade ela paga uma vez (R$ 25,00). A energia e as perdas dessa unidade
  reproduzem exatamente; a diferença tem uma causa e uma linha. A razão é que o dado de campo
  não permite distinguir dois veículos — o carregador da FIAP não tem cartões configurados e a
  OpenAPI da GoodWe não expõe nenhum campo de identidade —, então cobrar por unidade é a única
  regra que os dados sustentam, e é a mais defensável em assembleia. Se um condomínio quiser
  cobrar por veículo, isso se torna um parâmetro de `BillingPolicy` quando houver identidade.

### 4.5 Fechamento do período

- O período lista recargas elegíveis e excluídas, com motivo.
- Exibe cobertura de atribuição e pendências bloqueantes.
- Reconcilia a energia faturada contra a energia elegível, com diferença esperada de
  `0,00 kWh`, e contra o agregado do carregador no mesmo período.
- Exige aprovação explícita do administrador.
- Cria snapshot imutável da política e das tarifas usadas.
- Uma recarga já faturada não muda de fatura por edição silenciosa.

### 4.6 Fatura e PDF

- A fatura pertence a uma unidade e a um período.
- Contém a lista de recargas, energia, tarifa aplicada por faixa, taxa de infraestrutura,
  perdas e total.
- Exibe o morador ou contato de cobrança pelo vínculo ativo da unidade.
- Exibe procedência dos dados, versão da regra e identificador auditável.
- Pode ser gerada e baixada em PDF com a identidade visual do produto.
- Alterações posteriores de tarifa ou regra não mudam faturas já emitidas.

### 4.7 Insights e IA

**No escopo desta entrega — parecer de fechamento.**

- Regras determinísticas identificam horários inválidos, energia não positiva, potência média
  incompatível com o equipamento, duplicidades e desvios relevantes frente ao histórico
  disponível.
- Cada achado contém regra ou algoritmo, severidade, evidência, explicação e confiança.
- O parecer consolidado apresenta conclusão, severidade, confiança, evidências e recomendação.
- Dados insuficientes geram resultado explicitamente inconclusivo, nunca precisão artificial.
- Achados críticos bloqueiam o fechamento até decisão registrada.
- O administrador mantém a decisão final.

**Adiado para P1.** Previsão de consumo e demanda, segmentação de perfis de uso e interface
conversacional. As três permanecem no plano de produto e mantêm os requisitos já escritos
(FR-14, FR-21 e FR-22), fora do incremento atual.

### 4.8 Experiência

- O dashboard do gestor mostra energia, recargas, cobertura de atribuição, pendências,
  reconciliação e progresso do fechamento do período selecionado.
- O dashboard deriva seus números do read model canônico de recargas; identificadores brutos
  do carregador não representam moradores ou unidades.
- Pendências do período abrem uma fila operacional filtrada.
- Após confirmar uma importação, o gestor recebe um handoff explícito para continuar o
  fechamento.
- A navegação principal representa destinos recorrentes; a importação permanece em
  `Configurações > Fontes de dados`.
- A fatura é uma única página, servindo tanto a revisão do gestor quanto a visão do morador. O
  contexto de morador é indicado por um aviso permanente e é somente leitura.
- Toda tela que combina dados reais e demonstrativos apresenta sua procedência.
- A interface é em português e usa `Recargas`, não `Sessões`.

## 5. Fluxo principal

1. Gestor autentica e abre o local do LAB FIAP.
2. Gestor importa um CSV do SEMS+ ou seleciona o cenário demonstrativo rotulado.
3. Sistema valida, normaliza e deduplica o lote.
4. Gestor revisa as recargas sem identificação e as associa a unidades.
5. Sistema aplica a tarifa versionada vigente, identificando sua referência.
6. Sistema apresenta o parecer analítico do período, com evidências.
7. Gestor resolve os bloqueios e aprova o fechamento.
8. Sistema emite as faturas por unidade e congela o snapshot de cálculo.
9. Gestor abre a fatura de uma unidade como o morador a vê.
10. Fatura é baixada em PDF.

## 6. Requisitos funcionais

| ID | Requisito | Critério de aceite |
|---|---|---|
| FR-01 | Autenticar usuários | Token válido identifica usuário e organização; token ausente ou inválido recebe 401 |
| FR-02 | Autorizar por papel e organização | Usuário não acessa dados de outra organização ou ações fora do papel |
| FR-03 | Criar lote de importação | Arquivo aceito produz lote com checksum, origem e status |
| FR-04 | Pré-visualizar importação | Antes da confirmação, exibe contagens de válidos, inválidos e duplicados |
| FR-05 | Normalizar recarga SEMS+ | Campos observados são convertidos para o modelo canônico sem perder o registro bruto |
| FR-06 | Garantir idempotência | Reimportação não cria segunda recarga para a mesma chave natural |
| FR-07 | Explicar rejeição | Registro inválido apresenta código, campo e motivo acionável |
| FR-08 | Atribuir recarga | Gestor vincula recarga a uma unidade e a operação fica auditada |
| FR-09 | Expor confiança de identidade | Cada recarga mostra `confirmed`, `assigned` ou `unknown` |
| FR-10 | Versionar tarifa | Tarifa registra valores por faixa, vigência, fonte e data de captura |
| FR-11 | Calcular rateio | Fatura aplica energia por faixa, taxa de infraestrutura e perdas conforme regra versionada |
| FR-12 | Preservar cálculo emitido | Alterações posteriores de tarifa não mudam faturas já emitidas |
| FR-13 | Detectar anomalias | Fixtures anômalos definidos no plano de testes geram achados explicáveis |
| FR-14 | Prever consumo ou demanda | **Adiado para P1.** Requisito preservado sem alteração |
| FR-15 | Criar Pix sandbox | **Adiado para P1.** Requisito preservado sem alteração |
| FR-16 | Processar webhook idempotente | **Adiado para P1.** Requisito preservado sem alteração |
| FR-17 | Exibir dashboard do gestor | Métricas respeitam organização, local e período selecionados |
| FR-18 | Exibir visão do morador | Contexto de morador vê somente unidades, recargas e faturas autorizadas |
| FR-19 | Exibir procedência | Campos relevantes identificam fonte real, atribuída, simulada, derivada ou externa |
| FR-20 | Exportar evidência | Gestor exporta resumo do período com recargas, regras, faturas e fontes |
| FR-21 | Segmentar perfis de uso | **Adiado para P1.** Requisito preservado sem alteração |
| FR-22 | Reproduzir execução de IA | Cada execução registra algoritmo, versão, parâmetros, seed quando aplicável e referência imutável do dataset |
| FR-23 | Ingerir agregado do carregador | Energia diária informada pelo equipamento é persistida com procedência e nunca vira recarga faturável |
| FR-24 | Reconciliar energia | O fechamento compara energia faturada com energia elegível e com o agregado do carregador, exibindo as diferenças |
| FR-25 | Aprovar o fechamento | Período só fecha por ação explícita do administrador e com bloqueios resolvidos |
| FR-26 | Congelar snapshot | O fechamento grava versão de tarifa, política e parâmetros usados, de forma imutável |
| FR-27 | Emitir fatura por unidade | Fatura apresenta unidade, contato, recargas, energia, tarifa por faixa, infraestrutura, perdas, total e identificador auditável |
| FR-28 | Gerar PDF | Fatura emitida gera PDF baixável com a mesma composição exibida em tela |
| FR-29 | Apresentar parecer explicável | Parecer exibe conclusão, severidade, confiança, evidências e recomendação, ou declara-se inconclusivo |
| FR-30 | Assumir contexto de morador | Impersonate é somente leitura, restrito a uma unidade, passa pelo caminho real de autorização e gera evento de auditoria |
| FR-31 | Reproduzir o exemplo da Sprint 1 | O motor preserva energia e perdas de `data/exemplos/faturas.csv`, reproduz os totais das unidades com um usuário e verifica a redução de uma taxa em U102, conforme seção 4.4 |

## 7. Requisitos não funcionais

| ID | Requisito |
|---|---|
| NFR-01 | TypeScript será usado no frontend e client da API; Python será usado no backend e módulos de IA |
| NFR-02 | O domínio não importará SDKs de Supabase, ANEEL ou GoodWe |
| NFR-03 | Toda escrita relevante registrará ator, instante e organização |
| NFR-04 | Segredos existirão somente em variáveis de ambiente ou secret manager |
| NFR-05 | Valores monetários serão armazenados em centavos inteiros; energia, em decimal com precisão definida no banco |
| NFR-06 | Instantes serão armazenados em UTC e apresentados no fuso do local |
| NFR-07 | Importações, cálculos e fechamentos serão idempotentes |
| NFR-08 | A API publicará contrato OpenAPI e erros estruturados |
| NFR-09 | Testes de domínio não dependerão de rede ou serviços externos |
| NFR-10 | Nenhum fluxo enviará comandos ao equipamento do LAB FIAP |
| NFR-11 | Módulos analíticos dependerão de modelos canônicos e ports, não de payloads GoodWe, DataFrames ou acesso direto ao banco |
| NFR-12 | Execuções de IA com componentes estocásticos usarão seed controlada nos testes |
| NFR-13 | O arredondamento monetário será definido uma única vez no domínio e aplicado de forma idêntica em cálculo, exibição e PDF |

## 8. Fora do escopo

- Integração GoodWe sem credenciais oficiais.
- Automação permanente da interface do SEMS+.
- Controle remoto, OCPP ou Modbus.
- Pagamentos, reais ou sandbox.
- Login próprio de morador.
- Reserva de vagas e filas de carregamento.
- Aplicativos móveis nativos.
- Correção ou reabertura formal de períodos fechados.
- Treinamento de modelos complexos ou serviço de IA separado.

## 9. Riscos e respostas

| Risco | Resposta de produto |
|---|---|
| Formato real do export difere do observado | Isolar parser no adapter e manter fixture versionado por formato |
| Histórico de recargas por sessão continua indisponível | O agregado diário sustenta gráfico, KPI e reconciliação; o cenário demonstrativo rotulado sustenta a fatura, com procedência explícita |
| Identidade não vem do SEMS+ nem da API GoodWe | Atribuição manual explícita à unidade, com justificativa e nível de confiança |
| Tarifa pública não reproduz a conta completa | Rotular como estimativa base e registrar componentes, fonte e vigência |
| Reconciliação contra o agregado acusa diferença | Exibir a diferença como bloqueio ou alerta, nunca absorvê-la silenciosamente na fatura |
| Demonstração ao vivo falha no dia da prova | Manter captura gravada do fluxo completo como plano B |
| Escopo cresce para controle do carregador | Manter controle remoto como non-goal desta entrega |

## 10. Definition of done do incremento demonstrável

- O fluxo principal funciona de ponta a ponta com dados reais e demonstrativos identificados.
- Os critérios de aceite ativos possuem teste automatizado ou roteiro de demonstração
  rastreável. Os requisitos adiados permanecem documentados e sem implementação.
- O motor de rateio preserva energia e perdas do exemplo da Sprint 1 e verifica a divergência documentada da taxa única por unidade.
- O cálculo permanece igual em reexecuções sobre o mesmo snapshot.
- A reimportação não cria duplicatas.
- A soma da energia faturada reconcilia com a energia elegível em `0,00 kWh`, e a diferença
  contra o agregado do carregador é exibida.
- A demonstração inclui um achado analítico explicado, um fechamento aprovado, uma fatura
  emitida, um PDF baixado e a fatura vista no contexto do morador.
- README, PRD, métricas, Tech Spec e ADRs refletem o comportamento entregue.
