# Prompt de continuação para a próxima IA

Você está assumindo um trabalho em andamento no projeto **EV ChargeOps**. **Não recomece o projeto, não crie outra arquitetura e não descarte o que já foi implementado.** Continue a partir da branch e do worktree abaixo.

## Contexto operacional obrigatório

- Repositório principal: `/Users/paulofaulstich/Dropbox/Workspace/__claude/personal/education/fiap/challenges/good-we/ev-chargeops`
- Worktree de trabalho: `/Users/paulofaulstich/Dropbox/Workspace/__claude/personal/education/fiap/challenges/good-we/ev-chargeops/.worktrees/dashboard-operational`
- Branch: `codex/dashboard-operational`
- Commit-base do handoff: `3a5ca87 docs: record product and engineering handoff`. Este prompt foi versionado depois dele; confirme a HEAD com `git log -1 --oneline`.
- A branch estava 25 commits à frente de `main` antes deste prompt e pode ser integrada por fast-forward depois da verificação.
- A árvore estava limpa no momento deste prompt.
- Não existe push ou merge pendente autorizado implicitamente. Verifique antes de executar qualquer um deles.
- Não crie outro worktree: use o existente.
- Não exponha nem versione segredos. Os `.env.example` documentam somente os nomes das variáveis.

Leia integralmente, nesta ordem, antes de alterar código:

1. [`2026-08-30-ev-chargeops-status.md`](2026-08-30-ev-chargeops-status.md)
2. [`../product/problem-frame.md`](../product/problem-frame.md)
3. [`../product/prd.md`](../product/prd.md)
4. [`../product/success-metrics.md`](../product/success-metrics.md)
5. [`../technical/ev-chargeops-architecture.md`](../technical/ev-chargeops-architecture.md)
6. [`../superpowers/specs/2026-08-30-recurring-close-and-session-assignment-design.md`](../superpowers/specs/2026-08-30-recurring-close-and-session-assignment-design.md)

## O problema de produto

Síndicos e usuários de infraestrutura compartilhada de recarga não possuem uma forma integrada e auditável de atribuir recargas a unidades, calcular consumo individual, aplicar rateio e acompanhar a cobrança. Os dados existem no SEMS+, mas não vêm conectados ao contexto condominial e a API de EV Chargers não será disponibilizada no desafio.

O CSV é apenas o adapter temporário causado pela falta de API. **O produto não é uma plataforma de upload.** O produto deve transformar telemetria limitada em fechamento e cobrança condominial auditáveis.

## O que já funciona

- Next.js/React no frontend, FastAPI/Python no backend e client TypeScript gerado de OpenAPI.
- Autenticação/configuração Supabase e isolamento por organização.
- Upload e drag-and-drop de CSV SEMS+.
- Prévia, validação por linha, deduplicação, confirmação idempotente e histórico de importação.
- Sessões canônicas chamadas de **Recargas** na interface.
- Fila operacional para recargas sem identidade.
- Atribuição auditável da recarga à unidade condominial, com justificativa.
- Dashboard com energia, custo simples estimado, cobertura de atribuição, pendências e consumo diário.
- Navegação recorrente: `Visão geral`, `Recargas`, `Fontes de dados`.
- Header persistente com local, perfil e logout.
- Co-branding `EV ChargeOps` + `FIAP Challenge × GoodWe`.
- Web na porta `3407` e API na porta `8407`.

Módulos backend existentes:

- `audit`
- `identity`
- `ingestion`
- `organizations`
- `sessions`

Não existem ainda módulos funcionais de `tariffs`, `billing`, `payments` ou `insights`.

## Estado atual que não deve ser confundido com funcionalidade pronta

### Gráfico diário

O CSV usado na demonstração atual contém duas recargas, ambas no dia 29/08/2026. Portanto, o gráfico possui uma única barra. Isso não é bug do gráfico.

Não invente dias e os apresente como dados reais. A solução recomendada é criar um **cenário demonstrativo mensal explicitamente rotulado**, reutilizando os dados da Sprint 1 em `data/exemplos/`, e manter a distinção visual entre:

- `SEMS+ real`;
- `Cenário demonstrativo`.

### Custos

O componente atual `Custos por responsável` não é uma fatura. Ele:

- agrupa por unidade;
- soma energia;
- multiplica por uma constante frontend de `R$ 0,94/kWh`;
- não possui tarifa versionada, infraestrutura, perdas, fechamento, snapshot ou PDF.

O título recomendado é **Prévia de cobrança por unidade** e deve futuramente exibir também o morador/contato de cobrança.

## Decisões de UX já tomadas pelo usuário

Não reverta estas decisões sem uma razão concreta e aprovação:

- A aplicação deve parecer um sistema operacional, não uma landing page.
- Evitar títulos gigantes, margens excessivas e telas vazias.
- Toda tela deve indicar a ação seguinte quando houver uma ação operacional.
- Upload/importação é coadjuvante e permanece em `Configurações > Fontes de dados`.
- A navegação lateral não é um stepper; o processo se repete todos os meses.
- O progresso do fechamento pertence ao período e fica no dashboard.
- Usar `Recargas`, não `Sessões`, na interface.
- Abaixo do título da página, explicar brevemente o que existe naquele menu.
- Breadcrumbs devem seguir a mesma estrutura e o mesmo espaçamento.
- Perfil e logout devem permanecer visíveis em todas as telas autenticadas.
- A interface está em português.
- O estilo deve trazer referência à GoodWe sem fingir que o protótipo é um produto oficial da empresa.
- A assinatura visual aprovada é a variação harmonizada atual. Não refaça o logo sem solicitação.
- A IA deve ser híbrida e explicável: regras/evidências automáticas, decisão final do administrador.

## Direção de produto recomendada, mas ainda pendente de aprovação explícita

