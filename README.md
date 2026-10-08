# EV ChargeOps

Gestão de recarga compartilhada em condomínios: da exportação do carregador à fatura por unidade, com atribuição auditável, análise de anomalias e rastreabilidade dos valores.

**Enterprise Challenge 2026 · GoodWe + FIAP · Sprint 2 · Fase 6**

| Integrante | RM | Grupo da Sprint 2 |
|---|---|---|
| Paulo Roberto Faulstich Rego | 572292 | 17 |

## Entrega e documentação por sprint

O mesmo repositório reúne a pesquisa e sua implementação. A documentação histórica fica separada da descrição do produto atual.

| Documento | Conteúdo |
|---|---|
| [Sprint 1](docs/sprints/sprint-01/README.md) | Pesquisa, arquitetura e proposta original, preservadas a partir do commit publicado em junho |
| [Sprint 2](docs/sprints/sprint-02/README.md) | Requisitos, implementação, rubrica e orientação de entrega |
| [Mudanças em relação à proposta](docs/sprints/sprint-02/desvios-e-decisoes.md) | O que mudou, por quê e o que ficou para evolução futura |
| [Demonstração e evidências](docs/sprints/sprint-02/evidencias.md) | Vídeo da apresentação, reprodução do fechamento e resultados dos testes |
| [Arquivo TXT de entrega](docs/entregas/sprint-02.txt) | Identificação e link deste repositório |
| [Uso de IA no desenvolvimento](docs/uso_ia.md) | Apoio de ferramentas de IA e responsabilidade do autor |

