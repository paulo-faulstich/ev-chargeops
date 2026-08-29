# EV ChargeOps - Success Metrics

**Status:** proposta consolidada para revisão

**Data:** 29 de agosto de 2026

## 1. Princípio de medição

As métricas separam sucesso do protótipo, resultado operacional futuro e critérios acadêmicos. Os targets do MVP validam comportamento do sistema; não representam ainda impacto comercial comprovado.

## 2. North Star Metric

### Auditable Session Coverage

Percentual das sessões válidas do período que possuem procedência registrada, consumo validado, atribuição utilizável e inclusão rastreável em uma fatura.

```text
Auditable Session Coverage =
  sessões faturadas com procedência + atribuição válidas
  ----------------------------------------------------- × 100
             sessões válidas importadas
```

Uma sessão excluída por erro permanece no denominador até ser corrigida ou formalmente descartada com justificativa.

## 3. Métricas de outcome

| Métrica | Definição | Direção desejada |
|---|---|---|
| Cobertura de atribuição | Sessões válidas associadas a uma unidade / sessões válidas | Aumentar |
| Consumo não atribuído | kWh válidos sem unidade / kWh válidos importados | Reduzir |
| Tempo de fechamento | Tempo entre início da revisão e emissão das faturas | Reduzir |
| Reconciliação energética | Diferença absoluta entre kWh importado elegível e kWh faturado | Aproximar de zero |
| Taxa de contestação | Faturas contestadas / faturas emitidas | Reduzir |
| Tempo de resolução | Tempo mediano entre flag de anomalia e decisão registrada | Reduzir |
| Conversão de cobrança | Faturas pagas / cobranças emitidas | Aumentar |

As métricas de impacto serão baselineadas somente após uso por gestores reais. O protótipo instrumentará os eventos necessários para medi-las.

## 4. Acceptance metrics do MVP

| ID | Métrica | Target do MVP | Evidência |
|---|---|---|---|
| M-01 | Cobertura de ingestão do fixture SEMS+ | 100% dos registros classificados como válidos, inválidos ou duplicados | Resultado do lote |
| M-02 | Duplicação em reimportação | 0 novas sessões ao reimportar o mesmo lote | Teste de idempotência |
| M-03 | Cobertura de procedência | 100% das sessões persistidas com fonte, lote e registro bruto | Consulta de auditoria |
| M-04 | Determinismo do rateio | 100% das reexecuções idênticas para o mesmo snapshot | Teste de domínio |
| M-05 | Reconciliação do fixture | Diferença de 0,00 kWh entre sessões elegíveis e itens faturados | Relatório de fechamento |
| M-06 | Transparência de identidade | 100% das sessões com confiança `confirmed`, `assigned` ou `unknown` | Consulta de sessões |
| M-07 | Detecção de casos preparados | 100% dos fixtures anômalos conhecidos sinalizados com explicação | Teste de regras |
| M-08 | Isolamento organizacional | 0 acesso cruzado nos testes de autorização | Teste de segurança |
| M-09 | Integração tarifária | Uma tarifa versionada com fonte, vigência e captura demonstrada | Registro de tarifa |
| M-10 | Integração de pagamento | Uma ordem Pix sandbox criada e atualizada por webhook idempotente | Log de demonstração |
| M-11 | Proveniência na interface | 100% das telas de sessão e fatura identificam dados reais, atribuídos e simulados | Teste E2E |
| M-12 | Segurança do equipamento | 0 comandos ou alterações enviados ao carregador | Revisão de integrações |

## 5. Guardrail metrics

- Zero segredo versionado no Git.
- Zero pagamento em produção.
- Zero sessão simulada apresentada como real.
- Zero modificação remota do carregador.
- Zero fatura emitida para sessão crítica não revisada.
- Zero acesso de morador a dados de outra unidade não autorizada.

## 6. Eventos de produto

| Evento | Propriedades mínimas |
|---|---|
| `import_started` | organizationId, source, batchId, timestamp |
| `import_completed` | batchId, validCount, invalidCount, duplicateCount |
| `session_assigned` | sessionId, previousConfidence, newConfidence, actorId |
| `anomaly_flagged` | sessionId, ruleCode, severity |
| `billing_period_closed` | periodId, sessionCount, energyKwh, invoiceCount |
| `invoice_issued` | invoiceId, amountCents, sessionCount |
| `payment_order_created` | invoiceId, provider, externalStatus |
| `payment_status_changed` | invoiceId, previousStatus, newStatus |

Eventos não armazenarão nome, e-mail, cartão completo ou payload sensível de pagamento.

## 7. Alinhamento com a avaliação

| Critério do desafio | Evidência mensurável |
|---|---|
| Arquitetura funcional | Lote rastreável do input à fatura e ao pagamento |
| Gestão e estrutura de dados | M-01 a M-06 |
| Papel da IA | M-07 e explicações das regras/insights |
| Aderência ao contexto | M-11, M-12 e uso de sessões SEMS+ |
| Visão de produto real | M-09, M-10 e métricas de outcome instrumentadas |

## 8. Cadência futura

- Métricas do lote: a cada importação.
- Métricas de fechamento: mensalmente.
- Métricas de produto: painel móvel de 30 e 90 dias.
- Revisão de regras de anomalia: após cada falso positivo ou falso negativo confirmado.
- Revisão de targets comerciais: depois do primeiro ciclo com baseline real.
