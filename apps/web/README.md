# EV ChargeOps Web

Interface Next.js do produto operacional. A rota autenticada padrão é
`/dashboard`; a importação do SEMS+ fica em
`/settings/data-sources` como configuração secundária.

## Requisitos e execução local

Use Node.js `>=22.13.0 <23` e pnpm `11.19.0`. A partir da raiz:

```bash
pnpm install
cp apps/web/.env.example apps/web/.env.local
pnpm dev:web
```

A aplicação fica disponível em `http://localhost:3407`. O proxy local encaminha
`/api/*` para a API do ChargeOps em `http://127.0.0.1:8407`.

No modo `local/test`, defina `AUTH_MODE` como fixture no arquivo local. Esse
modo usa um token restrito ao ambiente não produtivo e não exige conta
Supabase. O Next.js encaminha `/api/*` para a API FastAPI e mantém o bearer
token fora de URLs.

## Modo demo

No modo `demo`, use autenticação Supabase e uma sessão real assinada. Defina
somente em `apps/web/.env.local`:

- `AUTH_MODE`
- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `API_PROXY_TARGET`

Somente a publishable key pode ser exposta ao browser. Nunca coloque
`DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, senhas ou tokens nesse arquivo ou
em qualquer variável `NEXT_PUBLIC_*`.

## Rotas do produto

- `/login`: autenticação por senha no modo demo.
- `/dashboard`: home autenticada e fundação do fechamento operacional.
- `/settings/data-sources`: preview, confirmação e histórico de importações.
- `/imports/new`: compatibilidade; redireciona para a fonte secundária.

O proxy do Next.js atualiza a sessão e protege as rotas. Uma sessão ausente
redireciona para `/login`; um usuário autenticado que abre a raiz ou o login é
direcionado para `/dashboard`.

## Verificação

Na raiz:

```bash
pnpm lint:web
pnpm --dir apps/web exec next build --webpack
pnpm test:web
```

Os testes Playwright iniciam servidores locais isolados, usam SQLite e fixture
auth e não acessam Supabase.