**Vídeo da apresentação:** [EV ChargeOps · Enterprise Challenge · 2026 GoodWe + FIAP](https://youtu.be/B1YzQmRzsfg) — 3min54s, não listado.

## Solução implementada

```text
CSV exportado do SEMS+
  → validação e importação com procedência
  → atribuição por cartão cadastrado ou decisão do gestor
  → tarifa e política de rateio versionadas
  → parecer analítico e revisão dos achados
  → aprovação do fechamento
  → faturas por unidade e PDF auditável
```

- **Importação:** prévia linha a linha, rejeição de registros inválidos, preservação do dado bruto e proteção contra duplicação em reimportações.
- **Identificação:** cartão cadastrado atribui a recarga à unidade; identidade desconhecida entra na fila para decisão justificada. O serial do carregador não é aceito como cartão de morador.
- **Rateio:** energia por faixa tarifária, taxa fixa por unidade ativa e perdas proporcionais ao valor da energia. Arredondamento por recarga e valores persistidos em centavos.
- **Análise:** regras de integridade e detecção estatística de consumo fora do padrão, executadas antes da emissão. Achados críticos não resolvidos impedem o fechamento.
- **Faturas:** regras congeladas na emissão, composição verificável, vínculo com os registros de origem e PDF. O gestor pode consultar a visão restrita de uma unidade, com auditoria.
- **Reconciliação:** a conferência interna protege o fechamento; a diferença em relação ao agregado do carregador é exibida e não é distribuída silenciosamente aos moradores.

A implementação usa Next.js/TypeScript na interface e FastAPI/Python no backend. SQLite atende à demonstração local; o modo remoto possui adapters para PostgreSQL, Auth e Storage do Supabase. [Arquitetura técnica](docs/technical/ev-chargeops-architecture.md).

## Papel da análise de dados e limites da IA

O parecer `closing-opinion/1.0.0` combina regras determinísticas (intervalo inválido, energia não positiva, potência incompatível, sobreposição e recarga sem unidade) com detecção de outliers por z-score modificado sobre a mediana e a MAD. Com menos de cinco recargas por unidade, a análise estatística informa amostra insuficiente. Não há modelo de linguagem gerando o parecer, nem modelo treinado de previsão ou segmentação.

Os achados críticos das regras de integridade bloqueiam a emissão até uma decisão registrada; o desvio estatístico de energia gera aviso para revisão. O motor financeiro permanece determinístico. Previsão de consumo e clustering, propostos na Sprint 1, foram adiados; a justificativa e os limites desse recorte estão no [registro de desvios](docs/sprints/sprint-02/desvios-e-decisoes.md).

## Dados reais e cenário demonstrativo

As recargas vêm do GoodWe HCA G2 do LAB FIAP Eco Smart Home, exportadas pelo SEMS+. O arquivo contém **145 registros e 1.130,66 kWh**; isso inclui registros que a validação rejeita. A importação integral classifica 141 registros como válidos e quatro como inválidos.

Energia, horários e registros de origem são observados. Condomínio, unidades, moradores, cartão de exemplo, tarifas e associação entre recargas e unidades são **cenário demonstrativo**. O campo de cartão da captura repete o serial do equipamento e não identifica o morador. [Procedência dos dados](data/sems-plus/README.md).

Não existe integração ativa com a API GoodWe, previsão de consumo, clustering, pagamento Pix ou login independente de morador. O projeto não envia comandos ao carregador. O cadastro de cartões é implementado, mas não foi validado com cartões reais do laboratório.

## Executar localmente

Requisitos: Node.js `>=22.13.0 <23`, pnpm `11.19.0` e Python 3.12+ com `uv`. O modo local dispensa conta Supabase. Execute os comandos abaixo a partir da raiz do repositório, em um clone novo ou ambiente local de demonstração.

```bash
pnpm install
uv sync --project apps/api
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
pnpm db:upgrade
uv run --project apps/api python apps/api/scripts/seed_operational_foundation.py
```

Os comandos `cp` são de preparação inicial: em uma instalação existente, preserve os arquivos de ambiente e confira a configuração antes de usá-los. O backend de exemplo usa SQLite e `AUTH_MODE=fixture`.

Em um terminal, inicie a API:

```bash
pnpm dev:api
```

Em outro terminal, provisione o gestor local, cadastre o cenário e reproduza julho:

```bash
curl --fail --silent --output /dev/null \
  -H 'Authorization: Bearer fixture-manager-token' \
  http://127.0.0.1:8407/v1/me
uv run --project apps/api python apps/api/scripts/seed_condominium_registry.py
uv run --project apps/api python apps/api/scripts/seed_real_july.py
```

O script importa recargas reais, faz atribuições explicitamente demonstrativas e fecha julho/2026. Em banco novo, o resultado esperado é **17 recargas válidas, 167,77 kWh, quatro faturas e R$ 270,12**. Se o período já estiver fechado, as faturas não são recriadas. Não use esse seed como operação de produção.

Inicie a interface:

```bash
AUTH_MODE=fixture pnpm dev:web
```

Abra `http://localhost:3407`. A autenticação fixture identifica o gestor local automaticamente. Ela só é permitida em desenvolvimento/teste. A API usa `http://127.0.0.1:8407`.

| Rota | O que conferir |
|---|---|
| `/dashboard` | Consumo e acompanhamento operacional |
| `/settings/data-sources` | Prévia da importação e erros por linha |
| `/sessions` | Recargas, procedência e atribuição justificada |
| `/charging-cards` | Cartões vinculados às unidades |
| `/closing` | Julho/2026, parecer e fechamento |
| `/invoices` | Quatro faturas de julho e seus PDFs |

O arquivo `ev_chargeops_local.db` contém o estado local e não é versionado. As migrações recriam o schema; os seeds recriam somente o cenário previsto. Decisões e dados adicionais inseridos manualmente não são recuperados apenas pelas migrações.

Para executar o modo remoto, consulte os guias da [API](apps/api/README.md) e da [interface](apps/web/README.md). Esse modo requer configuração própria do Supabase e não é necessário para avaliar o protótipo local.

## Verificação

Com o banco local migrado, dependências instaladas e servidores de desenvolvimento encerrados:

```bash
pnpm --dir apps/web exec playwright install chromium --with-deps
AUTH_MODE=supabase pnpm check
```

O override `AUTH_MODE=supabase` permite validar o build de produção, que bloqueia autenticação fixture. Os testes de navegador configuram separadamente seu modo fixture e seu banco descartável. O gate também compara o contrato gerado com o commit atual; alterações de contrato ainda não commitadas são apontadas como diferença.

Resultados e limites das verificações estão nas [evidências da Sprint 2](docs/sprints/sprint-02/evidencias.md).

## Estrutura do repositório

```text
apps/api/                 API, domínio, persistência, migrações e testes Python
apps/web/                 Interface Next.js e testes de navegador
packages/api-client/      Contrato OpenAPI e cliente TypeScript
data/exemplos/            Dados simulados usados na proposta original
data/sems-plus/           Capturas observadas e sua procedência
docs/sprints/sprint-01/   Arquivo histórico da primeira entrega
docs/sprints/sprint-02/   Entrega atual, requisitos, decisões e evidências
docs/entregas/            Arquivos TXT de cada sprint
docs/product/             Definição do produto e métricas
docs/technical/           Arquitetura da implementação
docs/decisions/           Histórico de decisões de arquitetura
```
