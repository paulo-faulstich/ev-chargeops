# ADR 0005: Next.js e FastAPI em monólito modular

**Status:** aceito

**Data:** 29 de agosto de 2026

**Substitui:** [ADR 0001](0001-nextjs-nestjs-monorepo.md)

## Contexto

A Sprint 01 planejou a implementação de ingestão, rateio e três capacidades de IA em Python: detecção de anomalias, previsão de consumo/demanda e segmentação por clustering. A decisão inicial por NestJS tratava modelos de IA como uma evolução posterior e previa um eventual segundo serviço Python.

Ao consolidar o PRD da Sprint 02, essas três capacidades passaram a integrar a demonstração principal. Manter NestJS exigiria implementar parte do domínio em TypeScript e introduzir um serviço Python, ou reproduzir em Node.js um fluxo de dados já planejado com `pandas` e `scikit-learn`.

## Decisão

Usar Next.js e TypeScript no frontend e um backend único em Python com FastAPI, Pydantic, SQLAlchemy e Alembic. O backend será um monólito modular implantável como uma única unidade, com fronteiras internas orientadas ao domínio e ports/adapters.

Detecção de anomalias, previsão e segmentação residirão inicialmente no mesmo backend, atrás de ports próprios. O frontend consumirá a API REST por um client TypeScript gerado ou validado a partir do contrato OpenAPI.

Supabase continuará fornecendo PostgreSQL, Auth e Storage. O backend validará o JWT, aplicará autorização de negócio e será o único acesso às tabelas operacionais.

## Consequências

- O stack de implementação fica alinhado ao plano de IA registrado na Sprint 01.
- Ingestão, rateio e IA compartilham modelos canônicos sem comunicação de rede entre serviços.
- A demonstração exige apenas um deploy de backend e uma cadeia de observabilidade.
- Frontend e backend usam linguagens diferentes, com o contrato OpenAPI como fronteira tipada.
- A disciplina modular precisa ser garantida por estrutura, imports e testes, pois não haverá isolamento de processos.
- Um módulo poderá ser extraído para serviço independente sem alterar os casos de uso consumidores, desde que preserve seus ports.

## Alternativas consideradas

- **NestJS com serviço Python de IA:** separa runtimes, mas adiciona dois deploys, falhas de rede, versionamento de contrato e observabilidade distribuída antes de existir necessidade de escala independente.
- **Backend integralmente em Node.js:** mantém TypeScript ponta a ponta, mas se afasta das ferramentas de dados e IA já planejadas para a Sprint 02.
- **Next.js full-stack:** reduz setup, mas mistura interface, autorização, domínio, ingestão e processamento analítico no mesmo runtime.
- **Microserviços Python desde o início:** oferecem isolamento máximo, com custo operacional incompatível com o estágio atual.

## Critério de extração futura

Um serviço de IA separado só será criado se houver pelo menos um motivador observável: necessidade de escala independente, jobs que prejudiquem a API transacional, ciclo de deploy próprio, ownership separado ou requisitos de runtime incompatíveis. Até lá, as fronteiras serão lógicas dentro do monólito modular.
