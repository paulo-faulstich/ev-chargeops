# Mudanças entre a proposta e a implementação

A Sprint 1 é preservada como pesquisa e planejamento. A Sprint 2 adotou o fluxo completo de fechamento e faturamento por unidade, considerando o acesso disponível aos dados do laboratório. Este registro atende à exigência do enunciado de justificar desvios no README e em sua documentação vinculada.

## Comparação de escopo

| Proposta ou planejamento anterior | Implementação da Sprint 2 | Motivo e consequência |
|---|---|---|
| Integração SEMS API e alternativa OCPP | CSV exportado do SEMS+, importado com validação e procedência | O acesso necessário à API de EV Chargers não foi disponibilizado no desafio e OCPP não estava disponível no equipamento de referência. Não há sincronização automática com o fabricante |
| Identidade por RFID para cada usuário | Cartões cadastrados no sistema ou atribuição manual justificada | Na captura, o `Card ID` repete o serial do carregador. O registro bruto é preservado; a associação demonstrativa não é apresentada como identidade informada pela GoodWe |
| Fatura e taxa de infraestrutura por usuário | Fatura e taxa fixa por unidade que carregou | A unidade é o responsável financeiro estável. No exemplo original, U102 tinha duas taxas de R$ 25,00; agora tem uma. A energia e as perdas são preservadas, mas o total de U102 cai de R$ 118,88 para R$ 93,88 |
| Detecção de anomalias | Implementada com regras determinísticas e estatística robusta | Atua antes da emissão. Inconsistências críticas bloqueiam; outliers de energia avisam. Decisões do gestor ficam registradas |
| Previsão de consumo/demanda e clustering | Adiados | O recorte priorizou a fatura auditável, e os dados reais não identificam usuários. Atribuições demonstrativas não sustentam previsões ou perfis reais de moradores. O protótipo não entrega todas as capacidades analíticas propostas na Sprint 1 |
| Interface conversacional NLP de apoio | Não implementada | O parecer tem explicações construídas por regras; não é texto gerado por modelo de linguagem |
| Consulta tarifária automatizada à ANEEL | Tarifas versionadas com fonte e vigência; valores de demonstração | Não há consulta automática à ANEEL no fluxo entregue. O seed usa as tarifas de referência da proposta, identificadas como cenário |
| Pix/Mercado Pago no planejamento intermediário | Fora desta entrega | O recorte produz o documento para repasse condominial. Não há cobrança real nem gateway de pagamento |
| Backend NestJS na decisão intermediária | FastAPI/Python com Next.js/TypeScript | Concentra regras, processamento e análise em Python. [ADR 0005](../../decisions/0005-nextjs-fastapi-modular-monolith.md) |
| Portal independente de morador | Visão da fatura em contexto restrito de unidade, acessível pelo gestor | Demonstra isolamento e leitura da fatura; não entrega cadastro/login próprio do morador |

## O que a análise faz

O algoritmo `closing-opinion/1.0.0` recebe as recargas do período e registra versão, parâmetros, amostra e checksum do conjunto analisado.

- Regras determinísticas verificam intervalo, energia, potência média, sobreposições e ausência de unidade.
- A regra estatística compara recargas da mesma unidade usando z-score modificado sobre a MAD. Usa desvio absoluto médio como alternativa quando a MAD é zero.
- São necessárias pelo menos cinco recargas por unidade para essa comparação; abaixo disso, o resultado informa amostra insuficiente.
- Outliers estatísticos geram aviso. Achados críticos das regras de integridade impedem o fechamento até revisão registrada.
- O cálculo financeiro não é produzido pela análise: tarifa, taxa e perdas seguem regras determinísticas.

A rubrica reserva 3,0 pontos ao papel estrutural da IA. A integração do parecer ao fechamento é demonstrável, mas a aceitação do recorte, sem previsão e clustering, cabe ao avaliador. Não se afirma que esses módulos foram implementados ou que o conjunto equivale a um modelo treinado de aprendizado de máquina.

## Rateio e comparação com a Sprint 1

```text
fatura(unidade, mês) = soma dos valores das recargas
                    + taxa fixa da unidade ativa
                    + percentual de perdas sobre o valor da energia
```

A taxa fixa é R$ 25,00 por unidade ativa no cenário, não um custo total dividido dinamicamente pelo número de unidades. Unidade sem consumo não recebe taxa. A faixa tarifária é a do início da sessão porque a fonte não contém uma curva de energia que permita repartir o consumo entre horários.

Os testes em `apps/api/tests/modules/billing/domain/test_sprint1_golden.py` verificam energia e perdas contra os dados originais, os totais das unidades com um usuário, a taxa única na unidade U102 e o total zerado da unidade sem consumo. **Não há reprodução literal das seis faturas originais:** a agregação por unidade e a redução de uma taxa são mudanças deliberadas.

## Limites da demonstração

Os dados do carregador são observados; os responsáveis, cartões de exemplo e valores tarifários são cenário. Uma implantação real ainda exige cadastro validado pela administração, tarifa contratada, validação das faturas com a conta de energia e piloto operacional. O modo local e o vídeo demonstram o protótipo acadêmico; não comprovam operação produtiva ou integração remota ativa.
