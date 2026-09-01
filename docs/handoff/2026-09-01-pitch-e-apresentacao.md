# EV ChargeOps — prompt de continuação: pitch de 3 minutos e apresentação

> Escrito em 01/09/2026. O produto está construído e rodando. **Esta etapa não é
> de código: é de narrativa.** O prompt anterior
> ([`NEXT_AI_PROMPT.md`](NEXT_AI_PROMPT.md)) cobria a implementação e está
> desatualizado em números; use este.

Você vai ajudar a escrever **o roteiro do pitch de 3 minutos** (gravado, para a
GoodWe) e **a apresentação**. Responda em português.

---

## 1. Regras que não se negociam

**Nunca apresente dado simulado como real.** Este produto inteiro se vende como
auditável; uma frase inflada no pitch destrói exatamente o que ele afirma ser. A
seção 4 diz linha a linha o que é real e o que é cenário.

**Não invente número.** Todos os números citáveis estão na seção 3. Se precisar
de um que não está lá, peça — não estime.

**Não afirme capacidade que não existe.** A seção 7 lista o que ficou de fora, e
por quê. Dizer "temos previsão de consumo" seria mentira verificável em 30
segundos de demo.

**Não redesenhe o produto.** As decisões da seção 6 foram tomadas com motivo
registrado. Se alguma parecer errada, aponte — mas não reescreva o pitch em cima
de um produto diferente do que existe.

---

## 2. O que é o EV ChargeOps, em uma frase

Uma plataforma que transforma sessões de recarga de veículos elétricos em
**faturas condominiais auditáveis** — da telemetria do carregador GoodWe até o
PDF que o morador recebe, com cada centavo rastreável até a recarga que o gerou.

Contexto: Enterprise Challenge 2026 GoodWe + FIAP, Sprint 2 (entrega 20/09/2026).
O laboratório é o **LAB FIAP Eco Smart Home**, com um carregador GoodWe HCA G2.

---

## 3. Números reais — todos verificados, todos citáveis

### A base de dados

| Fato | Valor |
|---|---|
| Histórico capturado do SEMS+ | **145 sessões, 1.130,66 kWh**, 01/01 a 31/08/2026 |
| Confere com | o cabeçalho do próprio relatório da GoodWe |
| Volume mensal | 10 a 26 sessões; 130 a 178 kWh desde março |
| Julho/2026 | **18 sessões, 167,77 kWh** |
| Recusadas pela ingestão | **4 das 145** (energia zero ou fim antes do início) — defeitos reais do portal do fabricante, não da conversão |

### O fechamento demonstrado (julho/2026)

| Fato | Valor |
|---|---|
| Recargas importadas e válidas | **17 de 18** |
| Faturas emitidas | **4** |
| Total faturado | **R$ 270,12** |
| Fatura da unidade A-101 | R$ 104,83 — 9 recargas, 83,290 kWh |
| Composição da A-101 | R$ 76,76 energia + R$ 25,00 taxa + R$ 3,07 perdas |

### A tarifa

| Faixa | Horário | Preço |
|---|---|---|
| Ponta | das 18h às 21h | R$ 1,25/kWh |
| Intermediário | das 6h às 18h | R$ 0,95/kWh |
| Fora de ponta | das 21h às 6h | R$ 0,78/kWh |

Mais: taxa de infraestrutura **R$ 25,00 por unidade ativa** e perdas técnicas de
**4% da energia**, rateadas na proporção do consumo.

### Os seriais

- Carregador (EV Charger SN): **`57000HPA247L0002`**
- Estação: `97500NAP25BL0008` — **não confunda**; documentação antiga citava o
  errado

---

## 4. Real vs. cenário — a linha que não pode ser cruzada

**REAL** (medido pelo equipamento da FIAP, exportado do SEMS+):
- energia, horários, duração de todas as 145 sessões
- o serial do carregador
- os defeitos de dado nas 4 linhas recusadas

**CENÁRIO** (o condomínio não existe; o LAB é um laboratório):
- as unidades A-101 a A-104 e a loja LJ-01
- os moradores (Ana Souza, Bruno Lima, Carla Mendes, Diego Ferreira)
- a tarifa e a política de rateio
- **a atribuição de cada recarga a uma unidade**

A fatura carimba isso: ela imprime `Procedência: dados reais` quando as recargas
são medidas. A distribuição por unidade é declarada como demonstração na
justificativa de cada atribuição. Se o pitch mostrar a tela, o carimbo aparece —
então não contradiga o que está na imagem.

---

## 5. A descoberta que sustenta o produto — use isto como espinha do pitch

Este é o melhor material narrativo que existe no projeto, e é verdade
verificável.

