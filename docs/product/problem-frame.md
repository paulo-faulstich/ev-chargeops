# EV ChargeOps - Problem Frame

**Status:** proposta consolidada para revisão

**Data:** 29 de agosto de 2026

## 1. Contexto

Condomínios e edifícios corporativos compartilham infraestrutura elétrica, vagas e carregadores entre pessoas com padrões de uso diferentes. O carregador registra energia e horários, mas esses registros não se tornam automaticamente atribuição por unidade, rateio, cobrança ou orientação operacional.

No LAB FIAP, o SEMS+ apresenta dados reais do carregador GoodWe, porém a API de EV Chargers não será disponibilizada aos grupos e o modelo de referência não oferece OCPP. O equipamento está em operação e não pode receber comandos ou alterações de configuração durante o desafio.

## 2. Problem statement

Síndicos e usuários de infraestruturas compartilhadas de recarga não possuem uma forma integrada e auditável de atribuir sessões a unidades, calcular o consumo individual, aplicar regras de rateio e acompanhar a cobrança. Os dados existem no SEMS+, mas não estão conectados ao contexto condominial nem disponíveis por API para o desafio.

## 3. Evidências disponíveis

> Atualizado em 31/08/2026, após a captura do histórico completo. A versão
> anterior desta seção descrevia uma janela de 30 dias e afirmava que o `Card ID`
> era igual ao serial da estação. Ambos os pontos estão corrigidos abaixo, e a
> conclusão sobre identidade ficou mais forte, não mais fraca.

### 3.1 Onde o dado por sessão realmente está

O histórico por sessão não fica em nenhuma tela da estação. Ele está no
dispositivo: **Station Details → EV Charger → painel `Charging Record`**, que
tem filtro por intervalo e exportação própria.

Isso importa porque as telas de estação são um beco sem saída para este produto:

- `Energy Monitoring` traz séries **da planta**, e a série `Charged Energy` ali é
  a **bateria estacionária**, não o carregador. Em 29/08/2026 o carregador
  entregou 10,50 kWh e essa série marca cerca de 0,5 kWh no mesmo dia.
- `EV Charger Monitoring` traz energia **diária** do carregador — útil para
  ordem de grandeza e reconciliação, inútil para faturar, porque não tem horário
  de início e portanto não resolve faixa tarifária.
- O **Report Center** exporta apenas relatórios de estação e inversor. Os dois
  formatos testados (`Station Statistical Report` e `Station Operation Report`)
  não contêm sessão alguma.

### 3.2 O que o histórico contém

Capturado em 31/08/2026 para o intervalo de 01/01 a 31/08/2026:
**145 sessões, 1.130,66 kWh**, total que confere com o cabeçalho do próprio
relatório. Cada linha traz `Card ID`, `RFID Card Name`, início, fim, duração e
energia carregada.

O volume é estável: entre 10 e 26 sessões por mês, com 130 a 178 kWh mensais
desde março. Julho de 2026 tem 18 sessões e 167,77 kWh.

### 3.3 O campo de identidade existe e não identifica ninguém

Esta é a evidência central do produto, e é mais específica do que se supunha:

- O `Card ID` é **`57000HPA247L0002` em todas as 145 sessões**, ao longo de oito
  meses. Não varia com o usuário, o dia ou o veículo.
- Esse valor é o **`EV Charger SN` declarado no cabeçalho do próprio relatório**:
  o campo que parece identidade é o serial do equipamento. (O serial que a
  documentação anterior citava, `97500NAP25BL0008`, é da estação, não do
  carregador.)
- A coluna **`RFID Card Name` existe e vem vazia** em todas as linhas.

O equipamento **suporta** identificação: o HCA G2 tem leitor RFID, e o relatório
reserva duas colunas para o portador do cartão. O que falta no LAB é o cadastro
de cartões — e, mesmo onde ele existir, nada no dado do fabricante liga um cartão
a uma unidade nem a uma cobrança. Essa ponte é o produto.

### 3.4 Qualidade do dado bruto

Quatro das 145 sessões são conexões sem energia entregue (0,00 kWh), duas delas
com início e fim no mesmo instante. A ingestão as recusa por
`ENERGY_NOT_POSITIVE` e `END_NOT_AFTER_START`, com o registro bruto preservado.
São defeitos reais do portal do fabricante, não da conversão.

### 3.5 Limitações de acesso

- Uma consulta ampla de aproximadamente 13 meses não retornou dados na tela de
  energia, enquanto a janela padrão de 30 dias funcionou. Já o `Charging Record`
  aceitou oito meses de uma vez. A ingestão continua validando lote a lote.
- A mentoria confirmou que a API para EV Chargers não será liberada aos grupos,
  que o fluxo é de consulta (`pull`) e que o acesso oferecido é à planta no SEMS+.
