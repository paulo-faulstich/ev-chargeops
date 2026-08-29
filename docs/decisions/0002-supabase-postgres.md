# ADR 0002: Supabase como plataforma PostgreSQL gerenciada

**Status:** aceito

**Data:** 29 de agosto de 2026

## Contexto

A demonstração precisa de persistência, identidade e armazenamento de arquivos sem demandar operação de infraestrutura própria. Também deve ser possível migrar o banco para outro provedor no futuro.

## Decisão

Usar Supabase para PostgreSQL, Auth e Storage. O backend FastAPI acessa o PostgreSQL por conexão padrão com SQLAlchemy; o Next.js não consulta tabelas operacionais diretamente.

## Consequências

- Banco relacional, autenticação e storage ficam disponíveis rapidamente.
- Trocar Supabase por outro PostgreSQL tende a exigir mudança de conexão e infraestrutura, não do domínio.
- Autorização de negócio permanece no FastAPI; RLS protege superfícies do Supabase.
- A equipe precisa administrar corretamente pool de conexões, migrations e chaves de serviço.

## Alternativas consideradas

- PostgreSQL local apenas: simples, mas reduz a qualidade da demonstração multiusuário.
- Acesso direto Next.js/Supabase: rápido, porém espalha regras e acopla o produto à plataforma.
- Firebase: bom ecossistema gerenciado, mas não preserva o modelo relacional já planejado.
