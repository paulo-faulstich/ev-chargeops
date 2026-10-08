# EV ChargeOps - Success Metrics

**Versão:** 0.2

**Status:** aprovado para implementação

**Data:** 30 de agosto de 2026

**PRD:** [prd.md](prd.md)

## 0. O que mudou na versão 0.2

Alinhamento ao recorte invoice-first do [PRD 0.4](prd.md). As métricas de pagamento, previsão
e segmentação foram marcadas como adiadas, sem alteração de conteúdo, para preservar
rastreabilidade com a Sprint 1. Entraram métricas para reconciliação contra o agregado do
fabricante, imutabilidade da fatura emitida, geração de PDF, reprodução do exemplo resolvido
da Sprint 1 e isolamento do contexto de morador.

## 1. Princípio de medição

As métricas separam sucesso do protótipo, resultado operacional futuro e critérios acadêmicos.
Os targets do MVP validam comportamento do sistema; não representam ainda impacto comercial
comprovado.

## 2. North Star Metric

### Auditable Session Coverage

Percentual das recargas válidas do período que possuem procedência registrada, consumo
validado, atribuição utilizável e inclusão rastreável em uma fatura.

```text
Auditable Session Coverage =
  recargas faturadas com procedência + atribuição válidas
  ------------------------------------------------------- × 100
             recargas válidas importadas
```

Uma recarga excluída por erro permanece no denominador até ser corrigida ou formalmente
descartada com justificativa.

## 3. Métricas de outcome

| Métrica | Definição | Direção desejada |
|---|---|---|
| Cobertura de atribuição | Recargas válidas associadas a uma unidade / recargas válidas | Aumentar |
| Consumo não atribuído | kWh válidos sem unidade / kWh válidos importados | Reduzir |
| Tempo de fechamento | Tempo entre início da revisão e emissão das faturas | Reduzir |
| Reconciliação interna | Diferença absoluta entre kWh elegível e kWh faturado | Aproximar de zero |
| Reconciliação externa | Diferença absoluta entre kWh faturado e o agregado do carregador no período | Aproximar de zero, ou explicada |
| Taxa de contestação | Faturas contestadas / faturas emitidas | Reduzir |
| Tempo de resolução | Tempo mediano entre achado analítico e decisão registrada | Reduzir |

As métricas de impacto serão baselineadas somente após uso por gestores reais. O protótipo
instrumentará os eventos necessários para medi-las.

## 4. Acceptance metrics do MVP

