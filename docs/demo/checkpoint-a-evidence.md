# Checkpoint A — evidências

Este registro separa evidência local automatizada de operações que exigem
acesso e autorização no projeto Supabase. Não contém tokens, e-mails, senhas,
connection strings nem payloads sensíveis.

## Escopo verificado localmente

Ambiente do gate: Node.js `22.19.0`, pnpm `11.19.0`, branch
`codex/operational-data-foundation`.

| Evidência | Comando | Resultado |
|---|---|---|
| Gate completo | `pnpm check` | Aprovado: Ruff; mypy em 48 arquivos; 114 testes da API; 5 de integração; Alembic e OpenAPI sem drift; 7 testes e typecheck do client; ESLint; build Webpack; 15 testes Playwright |
| Higiene de diff | `git diff --check` | Aprovado, sem saída |
| Higiene de credenciais | busca versionada por padrões de segredo | Aprovado: nenhum URL PostgreSQL com senha, JWT ou valor real de chave Supabase; e-mails versionados restantes usam somente o domínio reservado `example.test` |

Antes do gate, `pnpm db:upgrade` levou o SQLite local descartável ao head. O
gate cobre lint e typecheck da API, testes da API e de integração,
verificação de drift do Alembic e OpenAPI, testes e typecheck do client,
lint e build Webpack da web e testes Playwright. Os testes locais usam SQLite,
fixture auth e armazenamento isolado; não acessam o projeto Supabase.

Critérios locais rastreáveis no gate:

- `/dashboard` é a rota autenticada padrão;
- `/settings/data-sources` mantém a origem CSV como configuração secundária;
- lotes, registros brutos e sessões preservam procedência;
- replay por checksum e deduplicação entre lotes são cobertos por testes;
- consultas e restrições são isoladas por organização;
- não existe caminho de comando para o equipamento GoodWe/FIAP.

## Evidência remota pendente

As entradas abaixo permanecem deliberadamente pendentes. Nenhuma operação
live foi executada durante a preparação deste documento.

| Marco live | Evidência sanitizada a registrar | Estado |
|---|---|---|
| Configuração | modo demo validado sem fixture auth | Pendente de autorização |
| Migração | revisão Alembic em head e 10 tabelas operacionais | Pendente de autorização |
| Seed | 1 organização, 1 site, 1 carregador e 4 unidades, sem duplicação | Pendente de autorização |
| Storage | bucket privado `sems-imports`, `text/csv`, limite de 10 MB | Pendente de autorização |
| Auth | `/v1/me` com token assinado e bootstrap allowlisted | Pendente de autorização |
| Produto | screenshots sanitizados de `/dashboard` e `/settings/data-sources` | Pendente de autorização |
| Primeira importação | IDs e contagens: 1 lote, 2 registros brutos, 2 sessões, 1 evento de auditoria e 1 objeto privado | Pendente de autorização |
| Replay | mesmos IDs/contagens após reenvio, sem duplicação | Pendente de autorização |

## Limites de ação

Aplicar migration/seed, criar o bucket privado e confirmar a primeira
importação são escritas externas distintas. Cada uma requer confirmação no
momento da ação com o projeto-alvo e o efeito esperado claramente nomeados.
