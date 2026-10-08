# Sprint 2 — Desenvolvimento e prototipação

**Enterprise Challenge 2026 · GoodWe + FIAP · Fase 6 · Grupo 17**

Paulo Roberto Faulstich Rego · RM 572292

A Sprint 2 implementa o fluxo do EV ChargeOps: importar recargas, atribuir unidades, aplicar tarifa e rateio, revisar o parecer analítico e emitir faturas auditáveis.

## Entrega

O enunciado da atividade no FIAP ON pede um arquivo **TXT com o link do repositório**, contendo código-fonte, README atualizado, justificativas dos desvios em relação à Sprint 1 e evidências de funcionamento. O prazo informado é **13/10/2026 às 23h59**.

O arquivo preparado está em [docs/entregas/sprint-02.txt](../../entregas/sprint-02.txt). Publicar o repositório não equivale a enviar a atividade no portal; a confirmação de envio pertence ao FIAP ON.

O enunciado menciona validação por pitch presencial. **O autor informou em 08/10/2026 que recebeu autorização para realizar somente a apresentação online.** A evidência é o [vídeo da apresentação no YouTube](https://youtu.be/B1YzQmRzsfg), confirmado pelo autor nesta mesma data: 3min54s, enviado em 02/09/2026 e com visibilidade não listada. A autorização para apresentação somente online é registrada como relato do autor.

## Roteiro para avaliação

1. Consultar a [solução implementada e as instruções de execução](../../../README.md).
2. Ver as [evidências e a demonstração](evidencias.md).
3. Comparar os [desvios justificados](desvios-e-decisoes.md) com a [proposta original](../sprint-01/arquivo-original/README.md).
4. Consultar o [uso de ferramentas de IA no desenvolvimento](../../uso_ia.md).

| Critério do enunciado | Peso | Onde verificar |
|---|---:|---|
| Lógica central implementada | 3,0 | Importação, atribuição, fechamento, faturas; `apps/api/app/modules/` e roteiro de reprodução |
| Módulo de IA estrutural e integrado | 3,0 | `billing/domain/opinion.py`, bloqueios no fechamento e testes; limites e capacidades adiadas descritos nos desvios |
| Evidência de funcionamento | 2,0 | Demonstração, resultados reproduzidos e testes nas evidências |
| Autoria e compreensão | 1,0 | Decisões justificadas, histórico de commits, registro de uso de IA e apresentação do autor |
| README atualizado e organização | 1,0 | README principal e documentação separada por sprint |

Esta tabela localiza as evidências; não atribui nota nem substitui a avaliação do professor.

## O que está implementado

- Backend FastAPI e interface Next.js com escopo por organização.
- Importação SEMS+ validada, idempotente e rastreável até o registro bruto.
- Atribuição por cartão cadastrado ou decisão manual auditada.
- Tarifa por horário de início, política de rateio e cálculos em centavos.
- Parecer analítico com regras de integridade e detecção estatística de outliers.
- Revisão de achados, aprovação de fechamento, faturas imutáveis e PDF.
- Visão de morador por contexto restrito de unidade, acionada pelo gestor.

API GoodWe, previsão, clustering, Pix e login independente de morador não estão implementados. Consulte as justificativas e consequências em [desvios e decisões](desvios-e-decisoes.md).