| ID | Métrica | Target do MVP | Evidência |
|---|---|---|---|
| M-01 | Cobertura de ingestão do fixture SEMS+ | 100% dos registros classificados como válidos, inválidos ou duplicados | Resultado do lote |
| M-02 | Duplicação em reimportação | 0 novas recargas ao reimportar o mesmo lote | Teste de idempotência |
| M-03 | Cobertura de procedência | 100% das recargas persistidas com fonte, lote e registro bruto | Consulta de auditoria |
| M-04 | Determinismo do rateio | 100% das reexecuções idênticas para o mesmo snapshot | Teste de domínio |
| M-05 | Reconciliação interna | Diferença de 0,00 kWh entre recargas elegíveis e itens faturados | Relatório de fechamento |
| M-06 | Transparência de identidade | 100% das recargas com confiança `confirmed`, `assigned` ou `unknown` | Consulta de recargas |
| M-07 | Detecção de casos preparados | 100% dos fixtures anômalos conhecidos sinalizados com explicação | Teste de regras |
| M-08 | Isolamento organizacional | 0 acesso cruzado nos testes de autorização | Teste de segurança |
| M-09 | Integração tarifária | Uma tarifa versionada com faixas, fonte, vigência e captura demonstrada | Registro de tarifa |
| M-10 | Integração de pagamento | **Adiada para P1.** Métrica preservada sem alteração | — |
| M-11 | Proveniência na interface | 100% das telas de recarga e fatura identificam dados reais, atribuídos e simulados | Teste E2E |
| M-12 | Segurança do equipamento | 0 comandos ou alterações enviados ao carregador | Revisão de integrações |
| M-13 | Previsão demonstrável | **Adiada para P1.** Métrica preservada sem alteração | — |
| M-14 | Segmentação reproduzível | **Adiada para P1.** Métrica preservada sem alteração | — |
| M-15 | Rastreabilidade da IA | 100% dos resultados apresentados possuem versão do algoritmo e referência do dataset | Consulta de auditoria |
| M-16 | Comparação com o exemplo da Sprint 1 | Energia e perdas preservadas por unidade; totais iguais nas unidades com um usuário; redução explícita de R$ 25,00 em U102 pela taxa única. Inclui os três casos excepcionais | Testes golden e justificativa na seção 4.4 do PRD |
| M-17 | Reconciliação externa | A diferença entre energia faturada e agregado do carregador é calculada e exibida no fechamento, nunca absorvida em silêncio | Relatório de fechamento |
| M-18 | Imutabilidade da fatura | Alterar tarifa ou política após a emissão não altera nenhum valor de fatura já emitida | Teste de domínio |
| M-19 | Aprovação explícita | 0 faturas emitidas sem ação de aprovação registrada com ator e instante | Consulta de auditoria |
| M-20 | Geração de PDF | Fatura emitida gera PDF baixável cuja composição confere com a exibida em tela | Teste E2E |
| M-21 | Isolamento do contexto de morador | Contexto de morador não retorna dados de outra unidade, e o acesso passa pelo mesmo resolver de autorização de um morador real | Teste de autorização |
| M-22 | Auditoria do impersonate | 100% dos acessos em contexto de morador geram evento de auditoria com ator, unidade e instante | Consulta de auditoria |

## 5. Guardrail metrics

- Zero segredo versionado no Git.
- Zero recarga simulada apresentada como real.
- Zero valor agregado do fabricante apresentado como recarga faturável.
- Zero modificação remota do carregador.
- Zero fatura emitida para recarga crítica não revisada.
- Zero fatura emitida sem aprovação explícita.
- Zero acesso de contexto de morador a dados de outra unidade.
- Zero escrita a partir de um contexto de morador.

## 6. Eventos de produto

| Evento | Propriedades mínimas |
|---|---|
| `import_started` | organizationId, source, batchId, timestamp |
| `import_completed` | batchId, validCount, invalidCount, duplicateCount |
| `aggregate_imported` | batchId, source, periodFrom, periodTo, dayCount |
| `session_assigned` | sessionId, previousConfidence, newConfidence, actorId |
| `anomaly_flagged` | sessionId, ruleCode, severity |
| `closing_opinion_generated` | periodId, insightRunId, severity, confidence, blockingCount |
| `billing_period_closed` | periodId, sessionCount, energyKwh, invoiceCount, actorId |
| `invoice_issued` | invoiceId, unitId, amountCents, sessionCount |
| `invoice_pdf_downloaded` | invoiceId, actorId, context |
| `resident_context_entered` | actorId, unitId, timestamp |

Eventos não armazenarão nome, e-mail ou payload sensível.

## 7. Alinhamento com a avaliação

| Critério do desafio | Evidência mensurável |
|---|---|
| Arquitetura funcional | Lote rastreável do input à fatura e ao PDF |
| Gestão e estrutura de dados | M-01 a M-06, M-16 e M-17 |
| Papel da IA | M-07 e M-15, com o parecer atuando antes da fatura e bloqueando a emissão |
| Aderência ao contexto | M-11, M-12, M-17 e uso de recargas reais do SEMS+ |
| Visão de produto real | M-09, M-18 a M-22 e métricas de outcome instrumentadas |

## 8. Cadência futura

- Métricas do lote: a cada importação.
- Métricas de fechamento: mensalmente.
- Revisão de regras de anomalia: após cada falso positivo ou falso negativo confirmado.
- Revisão de targets comerciais: depois do primeiro ciclo com baseline real.
