# EV ChargeOps - Problem Frame

**Status:** proposta consolidada para revisão

**Data:** 29 de agosto de 2026

## 1. Contexto

Condomínios e edifícios corporativos compartilham infraestrutura elétrica, vagas e carregadores entre pessoas com padrões de uso diferentes. O carregador registra energia e horários, mas esses registros não se tornam automaticamente atribuição por unidade, rateio, cobrança ou orientação operacional.

No LAB FIAP, o SEMS+ apresenta dados reais do carregador GoodWe, porém a API de EV Chargers não será disponibilizada aos grupos e o modelo de referência não oferece OCPP. O equipamento está em operação e não pode receber comandos ou alterações de configuração durante o desafio.

## 2. Problem statement

Síndicos e usuários de infraestruturas compartilhadas de recarga não possuem uma forma integrada e auditável de atribuir sessões a unidades, calcular o consumo individual, aplicar regras de rateio e acompanhar a cobrança. Os dados existem no SEMS+, mas não estão conectados ao contexto condominial nem disponíveis por API para o desafio.

## 3. Evidências disponíveis

- O SEMS+ apresenta histórico de início, fim, duração, energia, autonomia estimada, porta e um campo rotulado como `Card ID`.
- Na janela observada entre 31/07/2026 e 27/08/2026, foram identificadas 16 sessões, somando 133,83 kWh.
- O `Card ID` observado é igual ao serial do carregador em todas as sessões consultadas; portanto, não comprova a identidade do usuário.
- O histórico de recarga possui opção de exportação, mas o Report Center oferece apenas relatórios de estação e inversor.
- Uma consulta ampla de aproximadamente 13 meses não retornou dados, enquanto a janela padrão de 30 dias funcionou. A ingestão deve operar em janelas mensais e validar cada lote.
- A mentoria confirmou que a API para EV Chargers não será liberada aos grupos, que o fluxo é de consulta (`pull`) e que o acesso oferecido é à planta no SEMS+.

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
