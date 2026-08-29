# ADR 0003: Ports and Adapters para integrações substituíveis

**Status:** aceito

**Data:** 29 de agosto de 2026

## Contexto

A fonte disponível hoje é um arquivo obtido do SEMS+, enquanto o futuro pode oferecer GoodWe API, OCPP, Modbus ou plataformas de terceiros. Tarifas, pagamentos e análise também podem trocar de provedor.

## Decisão

Casos de uso dependerão de interfaces definidas na camada de aplicação. CSV, ANEEL, Mercado Pago, Supabase e futuros provedores serão adapters de infraestrutura injetados pelo NestJS.

## Consequências

- Adicionar uma nova fonte não altera o domínio de sessão e rateio.
- Adapters podem receber testes de contrato comuns.
- Falhas externas são traduzidas para erros da aplicação.
- Existe custo moderado de interfaces e mapeamento, concentrado apenas nas fronteiras realmente voláteis.

## Alternativas consideradas

- SDKs usados diretamente nos services: menor código inicial, mas alto acoplamento.
- Sistema dinâmico de plugins: flexível, porém desnecessário e arriscado para o MVP.
- Microserviço por integração: isolamento máximo com complexidade operacional prematura.
