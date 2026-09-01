# EV ChargeOps — prompt de continuação

> Substitui a versão anterior, escrita quando os passos 5 a 8 ainda estavam
> pendentes. O histórico detalhado das etapas anteriores continua em
> [`2026-08-30-ev-chargeops-status.md`](2026-08-30-ev-chargeops-status.md).

Você está assumindo um trabalho em andamento. **Não recomece, não redesenhe a
arquitetura e não descarte o que já existe.** Continue de onde parou.

## Contexto operacional obrigatório

- Worktree: `/Users/paulofaulstich/Dropbox/Workspace/__claude/personal/education/fiap/challenges/good-we/ev-chargeops/.worktrees/dashboard-operational`
- Branch: `codex/dashboard-operational`
- O incremento de faturamento **está commitado**. Confirme com `git status` antes
  de qualquer coisa e **não commite sem pedir**.
- Não crie outro worktree. Não faça push nem merge sem autorização.
- Responda em português. Seja direto sobre o que está pronto, simulado, pendente
  ou bloqueado.

## Leitura obrigatória, nesta ordem

1. [`../product/prd.md`](../product/prd.md) — versão 0.4, com a seção 0 explicando cada mudança
2. [`../product/success-metrics.md`](../product/success-metrics.md) — versão 0.2
3. [`../technical/ev-chargeops-architecture.md`](../technical/ev-chargeops-architecture.md) — versão 0.2
4. [`../superpowers/specs/2026-08-30-tariff-close-and-invoicing-design.md`](../superpowers/specs/2026-08-30-tariff-close-and-invoicing-design.md) — **o design implementado**
5. [`../../README.md`](../../README.md) seções 5 e 6 — modelo de rateio e papel da IA da Sprint 1

## Decisões já tomadas — não reabra sem motivo concreto

- **Recorte invoice-first.** Mercado Pago, previsão e segmentação foram para P1.
- **A unidade é o alvo da atribuição**, não o usuário. O morador aparece pelo
  vínculo ativo; sem vínculo, a fatura mostra o nome da unidade. Isso é o
  fallback desenhado, não uma lacuna.
- **A visão do morador é a própria fatura**, alcançada por impersonate, pelo
  mesmo `current_scope` que um morador real usaria. Sem segunda tela.
- **Arredondamento uma vez por recarga.** Cada linha impressa é conferível.
- **Faixa tarifária pelo horário de início.** Não dividir energia entre faixas.
- **Taxa de infraestrutura fixa por unidade ativa.**
- **Reconciliação dupla.** A interna bloqueia; a externa (contra o agregado do
  carregador) é alerta e nunca é absorvida em nenhuma fatura.

## Estado atual: o incremento está completo e verde

- **324 testes Python**, ruff e mypy limpos, sem drift de migration nem de contrato.
- **44 testes Playwright passando.**
- Client TypeScript com `tsc` e 19 testes vitest; web com `tsc` e `eslint`.
- **A demonstração roda sobre dado real da GoodWe.** Julho/2026 fechado com as 17
  recargas reais do `Charging Record` do SEMS+: 4 faturas, R$ 270,12, e a soma de
  energia (167,77 kWh) confere com o mês real. A fatura declara
  `Procedência: dados reais`.
- PDF byte-idêntico em dois downloads, com `ETag` igual ao sha256 do conteúdo.

Passos 1 a 4 (cálculo, persistência, readiness, parecer) seguem como descrito no
histórico. O que foi concluído depois:

### 5. Fechamento transacional

Uma transação congela `tariff_snapshot_id`, `billing_policy_id` e
`closing_insight_run_id`, calcula, persiste faturas e itens, marca recargas como
`billed`, congela os três totais de energia e audita. Fechar de novo devolve
`409` sem alterar nada.

### 6. PDF

`PdfInvoiceRenderer` (fpdf2), renderizado **a partir dos inteiros persistidos**.
`invoice_document_lines` é a declaração pura do conteúdo; o PDF é só a
tipografia dela. O checksum do primeiro render é gravado e todo render posterior
é conferido contra ele.

### 7. Contexto de morador