A Sprint 1 assumiu que o carregador identificaria o morador por cartão RFID. O
acesso real ao SEMS+ derrubou a premissa:

- O campo `Card ID` traz **`57000HPA247L0002` nas 145 sessões**, ao longo de oito
  meses.
- Esse valor é o **serial do próprio carregador**.
- A coluna `RFID Card Name` **existe e vem vazia** em todas as linhas.

Ou seja: **o campo que parece identidade é o equipamento se nomeando.** O HCA G2
*tem* leitor RFID e o relatório *reserva* as colunas — o que não existe é o
cadastro. E mesmo se existisse, o dado do fabricante ligaria um cartão a um
cartão: nada ali diz que aquele número é do apartamento 101, nem quem paga.

**Essa ponte é o produto.** A administração declara uma vez `RFID-A101-0001 →
unidade A-101`, e toda recarga seguinte com aquele cartão se atribui sozinha,
com origem `card`. Sem cartão conhecido, a recarga vai para a fila de revisão e o
síndico atribui com justificativa, com origem `manual`. As duas origens ficam
distinguíveis para auditoria — para sempre, inclusive depois de revogar o cartão.

### Como funciona o RFID, se perguntarem

O cartão é um chip passivo que guarda **um número** (UID), nada mais. No toque: o
leitor lê o UID → o carregador confere contra uma lista branca gravada nele ou
consulta a nuvem → autorizado, libera a trava e entrega energia → no fim, grava a
sessão carimbada com aquele UID. Esse carimbo é o que chega na coluna `Card ID`.

Dois limites honestos, que valem admitir antes de serem apontados: **o cartão
identifica o cartão, não a pessoa** (emprestou, a recarga vai para o dono do
cartão), e **MIFARE Classic é clonável** — implantação real pede cartão
criptografado, ou aceitar que o cartão é conveniência e a conferência de verdade
é o fechamento auditável.

---

## 6. Decisões de produto — respostas prontas para as perguntas prováveis

| Decisão | Por quê |
|---|---|
| **A unidade é o alvo da atribuição**, não a pessoa | O dado do fabricante não distingue quem carregou. O morador aparece pelo vínculo ativo; sem vínculo, a fatura mostra o nome da unidade. É o fallback desenhado, não uma lacuna |
| **A visão do morador é a própria fatura**, via impersonate | Um artefato serve os dois papéis, com autorização como filtro. Sem segunda tela, sem troca de login no meio do pitch |
| **Arredondamento uma vez por recarga** | Cada linha impressa é conferível, e a soma bate exatamente com o subtotal |
| **A faixa é a do horário de início** | O medidor dá o total da recarga, não uma curva. Dividir energia entre faixas seria inventar dado |
| **Reconciliação dupla** | A interna (faturas × recargas) **bloqueia** o fechamento. A externa (recargas × total do carregador) **avisa** e nunca é absorvida em fatura de ninguém |
| **A IA atua antes da fatura e pode bloquear a emissão** | É o parecer de fechamento: detecta intervalo inválido, energia não positiva, potência acima do nominal, duplicata suspeita, consumo fora do padrão e divergência com o agregado. Achado crítico exige decisão registrada com motivo antes de fechar |
| **Pagamento (Pix/Mercado Pago) fora do escopo** | O playbook descreve a cobrança como repasse na taxa condominial, não pagamento avulso. A fatura é o entregável |

---

## 7. O que NÃO existe — não prometa

- **Previsão de consumo** e **segmentação de perfis**: empurradas para P1.
- **Login de morador**: o morador é alcançado por impersonate, não por conta própria.
- **Integração por API com a GoodWe**: a API de EV Chargers não foi disponibilizada
  ao desafio. A entrada é o CSV exportado do SEMS+.
- **OCPP**: o HCA G2 do LAB não será apresentado como equipamento OCPP.
- **Síntese NLP de insights**: o briefing da GoodWe cita isso para a trilha EV
  ChargeOps e **não foi implementado**. O parecer usa regras determinísticas e
  estatística robusta (z-score modificado sobre MAD), não linguagem natural
  gerada. Se for citar IA, cite o que existe.
- Nenhum comando foi enviado ao carregador do LAB, por restrição explícita do desafio.

---

## 8. Como a GoodWe avalia — os eixos, nas palavras deles

Do deck oficial do challenge, slide "O Que Esperamos de Vocês":

1. **Arquitetura Funcional** — lógica clara de entradas e saídas de dados (data flow)
2. **Papel da IA Integrada** — IA justificada como motor lógico, não penduricalho de interface
3. **Aderência ao Contexto** — solução sob medida para o ambiente (comercial vs. condominial), usando o ecossistema GoodWe/FIAP
4. **Visão de Produto Real** — para quem serve? qual problema regulatório ou operacional resolve hoje?

