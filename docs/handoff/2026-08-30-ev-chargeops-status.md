# EV ChargeOps — Handoff de produto e engenharia

**Data:** 30 de agosto de 2026  
**Worktree:** `/Users/paulofaulstich/Dropbox/Workspace/__claude/personal/education/fiap/challenges/good-we/ev-chargeops/.worktrees/dashboard-operational`  
**Branch:** `codex/dashboard-operational`  
**HEAD no momento do handoff:** `85046b9 fix: apply harmonized co-brand typography`

## 1. Estado do Git

- A árvore de trabalho estava limpa antes da criação deste documento.
- A branch está 24 commits à frente de `main` e 0 commits atrás.
- Portanto, ela pode ser integrada localmente com fast-forward:

```bash
cd /Users/paulofaulstich/Dropbox/Workspace/__claude/personal/education/fiap/challenges/good-we/ev-chargeops
git merge --ff-only codex/dashboard-operational
```

- A `main` local já estava 43 commits à frente de `origin/main` antes dessa integração. Nenhum push remoto foi executado neste handoff.
- Antes de integrar, é prudente executar o gate completo descrito na seção 7.

## 2. Problema que o produto deve resolver

> Síndicos e usuários de infraestruturas compartilhadas de recarga não possuem uma forma integrada e auditável de atribuir sessões a unidades, calcular o consumo individual, aplicar regras de rateio e acompanhar a cobrança. Os dados existem no SEMS+, mas não estão conectados ao contexto condominial nem disponíveis por API para o desafio.

Documento de referência: [`docs/product/problem-frame.md`](../product/problem-frame.md).

O upload CSV é somente um adapter temporário porque a API de EV Chargers da GoodWe não será disponibilizada. Ele não é o produto principal. O produto é o fechamento mensal auditável: recarga, identidade, custo, decisão e cobrança.

## 3. O que está entregue

### Fundação e arquitetura

- Monorepo com Next.js/React no frontend, FastAPI/Python no backend e client TypeScript gerado de OpenAPI.
- Supabase Auth e PostgreSQL/Supabase previstos por configuração; modo de fixture continua disponível para desenvolvimento e testes.
- Domínio isolado de fornecedores por módulos e ports/adapters.
- Módulos backend existentes: `identity`, `organizations`, `ingestion`, `sessions` e `audit`.

### Ingestão SEMS+

- Upload e drag-and-drop de CSV.
- Prévia antes de persistir.
- Validação por linha, classificação de inválidos e deduplicação.
- Confirmação idempotente, histórico de lotes e procedência.
- CTA pós-importação para continuar o fechamento ou importar outro arquivo.

### Operação mensal

- Dashboard operacional em `/dashboard`.
- Recargas em `/sessions`.
- Fontes de dados em `/settings/data-sources`.
- A navegação é recorrente, não um stepper global.
- Progresso do fechamento é exibido no dashboard e pertence ao período.

### Atribuição

- Fila de recargas pendentes.
- Atribuição explícita à unidade condominial com justificativa.
- Alteração auditada sem modificar energia, horários ou procedência observados.
- A responsabilidade financeira durável pertence à unidade; o morador/contato pode ser exibido por meio do vínculo ativo.

### Dashboard e identidade visual

- KPIs de energia, custo estimado, cobertura de atribuição e pendências.
- Consumo diário derivado das sessões canônicas.
- Prévia de custos agrupada por unidade.
- Header persistente, menu de perfil e logout.
- Co-branding `EV ChargeOps`, `FIAP Challenge × GoodWe` e indicação `Powered by GoodWe / SEMS+`.
- Web configurada para a porta `3407`; API para `8407`, evitando as portas padrão usadas por outros projetos.

## 4. Limitações atuais importantes

### O gráfico de consumo não está quebrado

O fixture importado atualmente possui somente duas recargas no dia 29/08/2026. Por isso o gráfico mostra uma única barra de 10,50 kWh. Não devem ser inventados dias adicionais e apresentados como telemetria real.

Fixture atual:

`apps/api/tests/fixtures/sems_sessions.csv`

Já existe um conjunto demonstrativo mais rico da Sprint 1 em:

- `data/exemplos/sessoes.csv`
- `data/exemplos/faturas.csv`
- `data/exemplos/usuarios.csv`
- `data/exemplos/unidades.csv`

Ele ainda precisa ser convertido para um cenário de demonstração compatível com o fluxo atual e marcado visualmente como **dado demonstrativo**, nunca como SEMS+ real.

### “Custos por responsável” ainda não é cobrança

O dashboard hoje:

- agrupa as sessões atribuídas por unidade;
- soma a energia;
- multiplica por uma constante local de `R$ 0,94/kWh`;
- não possui tarifa persistida/versionada;
- não aplica taxa de infraestrutura ou perdas;
- não cria período fechado, snapshot de cálculo, fatura ou PDF.

O nome mais correto para o componente atual seria **“Prévia de cobrança por unidade”**.

### A solução ainda não fecha o problem statement ponta a ponta

O fluxo entregue termina em “quem consumiu quanto e qual é o custo simples estimado”. Ainda faltam rateio, parecer da IA, aprovação do fechamento, fatura explicável e visão do morador.

## 5. O que falta implementar

### P0 — Vertical slice recomendada para o pitch

1. **Dataset demonstrativo mensal com procedência**
   - várias datas, unidades e perfis;
   - ao menos uma anomalia intencional;
   - selector/badge claro entre `SEMS+ real` e `Cenário demonstrativo`;
   - nenhuma mistura silenciosa das origens.