`POST`/`DELETE /v1/resident-context`. O header `X-Resident-Context` estreita o
escopo para `resident` + uma unidade dentro de `current_scope`, então todo
endpoint de gestor rejeita por construção.

### 8. Web

A constante `ESTIMATED_TARIFF_BRL_PER_KWH = 0.94` **foi removida**: valor devido
só existe em fatura emitida.

A navegação separa dois ritmos, porque acompanhamento diário e decisão mensal
não são a mesma coisa:

```
Operação     → /dashboard  /sessions  /charging-cards
Faturamento  → /closing    /invoices
Configurações→ /settings/data-sources
```

- `/dashboard` acompanha: quatro indicadores (incluindo a reconciliação externa
  contra o agregado do carregador), consumo diário, atenção necessária e um
  bloco compacto de destaques do fechamento que aponta para `/closing`.
- `/closing` é a decisão: readiness, bloqueios, parecer, decisão dos achados
  críticos, aprovar e emitir, faturas emitidas e o consumo por responsável que
  se confere antes de aprovar.
- `/invoices` lista as faturas; `/invoices/{id}` é a fatura com os quatro blocos
  da seção 9 e o botão "Ver como o morador" ao lado do PDF.

### 9. Cartões de recarga

O equipamento autentica um cartão RFID e o relatório do SEMS+ carrega `Card ID` e
`RFID Card Name`. O que não existe no dado do fabricante é a ligação entre cartão,
unidade e cobrança. `charging_cards` é essa ponte, dita uma vez por um gestor e
auditada.

- Na importação, recarga com cartão registrado **se atribui sozinha**, com
  `identity_confidence = confirmed`; só as desconhecidas vão para a revisão.
- `session_assignments.origin` distingue `card` de `manual` para sempre, e a tela
  de Recargas mostra os três estados lado a lado.
- Decisão do gestor **sobrepõe** o cartão.
- **Registrar o serial do próprio carregador é recusado** (`422
  CARD_IS_THE_CHARGER_SERIAL`). Aceitá-lo atribuiria todas as recargas do
  conector a uma unidade por construção, e a fatura afirmaria uma identidade que
  ninguém verificou. É por isso que `57000HPA247L0002` não está registrado e as
  recargas reais caem na fila.

### Endpoints

```
GET    /v1/billing-periods
POST   /v1/billing-periods                                   (idempotente)
GET    /v1/billing-periods/{id}
GET    /v1/billing-periods/{id}/readiness
POST   /v1/billing-periods/{id}/closing-opinion
GET    /v1/billing-periods/{id}/findings
POST   /v1/billing-periods/{id}/findings/{id}/decision
POST   /v1/billing-periods/{id}/close
GET    /v1/charging-cards
POST   /v1/charging-cards                    (recusa o serial do carregador)
DELETE /v1/charging-cards/{id}               (revoga sem apagar o passado)
GET    /v1/invoices
GET    /v1/invoices/{id}                     (fatura + tarifa congelada + faixas)
GET    /v1/invoices/{id}/document             (PDF)
POST   /v1/resident-context
DELETE /v1/resident-context
```

## O que falta

Nada do recorte invoice-first. O que sobrou é P1 ou polimento:

- **Mercado Pago, previsão e segmentação** seguem adiados, documentados com os
  IDs originais no PRD para preservar rastreabilidade com a Sprint 1.
- **Moradores no cenário demonstrativo.** `seed_demo_scenario.py` não cria
  vínculo de morador, então o PDF do pitch mostra "Responsável: Unidade A-101".
  É o fallback correto, mas um nome de pessoa ficaria melhor na gravação.
- **Login de morador** continua fora de escopo. Adicionar depois acrescenta uma
  porta; não muda o modelo.

## Armadilhas deste ambiente — leia antes de rodar qualquer coisa

- **`uv run` está bloqueado por política** dentro da sessão. Use os binários do
  venv direto: `apps/api/.venv/bin/{python,pytest,ruff,mypy,alembic}`. Logo,
  `pnpm check` não roda inteiro; execute etapa por etapa.
- **Instalar pacote Python via Bash está bloqueado.** Se faltar dependência, o
  Paulo roda `uv sync --project apps/api` fora da sessão.