E a frase que deve governar o roteiro inteiro:

> **"O código é apenas o veículo; a avaliação foca no raciocínio arquitetônico, de negócios e de gestão de dados."**

O deck também define a trilha EV ChargeOps como *"histórico operacional, gestão
compartilhada, inteligência de dados"*, com a IA em *"análise de padrões de
consumo do morador"*.

**Confirme os pesos de cada eixo com o Paulo** — ele mencionou uma distribuição
45/15/15/15/10, que não está registrada nos documentos do repositório. A rubrica
que está nos PDFs (`material-apoio/enunciados/briefing-portal-fiap-sprints.pdf`) é a da **Sprint 1**, de 0 a 10, e não vale
para esta etapa.

---

## 9. Sugestão de espinha para os 3 minutos

Isto é ponto de partida, não roteiro fechado. Ajuste com o Paulo.

| Tempo | Bloco | Conteúdo |
|---|---|---|
| 0:00–0:25 | **O problema, concreto** | O condomínio tem um carregador e uma conta de luz única. O carregador mede energia; ninguém sabe de quem ela foi |
| 0:25–1:00 | **A descoberta** | 145 sessões reais, oito meses, e o campo de identidade repetindo o serial do equipamento. A premissa da Sprint 1 caiu no campo |
| 1:00–2:00 | **A solução, demonstrada** | Importar → atribuir (cartão ou decisão registrada) → parecer da IA que pode bloquear → fechar → fatura que se explica linha a linha |
| 2:00–2:35 | **A prova** | Julho real fechado: 17 recargas, 4 faturas, R$ 270,12, energia batendo com os 167,77 kWh do relatório da GoodWe. E o PDF |
| 2:35–3:00 | **Por que importa** | Repasse na taxa condominial deixa de ser rateio às cegas e vira documento auditável. E o caminho: cadastro de cartões faz a atribuição virar automática |

**O momento "uau" mais forte** é a auditabilidade da fatura: clicar em uma
recarga e chegar até a linha do relatório da GoodWe que a originou. Não é um
gráfico bonito — é a promessa do produto sendo cumprida na tela.

---

## 10. Estado do repositório

**Diretório:** `/Users/paulofaulstich/Dropbox/Workspace/__claude/personal/education/fiap/challenges/good-we/ev-chargeops`, branch `main`.

- **Há trabalho não commitado** (~28 arquivos, uma rodada de humanização de
  vocabulário). Rode `git status` antes de qualquer coisa e **não commite sem
  pedir**.
- **328 testes Python** passando; ruff, mypy, `tsc` e `eslint` limpos.
- **Playwright: 3 specs foram editadas e não foram verificadas** — o e2e precisa
  rodar (`pnpm test:web`), e **com os servidores de desenvolvimento derrubados**,
  senão o Next 16 trava por diretório de projeto.
- Existe uma conversa pendente sobre remover o worktree `.worktrees/dashboard-operational`.

### Rodar a demo

```bash
pnpm db:upgrade
uv run --project apps/api python apps/api/scripts/seed_operational_foundation.py
pnpm dev:api          # 8407
# uma requisição autenticada provisiona o gestor fixture
uv run --project apps/api python apps/api/scripts/seed_condominium_registry.py
uv run --project apps/api python apps/api/scripts/seed_real_july.py
pnpm dev:web          # 3407
```

O fechamento de julho é reprodutível: sai **sempre** R$ 270,12 e as mesmas 4
faturas.

> Aviso de ambiente: a pasta está sincronizada pelo Dropbox e o watcher do
> Turbopack não detecta mudanças de forma confiável ali. Se editar código, **reinicie
> o dev server** — não confie em hot reload.

### Leitura, nesta ordem

1. [`../product/problem-frame.md`](../product/problem-frame.md) — seção 3, as evidências reais
2. [`../product/prd.md`](../product/prd.md) — seção 0, o que mudou na v0.4 e por quê
3. [`../../data/sems-plus/2026-08-31-ev-charger-sessoes.md`](../../data/sems-plus/2026-08-31-ev-charger-sessoes.md) — a procedência da captura
4. [`../product/success-metrics.md`](../product/success-metrics.md) — seção 7, alinhamento com a avaliação

---

## 11. Como trabalhar com o Paulo

Ele é direto e detecta afirmação inflada rápido. Vale:

- **Separar sempre** o que está pronto, o que é cenário, o que está pendente e o
  que está bloqueado.
- **Recomendar**, não apresentar cardápio de opções. Se houver escolha real de
  voz ou ênfase, faça a chamada e explique o porquê em uma linha.
- **Não commitar sem pedir.** Isso é decisão explícita dele.
- Quando ele apontar um erro, corrigir e seguir — sem cerimônia.
