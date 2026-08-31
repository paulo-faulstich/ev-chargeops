# Capturas reais do SEMS+

Esta pasta guarda dados **reais** exportados do SEMS+ (`semsplus.goodwe.com`) para a
estação `LAB FIAP Eco Smart Home`. É diferente de [`../exemplos/`](../exemplos/), que
contém o conjunto **fabricado** da Sprint 1.

Regra: nada aqui é editado depois de capturado. Correções e normalizações acontecem no
adapter de ingestão, nunca no arquivo original. Cada captura registra data, tela de
origem e limitações conhecidas.

## `2026-08-30-estacao-energia-agregada.csv`

**Capturado em:** 30 de agosto de 2026
**Origem:** SEMS+ → Station Details → área de energia da estação
**Checksum (SHA-256):** `86c68dd4378bf374c900e9359b41d0732131c7cde05ccc6df1d6de60f4c7c6b2`

### O que é

Agregados de energia da **planta** (geração solar, exportação, importação e consumo do
site), em quatro granularidades misturadas no mesmo arquivo:

| `Period_Type` | Linhas | Cobertura |
|---|---|---|
| `Year` | 1 | 2026 |
| `Month` | 8 | 01/2026 a 08/2026 |
| `Week` | 21 | 15/2026 a 35/2026 |
| `Day` | 31 | 30/07/2026 a 29/08/2026 |

Colunas: `Period_Type`, `Period_Value`, `Energy_Generation_kWh`,
`Grid_Export_Energy_kWh`, `To_Grid_Revenue`, `Import_Energy_kWh`,
`Energy_Consumption_kWh`.

### O que NÃO é

**Não é dado de recarga.** Não há início, fim, duração, porta, `Card ID` nem energia por
sessão. Nenhuma linha deste arquivo pode virar `ChargingSession`, ser atribuída a uma
unidade ou entrar em uma fatura.

O `Energy_Consumption_kWh` é o consumo medido da planta, **não** o consumo do carregador.
Em agosto de 2026 ele soma 57,6 kWh, enquanto a recarga observada no mesmo período passa
de 130 kWh — ou seja, o carregador não está dentro dessa medição. Apresentar essa coluna
como consumo de recarga violaria o guardrail "zero sessão simulada apresentada como real"
e invalidaria a métrica M-05 de reconciliação.

A telemetria de recarga vem de outra tela: Station Details → aba
`EV Charger Monitoring`, com o seletor `EV Charger` (série `Charged Energy` por dia).

### Uso previsto

Contexto solar. Cruzar a geração diária com o horário das recargas permite recomendar
janelas de carregamento cobertas por geração própria em vez de importação da rede, e
separar autoconsumo de exportação no custo real do condomínio. Entra como fonte
secundária, sempre rotulada, e nunca se mistura à reconciliação de recargas.

### Divergências conhecidas nos próprios agregados

Estas inconsistências vêm do portal, não da captura. Elas são evidência legítima para o
parecer explicável da IA sobre por que o fechamento precisa de reconciliação em vez de
confiar cegamente no fornecedor.

- `Month 08/2026` informa 148,1 kWh de geração, mas a soma das 29 linhas `Day` de agosto
  dá 150,2 kWh.
- `Year 2026` informa 2080,0 kWh, enquanto as 8 linhas `Month` somam 2086,4 kWh.
- `Month 02/2026` tem exportação (780,81 kWh) maior que a geração (578,2 kWh).
- Os dias 10, 11 e 12/08/2026 têm valores idênticos em todas as colunas.
- As granularidades não têm interseção completa: 21 semanas, 8 meses e 31 dias.

Ao derivar qualquer número deste arquivo, declare explicitamente qual granularidade foi
usada.