- **Testes de integração precisam rodar da raiz do repo**, não de `apps/api` — o
  `alembic.ini` é resolvido por caminho relativo.
- **O `next dev` só sobe com `WATCHPACK_POLLING=true`.** O projeto vive dentro do
  Dropbox e sem isso o watcher estoura em `EMFILE`. Já está no
  `playwright.config.ts`; se você subir o dev server à mão, lembre.
- **`next build` recusa `AUTH_MODE=fixture`** — guard proposital.
- **Playwright não roda dentro da sessão.** O Chromium falha com
  `bootstrap_check_in ... Permission denied (1100)`. O Paulo roda `pnpm test:web`
  fora. **Não afirme que os testes de UI passam sem que ele confirme.**
- **O PATH do Codex vence o nvm.** `~/.cache/codex/codex-runtimes/.../node` vem
  antes e é v24, enquanto o repo exige `>=22.13.0 <23` com `engineStrict`. Como o
  `pnpm` do nvm é um shim do corepack com `#!/usr/bin/env node`, ele herda o Node
  errado e falha com `ERR_PNPM_UNSUPPORTED_ENGINE` mesmo depois de `nvm use`. A
  saída é `export PATH="$HOME/.nvm/versions/node/v22.19.0/bin:$PATH"` seguido de
  `hash -r`.
- Cuidado com heredocs no Bash: um hook bloqueia padrões de agendamento, e a
  string `at <dígito>` num comentário já dispara falso positivo.

## Como rodar

```bash
cd .../.worktrees/dashboard-operational

apps/api/.venv/bin/alembic -c apps/api/alembic.ini upgrade head
apps/api/.venv/bin/python apps/api/scripts/seed_operational_foundation.py
apps/api/.venv/bin/uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8407

# com a API no ar, em outro terminal: o perfil do gestor nasce na primeira
# requisição autenticada, então o cadastro do condomínio vem depois dela
curl -s localhost:8407/v1/me -H 'Authorization: Bearer fixture-manager-token'
apps/api/.venv/bin/python apps/api/scripts/seed_condominium_registry.py
apps/api/.venv/bin/python apps/api/scripts/seed_real_july.py

# outro terminal
cd apps/web && WATCHPACK_POLLING=true ./node_modules/.bin/next dev --hostname 127.0.0.1 --port 3407
```

`apps/api/.env` e `apps/web/.env` já existem, em modo `fixture`, gitignored.
Token de teste: `Authorization: Bearer fixture-manager-token`.

`seed_real_july.py` importa o julho **real** pelo caminho de importação de
verdade, distribui as recargas entre as unidades (isso é cenário, e o script diz
na justificativa de cada linha) e fecha o período.

`seed_demo_scenario.py` continua existindo e gera um maio **simulado** com
defeitos plantados, útil para mostrar escala e o bloqueio por achado crítico. Os
dois convivem: a procedência viaja com cada recarga.

## Verificação

```bash
apps/api/.venv/bin/ruff check apps/api/app apps/api/tests
apps/api/.venv/bin/mypy app                    # de dentro de apps/api
apps/api/.venv/bin/python -m pytest apps/api/tests -q
apps/api/.venv/bin/alembic -c apps/api/alembic.ini check
apps/api/.venv/bin/python apps/api/scripts/export_openapi.py   # após mudar endpoints
cd packages/api-client && ./node_modules/.bin/openapi-typescript openapi.json -o src/schema.ts
cd apps/web && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/eslint src e2e
```

## Achados que não podem se perder

**A divergência da U102.** O golden reproduz a Sprint 1 ao centavo exceto a taxa
de infraestrutura da unidade com dois veículos: a Sprint 1 cobrava por usuário
RFID (R$ 50,00), o modelo por unidade cobra uma vez (R$ 25,00). Fixado em
`test_two_vehicle_unit_diverges_from_sprint1_only_on_the_fee` e documentado no
PRD 4.4. **Não "conserte" ajustando o teste até passar.**

**O bug de fuso, versão limites de período.** `_period_bounds` montava os limites
do mês em UTC, jogando tudo a partir das 21h do último dia no mês seguinte — o
horário de pico da garagem. Use **sempre** `period_bounds` de `domain/period.py`.