2. **Tarifa e regras de rateio versionadas**
   - valor da energia;
   - vigência, fonte e data de referência;
   - taxa de infraestrutura;
   - regra de perdas/rateio;
   - cálculo determinístico em centavos.

3. **Fechamento mensal**
   - sessões elegíveis e excluídas;
   - cobertura de atribuição;
   - pendências bloqueantes;
   - reconciliação de energia com diferença esperada de `0,00 kWh`;
   - aprovação explícita do administrador;
   - snapshot imutável das regras usadas.

4. **IA híbrida e explicável**
   - regras determinísticas para impossibilidades, duplicidades e desvios;
   - comparação com histórico quando houver amostra suficiente;
   - parecer com severidade, confiança, evidências e recomendação;
   - resultado inconclusivo quando os dados forem insuficientes;
   - administrador mantém a decisão final.

5. **Fatura por unidade/morador**
   - período, unidade e contato responsável;
   - lista de recargas;
   - energia, tarifa, infraestrutura, perdas e total;
   - procedência e versão da regra;
   - identificador auditável;
   - emissão e download em PDF com identidade visual do produto.

6. **Visão do morador**
   - consumo e recargas da unidade autorizada;
   - composição da cobrança;
   - parecer/recomendação pertinente;
   - download da fatura PDF.

### P1 — Depois da vertical slice

- Previsão de consumo com horizonte, amostra, erro e incerteza.
- Segmentação reproduzível de perfis de uso.
- Integração de tarifa pública, preservando cache e evidência da resposta.
- Pagamento Pix em Mercado Pago sandbox, caso ainda haja prazo e seja importante demonstrar integração transacional.

### P2 — Evolução posterior

- Webhooks e ciclo completo de pagamento.
- Notificações.
- Múltiplos locais/condomínios na experiência.
- Adapters de API ou protocolos futuros quando a GoodWe disponibilizar acesso.
- Correção/reabertura formal de períodos fechados.

## 6. Decisão de escopo pendente

O PRD aprovado ainda exige tarifa, rateio, anomalia, previsão, segmentação e Mercado Pago sandbox. A recomendação mais recente é priorizar uma vertical slice **invoice-first**:

```text
SEMS+ real ou demo identificado
  → importação auditável
  → atribuição às unidades
  → cálculo/rateio transparente
  → parecer explicável da IA
  → aprovação do fechamento
  → fatura por morador/unidade
  → PDF auditável
```

O pagamento sandbox seria adiado para P1. Essa alteração ainda deve ser aprovada explicitamente e, se aprovada, refletida em:

- `docs/product/prd.md`;
- `docs/product/success-metrics.md`;
- `docs/technical/ev-chargeops-architecture.md`;
- um novo design e plano de implementação.

Não tratar essa recomendação como funcionalidade já entregue.

## 7. Como executar e verificar

### Dependências

```bash
cd /Users/paulofaulstich/Dropbox/Workspace/__claude/personal/education/fiap/challenges/good-we/ev-chargeops/.worktrees/dashboard-operational
pnpm install
uv sync --project apps/api
```

### Configuração

Os segredos não são versionados. Usar os exemplos:

- `apps/api/.env.example`
- `apps/web/.env.example`

As chaves esperadas incluem, entre outras, `DATABASE_URL`, configurações Supabase, `SUPABASE_SERVICE_ROLE_KEY`, `NEXT_PUBLIC_API_URL` e `API_PROXY_TARGET`. Não expor a service role no frontend.

### Banco

```bash
pnpm db:upgrade
```

### Rodar localmente

Em terminais separados:

```bash
pnpm dev:api
pnpm dev:web
```

Abrir:

- Web: `http://127.0.0.1:3407`
- Health da API: `http://127.0.0.1:8407/health`

No momento deste handoff havia processos ouvindo nas duas portas, mas PIDs e sessões de terminal não devem ser considerados permanentes.

### Gate completo antes de integração/push

```bash
pnpm check
```

Esse comando executa lint e typecheck do backend, testes API e integração, validação de migrations, drift do contrato OpenAPI, testes/typecheck do client, lint/build web e Playwright.

O gate completo **não foi reexecutado durante a preparação deste handoff**. Não afirmar que a HEAD atual está integralmente verde sem rodá-lo novamente.

## 8. Próximo passo recomendado

1. Aprovar ou rejeitar explicitamente o recorte `invoice-first` e o adiamento do Mercado Pago.
2. Atualizar PRD e métricas se aprovado.
3. Escrever design do domínio de tarifa, fechamento, billing e PDF.
4. Implementar por testes, começando pelo cálculo determinístico e reconciliação.
5. Adicionar cenário demonstrativo mensal com procedência.
6. Implementar parecer explicável antes da aprovação.
7. Gerar fatura/PDF e visão do morador.
8. Ensaiar um roteiro de pitch de 90–120 segundos mostrando a trilha completa da sessão até a fatura.

## 9. Critério para considerar a solução “matadora”

Uma demonstração deve permitir que o avaliador veja, sem explicação defensiva:

1. de onde veio cada recarga;
2. por que ela foi atribuída àquela unidade;
3. como cada centavo foi calculado;
4. o que a IA encontrou e quais evidências sustentam o parecer;
5. quem aprovou o fechamento;
6. como a fatura volta às sessões originais;
7. que o morador consegue compreender e baixar a própria cobrança.

O upload e o gráfico são suporte. A história principal é transformar telemetria limitada em uma cobrança condominial auditável, explicável e pronta para decisão.