Priorizar uma vertical slice **invoice-first**:

```text
SEMS+ real ou cenário demo identificado
  → importação auditável
  → atribuição às unidades
  → tarifa e rateio transparentes
  → parecer explicável da IA
  → aprovação do fechamento
  → faturas por unidade/morador
  → PDF auditável
```

O PRD atual ainda exige previsão, segmentação e Mercado Pago sandbox. A recomendação é:

- P0: dataset demo com procedência, tarifa/rateio, fechamento, IA explicável, fatura e PDF, visão do morador;
- P1: previsão, segmentação, tarifa pública integrada e Mercado Pago sandbox;
- P2: pagamentos completos, notificações e adapters futuros.

**Primeira ação da próxima IA:** confirmar com Paulo se o recorte `invoice-first` está aprovado e se o Mercado Pago pode ser movido para P1. Faça uma pergunta objetiva e única. Não altere PRD ou código de billing antes dessa confirmação.

## Depois da aprovação: sequência obrigatória

### 1. Atualizar contrato de produto

Atualizar PRD, success metrics e arquitetura para refletir o recorte aprovado. Registrar claramente o que mudou e por quê; a Sprint 1 já foi entregue e avaliada, portanto não reescrever a história como se o planejamento anterior estivesse errado.

### 2. Desenhar antes de implementar

Criar um design curto para:

- tarifa versionada;
- regra de rateio;
- período de fechamento;
- snapshot imutável;
- invoice e invoice items;
- parecer da IA;
- PDF;
- visão do morador.

Apresentar as decisões mais relevantes a Paulo para aprovação antes de começar implementação extensa.

### 3. Implementar por vertical slice e testes

Ordem sugerida:

1. cálculo determinístico em centavos;
2. reconciliação de energia com diferença `0,00 kWh`;
3. persistência de tarifa, período e snapshot;
4. dataset demonstrativo mensal e procedência;
5. parecer explicável e bloqueios;
6. aprovação/fechamento;
7. faturas por unidade;
8. geração/download do PDF;
9. visão do morador;
10. refinamento do dashboard e roteiro de pitch.

Não implementar apenas novas telas com valores mockados. O pitch precisa demonstrar o fluxo real pelo domínio e banco.

## Critérios mínimos do P0

- O gestor consegue importar ou selecionar dados demonstrativos claramente rotulados.
- Cada recarga elegível está atribuída a uma unidade ou bloqueia o fechamento.
- O cálculo usa tarifa e regras versionadas.
- Soma da energia faturada reconcilia com a energia elegível em `0,00 kWh`.
- O parecer da IA mostra conclusão, severidade, confiança, evidências e recomendação.
- O administrador aprova explicitamente o fechamento.
- Faturas emitidas não mudam quando tarifa ou regra futura muda.
- A fatura exibe morador/contato, unidade, recargas, energia, tarifa, infraestrutura, perdas e total.
- O PDF é gerado e pode ser baixado.
- A visão do morador respeita autorização e mostra apenas sua unidade.
- Dados reais e demonstrativos nunca são apresentados como se fossem a mesma procedência.

## Arquivos úteis para começar

- Dashboard UI: `apps/web/src/components/dashboard/dashboard-overview.tsx`
- Agregação atual: `apps/web/src/components/dashboard/dashboard-summary.ts`
- Rotas web: `apps/web/src/app/(app)/`
- Shell/navegação: `apps/web/src/components/shell/app-shell.tsx`
- Sessões backend: `apps/api/app/modules/sessions/`
- Ingestão backend: `apps/api/app/modules/ingestion/`
- Migrations: `apps/api/alembic/versions/`
- Dados ricos da Sprint 1: `data/exemplos/`
- Fixture SEMS+ mínimo: `apps/api/tests/fixtures/sems_sessions.csv`
- Testes de dashboard: `apps/web/e2e/dashboard.spec.ts`
- Testes de recargas: `apps/web/e2e/session-review.spec.ts`

## Como rodar

```bash
cd /Users/paulofaulstich/Dropbox/Workspace/__claude/personal/education/fiap/challenges/good-we/ev-chargeops/.worktrees/dashboard-operational
pnpm install
uv sync --project apps/api
pnpm db:upgrade
```

Em terminais separados:

```bash
pnpm dev:api
pnpm dev:web
```

- Web: `http://127.0.0.1:3407`
- API: `http://127.0.0.1:8407`

Segredos não estão no Git. Use `apps/api/.env.example` e `apps/web/.env.example`; não imprima os valores reais no chat ou nos logs.

## Verificação

Antes de afirmar que algo está pronto ou integrar a branch:

```bash
pnpm check
```

O gate completo não foi executado durante a criação do handoff. Execute-o na HEAD antes de merge/push. Se houver falha, diagnostique-a antes de alterar comportamento. Não esconda falhas de ambiente como se fossem sucesso funcional.

## Integração

Após implementação aprovada, testes verdes e revisão:

```bash
cd /Users/paulofaulstich/Dropbox/Workspace/__claude/personal/education/fiap/challenges/good-we/ev-chargeops
git merge --ff-only codex/dashboard-operational
```

Não faça push sem autorização. A `main` local já estava à frente de `origin/main` no handoff.

## Forma de trabalhar com Paulo

- Responda em português.
- Seja direto sobre o que está entregue, simulado, pendente ou bloqueado.
- Não deixe uma etapa longa sem atualização objetiva de progresso.
- Se o trabalho for interrompido, preserve tudo e atualize este handoff com commits, arquivos, testes e próximo passo exato.
- Não consuma tempo refazendo decisões visuais já aprovadas.
- O objetivo não é maximizar quantidade de features; é apresentar uma história coerente, funcional e auditável da recarga até a cobrança.