- As capturas usadas estão em [`../../data/sems-plus/`](../../data/sems-plus/),
  cada uma com a tela de origem e as limitações de leitura registradas.

## 4. Usuários e necessidades

### Síndico ou gestor

Quando fecha o período de recarga, precisa transformar dados operacionais em cobranças compreensíveis, localizar inconsistências e explicar o rateio sem manipular planilhas frágeis.

### Morador ou usuário do carregador

Quando recebe uma cobrança, precisa reconhecer as sessões atribuídas à sua unidade, entender energia, tarifa, custos comuns e status do pagamento.

### Operador técnico

Quando uma importação ou sessão apresenta erro, precisa identificar origem, lote, registro bruto e transformação aplicada para corrigir o problema sem alterar silenciosamente o histórico.

## 5. Current state e workarounds

O gestor consulta o SEMS+, exporta ou transcreve registros e complementa manualmente as informações que não existem no portal, principalmente usuário e unidade. Esse processo não fornece deduplicação, trilha de auditoria, aplicação consistente do rateio nem separação explícita entre dados reais e demonstrativos.

## 6. Impactos do problema

- Tempo operacional para consolidar sessões e fechar o período.
- Risco de sessão duplicada, omitida ou atribuída à unidade errada.
- Dificuldade de defender o rateio em caso de contestação.
- Falta de visibilidade sobre anomalias, horários de maior demanda e tendência de consumo.
- Baixa portabilidade: o processo depende da interface e do formato de um fornecedor.

## 7. Hipótese de produto

Se o EV ChargeOps normalizar sessões de diferentes fontes em um modelo canônico, preservar a procedência de cada campo e aplicar regras determinísticas de atribuição, tarifa e rateio, então o gestor poderá fechar cobranças auditáveis e o morador poderá compreender o próprio consumo, mesmo quando a integração original for limitada.

## 8. Outcomes desejados

1. Transformar registros de carregamento em sessões canônicas auditáveis.
2. Aumentar a cobertura de sessões corretamente atribuídas a unidades.
3. Reduzir esforço e incerteza no fechamento mensal.
4. Produzir faturas determinísticas e explicáveis.
5. Sinalizar inconsistências antes da cobrança.
6. Permitir evolução da fonte atual por CSV para APIs ou protocolos futuros sem reescrever o domínio.

## 9. Restrições

- Nenhum comando ou configuração será enviado ao carregador do LAB FIAP.
- A solução não dependerá de credenciais da API GoodWe não fornecidas.
- O HCA G2 usado no desafio não será apresentado como equipamento OCPP.
- Campos reais e simulados serão identificados separadamente.
- A tarifa ANEEL será apresentada como estimativa base, com fonte e data de referência.
- O Mercado Pago será usado apenas em ambiente sandbox.

## 10. Princípios de produto

- **Auditável por padrão:** todo valor relevante aponta para sua origem e regra de cálculo.
- **Verdade antes de automação:** limitações da fonte são expostas, não mascaradas.
- **Fornecedor substituível:** fontes externas entram por contratos estáveis.
- **IA explicável:** insights mostram dados e regras que sustentam a conclusão.
- **Menor privilégio:** a demonstração é somente leitura em relação ao equipamento real.
- **Evolução incremental:** monólito modular primeiro; separação em serviços somente quando houver necessidade comprovada.

## 11. Non-goals

- Controlar remotamente potência, início ou encerramento de recargas.
- Automatizar a interface web do SEMS+ como fonte permanente.
- Processar pagamentos reais.
- Representar dados simulados como telemetria real.
- Construir uma rede pública de eletropostos ou um sistema completo de reservas.
- Treinar modelos complexos com o pequeno histórico disponível.

## 12. Premissas e validação

| Premissa | Como será validada |
|---|---|
| O histórico pode ser obtido em arquivo estruturado | Importar um arquivo exportado do SEMS+; enquanto o formato não estiver disponível, usar um fixture fiel aos campos observados |
| Janelas mensais são suficientes para o fechamento | Demonstrar importação, deduplicação e fechamento de um período mensal |
| Sessões sem identidade podem ser tratadas sem fingir certeza | Exigir atribuição explícita e registrar `identityConfidence` |
| A tarifa pública pode sustentar uma estimativa transparente | Armazenar fonte, vigência e componentes utilizados no cálculo |
| Uma integração transacional aumenta a validação do produto | Criar e acompanhar uma cobrança Pix exclusivamente no sandbox |

## 13. Relação com a Sprint 1

Este problem frame não substitui a pesquisa entregue. Ele transforma a pesquisa e as restrições descobertas após a entrega em uma definição operacional para a próxima etapa.
