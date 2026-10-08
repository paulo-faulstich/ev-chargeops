# Registro de uso de Inteligência Artificial

Conforme a seção sobre uso de IA do enunciado, este arquivo registra de forma transparente como a IA foi utilizada na Sprint 01 do EV ChargeOps e qual validação crítica foi feita pelo autor.

## Autoria e responsabilidade

A pesquisa, a escolha das frentes e opções de aprofundamento, a arquitetura, o modelo de rateio e a definição do papel da IA refletem o entendimento e as decisões do autor. A IA foi usada como ferramenta de apoio à produtividade, sempre a partir das definições do autor e com revisão crítica integral. As conclusões e a proposta são autorais.

## Como a IA apoiou

- Organização da pesquisa: Apoiar a busca por fontes (regulação, datasheet do carregador, API do SEMS, soluções de mercado e dados de frota).
- Apoio à redação: Apoio a estruturação do README e revisão de texto a partir das decisões do autor.
- Geração dos dados simulados: apoio na construção do conjunto em `data/exemplos/`, mantendo coerência com o modelo de rateio.

## Validação crítica realizada pelo autor

- Fontes conferidas: cada fonte citada na Seção 9 do README foi efetivamente consultada; afirmações sobre a RN 1.000/2021, a legislação paulistana, as interfaces do HCA G2, a API do SEMS e os números da ABVE foram verificadas nas páginas originais.
- Matemática do rateio refeita à mão: os valores da tabela da Seção 5.4 foram conferidos a partir das tarifas por período e das energias das sessões (energia individual, taxa de infraestrutura e perdas de 4%).
- Coerência dos dados verificada: o conjunto simulado foi checado para conter os três casos excepcionais que o modelo precisa tratar (sessão interrompida, usuário sem consumo e duas faturas na mesma unidade).

O autor é capaz de explicar e defender integralmente a pesquisa, a arquitetura e o modelo de rateio propostos.
