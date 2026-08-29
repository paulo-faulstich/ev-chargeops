# ADR 0001: Next.js e NestJS em monorepo TypeScript

**Status:** aceito

**Data:** 29 de agosto de 2026

## Contexto

O produto precisa de uma experiência web convincente e de um backend com fronteiras explícitas para ingestão, rateio, pagamentos e insights. Route Handlers do Next.js seriam suficientes para uma camada BFF, mas concentrariam UI e domínio no mesmo runtime e enfraqueceriam a demonstração arquitetural.

## Decisão

Usar Next.js no frontend e NestJS no backend, em um monorepo pnpm com contratos TypeScript compartilhados. O backend expõe REST/OpenAPI e concentra regras, autorização e integrações.

## Consequências

- Tipagem e ferramentas consistentes entre frontend e backend.
- Módulos do NestJS tornam dependências e responsabilidades visíveis.
- Frontend e backend podem ser implantados separadamente.
- Há mais configuração inicial que em uma aplicação Next.js única.

## Alternativas consideradas

- Next.js full-stack: menor setup, mas maior acoplamento entre interface e domínio.
- Fastify sem NestJS: menor overhead, porém exige definir manualmente convenções e módulos.
- React com backend Python: adequado para ML, mas adiciona duas stacks antes de existir necessidade de modelos avançados.