**O bug de fuso, versão persistência.** O SQLite devolve `datetime` **sem fuso**,
e `astimezone` lê um naive como hora local *do servidor*. Numa máquina fora de
São Paulo, isso deslocava toda data impressa — recargas de 31/05 saíam como
01/06 — e, pior, gravava instantes com offsets misturados, o que fazia o filtro
de período **cobrar o conjunto errado de recargas**: a mesma fatura fechava em
R$ 1.067,43 antes e R$ 1.121,70 depois. Corrigido com `UtcDateTime` em
`app/shared/sqlalchemy.py`, que recusa gravar naive e devolve sempre aware. Todo
`DateTime` novo deve usar esse tipo. Um teste que existia *codificava o bug* como
esperado; o contorno foi removido. A regressão está em
`test_invoice_times_survive_the_round_trip_through_the_database` — os testes de
rendering constroem datetimes aware em Python e por isso nunca pegariam isso.

**Procedência derivada da origem.** `provenance_of(source)` deriva o valor, e
`SourceKind.SIMULATED` produz `DataProvenance.SIMULATED` obrigatoriamente. O
guardrail "zero recarga simulada apresentada como real" é garantido na
construção, não por disciplina.

**Achado crítico só sai com decisão registrada.** `readiness` bloqueia o
fechamento enquanto houver `analytical_findings` crítico com `resolved_at` nulo.
Antes não existia caminho de escrita para isso, e nenhum período com defeito
podia fechar. Hoje `POST .../findings/{id}/decision` grava motivo, autor e
instante, e audita. O achado nunca é apagado.

**O `Card ID` do LAB é o serial do carregador.** `57000HPA247L0002` aparece em
todas as 145 sessões de oito meses, e é o `EV Charger SN` do cabeçalho do
relatório. O serial que a documentação antiga citava (`97500NAP25BL0008`) é da
estação. Uma importação real falha com "No charger in organization for serial"
se o carregador certo não estiver cadastrado — `seed_condominium_registry.py`
cria esse equipamento.

**Localizador de linha precisa nomear a tabela.** A tela de recargas mostra
duas tabelas sobre as mesmas recargas — a fila de revisão e o histórico do
período. Um `getByRole("row", { name: /3,50 kWh/ })` sem escopo casa as duas e
o Playwright recusa por ambiguidade. O helper `queue(page)` em
`session-review.spec.ts` existe para isso. O mesmo vale para qualquer tabela
nova: adicionar uma quebra localizadores por texto de telas antigas.

**Só existe um `next dev` por projeto.** O Next 16 trava por diretório, não por
porta: um dev server aceso na 3407 impede o Playwright de subir o dele na 3102,
e a suíte morre com `Process from config.webServer was not able to start`.
Derrube qualquer dev server antes de `pnpm test:web`.

**O e2e roda serial de propósito.** Uma única API e um único SQLite servem a
suíte inteira; com workers paralelos os testes leem as escritas uns dos outros.
Além disso, o preview de importação confere duplicatas **contra o banco**, então
um teste que confirma um lote transforma o mesmo fixture em duplicata para o
próximo. Testes de preview trazem o próprio dia no CSV por isso.

## Contexto do desafio

Sprint 2 entrega em **20/09/2026**. Dois pitches: **3 minutos gravados** para a
GoodWe e **5 minutos presenciais** na FIAP. Mesmo artefato, ênfases diferentes.
Para a GoodWe, dado real do SEMS+ e a reconciliação contra o agregado do próprio
equipamento — eles conseguem conferir. Para a FIAP, a reprodução do exemplo
resolvido da Sprint 1 ao centavo.

A GoodWe não expõe **nenhum campo de identidade** em toda a OpenAPI de EV Charger
(atributos são só `model` e `ratedPower`). Essa lacuna estrutural é o que o
produto preenche, e é o argumento mais forte do pitch. A telemetria, porém,
suporta consulta histórica de `vehConnectStatus`, `currentChargeE`,
`currentChargeTime` e `activePower` — a sessão é derivável da API quando houver
credenciais. O contrato dessa derivação está na seção 7.3 da arquitetura.
