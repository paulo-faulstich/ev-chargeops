# `2026-08-31-ev-charger-energia-diaria.csv`

**Capturado em:** 31 de agosto de 2026
**Origem:** SEMS+ → Station Details → aba **EV Charger Monitoring**, seletor
`EV Charger`, granularidade `Week`, semanas ISO 20/2026 a 35/2026
**Estação:** LAB FIAP Eco Smart Home

## O que é

Energia diária entregue **pelo carregador de veículo elétrico** (série
`Charged Energy` daquela aba), de 11/05/2026 a 30/08/2026 — 112 dias.

| Mês | Energia | Dias com recarga |
|---|---:|---:|
| 05/2026 (parcial, a partir do dia 11) | 106,27 kWh | 14 |
| 06/2026 | 129,45 kWh | 20 |
| 07/2026 | 161,45 kWh | 20 |
| 08/2026 (até o dia 30) | 125,16 kWh | 24 |
| **Total** | **522,33 kWh** | **78** |

## Não confundir com a aba Energy Monitoring

A aba `Energy Monitoring` da mesma tela também tem uma série chamada
`Charged Energy`, mas ali ela é a **bateria estacionária** da planta, não o
carregador. As duas séries têm ordens de grandeza diferentes e não devem ser
somadas nem substituídas uma pela outra.

Verificação rápida: em 29/08/2026 o histórico de recarga registra 7,00 + 3,50 =
10,50 kWh de recarga, e o `Charged Energy` da aba `Energy Monitoring` naquele dia
é de cerca de 0,5 kWh.

## Limitação da captura — leia antes de usar

**Estes valores foram lidos de capturas de tela, não exportados.** O SEMS+ não
oferecia exportação nessa aba no momento da captura.

A coluna `reading_method` distingue as duas situações:

- `tooltip` (12 registros): valor exato, lido do tooltip do gráfico.
- `chart` (100 registros): valor **estimado** pela altura da barra contra o eixo.
  A precisão é da ordem de ±0,2 kWh, e dias de valor muito baixo podem estar
  registrados como zero.

Por isso este arquivo serve para **ordem de grandeza, sazonalidade e
reconciliação aproximada**, e não como fonte de cobrança. Nenhuma fatura deve ser
emitida a partir dele sem que a limitação esteja declarada na tela.

## O que este arquivo permite e o que não permite

**Permite** alimentar `charger_energy_readings` com o agregado diário **real** do
equipamento, que é o lado externo da reconciliação dupla. Hoje esse lado é
gerado pelo `seed_demo_scenario.py`; com este arquivo ele passa a ser medição.

**Não permite** emitir faturas. Um agregado diário não tem horário de início
(necessário para resolver a faixa tarifária), duração, porta nem `Card ID`. Para
sessões é preciso o **histórico de recarga**, que fica em outra tela e, segundo o
problem frame, oferece exportação.

## Regra da pasta

Nada aqui é editado depois de capturado. Correções e normalizações acontecem no
adapter de ingestão, nunca no arquivo original.
