# `2026-08-31-ev-charger-sessoes.csv`

**Capturado em:** 31 de agosto de 2026
**Origem:** SEMS+ → Station Details → dispositivo **EV Charger** → painel
**Charging Record**, exportado em PDF e convertido sem alteração de valores
**Intervalo pedido:** 01/01/2026 00:00 a 31/08/2026 23:59

## O que é

O histórico de recarga do carregador, sessão por sessão. **145 sessões,
1.130,66 kWh** — total que confere exatamente com o `Total Energy Charged`
declarado no cabeçalho do próprio PDF.

| Mês | Sessões | Energia |
|---|---:|---:|
| 01/2026 | 10 | 85,33 kWh |
| 02/2026 | 15 | 111,04 kWh |
| 03/2026 | 26 | 177,78 kWh |
| 04/2026 | 21 | 153,52 kWh |
| 05/2026 | 20 | 166,78 kWh |
| 06/2026 | 19 | 137,76 kWh |
| 07/2026 | 18 | 167,77 kWh |
| 08/2026 | 16 | 130,68 kWh |
| **Total** | **145** | **1.130,66 kWh** |

## Formato

Convertido para o mesmo cabeçalho que o adapter de ingestão já consome:

```
Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
31/05/2026 19:10:00,01/06/2026 00:59:00,14.29,1,57000HPA247L0002,57000HPA247L0002
```

Duas conversões foram aplicadas ao ler o PDF, e nenhum valor foi alterado:

- **Datas.** O PDF traz `MM/DD/YYYY`; o adapter espera `DD/MM/YYYY`.
- **Segundos.** O PDF tem precisão de minuto. Os segundos foram preenchidos com
  `00`. A tela do SEMS+ mostra segundos (ex.: `28/07/2026 17:13:14`), então uma
  captura futura pela tela é mais precisa que esta.

A coluna `Charging Port` não existe no PDF. Todas as sessões visíveis na tela têm
porta `1`, e o valor foi preenchido com `1`.

## O Card ID não identifica ninguém

O `Card ID` é **57000HPA247L0002** em todas as 145 sessões, de 01/01 a 30/08. É o
mesmo valor do `EV Charger SN` declarado no cabeçalho do relatório: o campo que
parece identidade é o serial do próprio equipamento.

A coluna `RFID Card Name` existe no relatório e vem **vazia** em todas as linhas.

É por isso que a atribuição do EV ChargeOps tem a unidade como alvo, e não o
usuário: não existe, no dado do fabricante, nada que distinga quem carregou.

## Quatro linhas que a ingestão recusa — e deve recusar

Ao passar pelo importador real, 141 das 145 são aceitas. As quatro recusadas são
eventos reais de qualidade de dado, não erro de conversão:

| Registro | Motivo |
|---|---|
| 06/03/2026 19:28, 0,00 kWh | `END_NOT_AFTER_START` |
| 17/04/2026 07:10, 0,00 kWh | `ENERGY_NOT_POSITIVE` |
| 14/06/2026 20:11, 0,00 kWh | `ENERGY_NOT_POSITIVE` |
| 28/07/2026 17:13, 0,00 kWh | `END_NOT_AFTER_START` |

Todas são conexões sem energia entregue. As de `END_NOT_AFTER_START` têm início
e fim no mesmo minuto por causa da precisão do PDF; na tela duram alguns segundos
e continuam com 0,00 kWh, ou seja, seriam recusadas de qualquer forma.

## Regra da pasta

Nada aqui é editado depois de capturado. Correções e normalizações acontecem no
adapter de ingestão, nunca no arquivo original.
