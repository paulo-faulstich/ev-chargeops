# ADR 0004: Procedência explícita para dados reais, atribuídos e simulados

**Status:** aceito

**Data:** 29 de agosto de 2026

## Contexto

O SEMS+ fornece energia e horários reais, mas o histórico observado não fornece identidade confiável. A demonstração precisa completar usuário e unidade sem apresentar essa associação como telemetria GoodWe.

## Decisão

Persistir fonte, lote e registro bruto de cada sessão. Campos de identidade recebem nível de confiança, e a interface distingue dados `real`, `assigned`, `simulated`, `derived` e `external`.

## Consequências

- A solução permanece honesta sobre limitações da integração.
- Faturas e insights podem ser auditados até a origem.
- A interface precisa comunicar procedência sem sobrecarregar o usuário.
- O modelo armazena metadados adicionais e eventos de atribuição.

## Alternativas consideradas

- Preencher identidades simuladas diretamente no CSV: simples, mas mistura evidência e demonstração.
- Ignorar usuários e faturar apenas por carregador: não resolve o desafio condominial.
- Bloquear qualquer sessão sem RFID: impediria demonstrar o fluxo com os dados disponíveis.
