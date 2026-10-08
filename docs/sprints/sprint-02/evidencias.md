# Evidências da Sprint 2

## Apresentação online

[**EV ChargeOps · Enterprise Challenge · 2026 GoodWe + FIAP**](https://youtu.be/B1YzQmRzsfg)

Vídeo enviado em **02/09/2026**, com duração de **3min54s** e visibilidade **não listada**, conforme consulta ao YouTube Studio em 08/10/2026. A descrição identifica o pitch da Sprint 02; o autor confirmou o link e seu reaproveitamento para esta entrega. A autorização para realizar somente a apresentação online foi informada pelo autor.

## Reprodução do protótipo

O [README principal](../../../README.md#executar-localmente) apresenta a sequência para preparar um banco local novo, iniciar a API, cadastrar o cenário, importar as recargas e abrir a interface.

| Verificação | Resultado esperado do cenário de julho/2026 |
|---|---|
| Arquivo mensal | 18 registros, dos quais 17 são válidos |
| Energia faturada | 167,77 kWh |
| Faturas | 4, uma por unidade ativa |
| Total | R$ 270,12 |
| Exemplo A-101 | 9 recargas, 83,290 kWh, R$ 104,83 |

A atribuição às unidades e as tarifas são demonstrativas. Energia e horários vêm da exportação observada do SEMS+. A base integral contém 145 registros, incluindo quatro inválidos; quantidade de registros de origem não equivale a quantidade de recargas faturáveis.

## Verificação automatizada

A execução de 08/10/2026 aprovou 328 testes Python e 19 testes do cliente da API. Ruff, mypy, ESLint, tipos TypeScript, build Webpack com `AUTH_MODE=supabase`, migrações em banco temporário e contrato OpenAPI também foram verificados.

A revisão identificou três expectativas desatualizadas nos testes de navegador: duas buscavam o título anterior do login e uma dependia implicitamente do mês de agosto. Após os ajustes, os **44 testes de navegador passaram**, em 20,3 segundos. Os testes de autenticação verificam o redirecionamento e os campos de acesso; o teste de período fixa outubro como data e verifica a seleção de agosto entre os períodos disponíveis.

## Reprodução verificada em 08/10/2026

O roteiro foi executado em SQLite temporário criado do zero, sem usar o banco local existente ou o Supabase. Foram criadas quatro unidades, quatro moradores demonstrativos, um cartão fictício e o cadastro do carregador real. A importação de julho aceitou 17 dos 18 registros; a importação seguinte do histórico completo acrescentou 124 válidos, reconheceu os 17 já importados e rejeitou quatro inválidos. Nenhum achado crítico precisou ser aceito para fechar julho.

| Unidade | Energia | Total |
|---|---:|---:|
| A-101 | 83,290 kWh | R$ 104,83 |
| A-102 | 46,440 kWh | R$ 77,41 |
| A-103 | 18,410 kWh | R$ 44,36 |
| A-104 | 19,630 kWh | R$ 43,52 |
| **Total** | **167,770 kWh** | **R$ 270,12** |

Uma revisão independente conferiu os dez arquivos históricos contra o commit original, os checksums, os links locais e as descrições de IA/rateio contra o código, sem apontar correções adicionais no escopo.

## O que os testes cobrem

- Reimportação e deduplicação; dados reais, simulados e atribuídos identificáveis.
- Motor de rateio, política por unidade, arredondamento e comparação com o exemplo original.
- Anomalias críticas, outliers, amostra insuficiente e decisão registrada antes do fechamento.
- Proteção por organização/unidade, leitura restrita do morador e PDF.
- Navegação, importação, revisão de recargas e recuperação de falhas na interface.

Testes aprovados são evidência técnica do comportamento coberto. A compreensão do código e das decisões deve ser demonstrada pelo autor na apresentação e na avaliação.
