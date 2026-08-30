# EV ChargeOps API

Backend FastAPI responsável por autenticação, escopo organizacional,
persistência e consulta das importações do SEMS+. O backend é o único
componente que acessa as tabelas operacionais e o armazenamento de arquivos
originais.

## Modos de execução

### Local/test

O modo `local/test` usa SQLite, autenticação fixture e armazenamento no
filesystem. Não requer Supabase ou outra conta externa. Copie `.env.example`
para `.env`, instale as dependências na raiz e execute:

```bash
pnpm db:upgrade
uv run --project apps/api python apps/api/scripts/seed_operational_foundation.py
pnpm dev:api
```

A API local escuta em `http://127.0.0.1:8407`.

O script raiz `db:upgrade` executa
`uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head`.
O seed pode ser repetido sem duplicar a organização, o site, o carregador ou
as quatro unidades.

### Demo

O modo `demo` exige Supabase PostgreSQL, Auth e Storage. Use PostgreSQL direto
quando o host tiver IPv6. Para um backend somente IPv4, selecione o
**Supavisor session** na porta `5432`; transaction mode não é a conexão
documentada para este backend persistente.

O inventário de configuração do backend é:

- `APP_ENV`
- `AUTH_MODE`
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_JWT_AUDIENCE`
- `ORIGINAL_FILE_STORE`
- `DEMO_MANAGER_EMAIL`
- `ORIGINAL_FILES_ROOT` e `FIXTURE_AUTH_TOKEN` somente em `local/test`
- `SUPABASE_SERVICE_ROLE_KEY` somente no backend em `demo`

Defina os valores somente em `apps/api/.env`, que não deve ser versionado. Em
demo, use autenticação Supabase, PostgreSQL e o armazenamento Supabase;
fixture auth é rejeitado. `SUPABASE_SERVICE_ROLE_KEY` é exclusivo do backend
e jamais pode entrar no frontend, em logs ou em documentação. Este guia
publica apenas nomes de variáveis, nunca credenciais ou connection strings.

## Migrações, seed e Storage remoto

Os comandos locais e remotos são os mesmos:

```bash
pnpm db:upgrade
uv run --project apps/api python apps/api/scripts/seed_operational_foundation.py
pnpm db:check
```

Quando `DATABASE_URL` aponta para um projeto remoto, migration e seed são
escritas externas. Confirme o projeto e os comandos no momento da execução.
Antes da primeira importação remota, um operador deve criar separadamente o
bucket privado `sems-imports`, restringir o MIME type a `text/csv` e limitar
cada objeto a 10 MB. A criação do bucket e a primeira confirmação de
importação também são escritas externas e exigem autorização explícita.

O seed não cria usuários do Auth. O operador cria ou identifica a conta cujo
valor corresponde a `DEMO_MANAGER_EMAIL`; a primeira requisição autenticada a
`/v1/me` cria somente o perfil e membership allowlisted.

## Rotas

- `GET /health`: saúde da API, sem autenticação.
- `GET /v1/me`: escopo do usuário autenticado.
- `POST /v1/import-batches/preview`: valida e classifica o CSV sem persistir.
- `POST /v1/import-batches`: confirma uma importação idempotente.
- `GET /v1/import-batches`: lista lotes da organização autenticada.
- `GET /v1/import-batches/{batch_id}`: retorna lote e registros brutos.

Todos os endpoints operacionais recebem bearer token verificado e derivam a
organização do escopo autorizado, nunca de um identificador fornecido pelo
cliente. CSV é somente um adapter de leitura; não existe caminho de comando
para o carregador GoodWe/FIAP.

## Verificação

Na raiz:

```bash
pnpm typecheck:api
pnpm test:api
pnpm test:integration
pnpm db:check
pnpm check
```
