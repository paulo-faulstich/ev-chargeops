import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.modules.audit.infrastructure import models as audit_models  # noqa: F401
from app.modules.ingestion.infrastructure import (
    models as ingestion_models,  # noqa: F401
)
from app.modules.organizations.infrastructure import (
    models as organization_models,  # noqa: F401
)
from app.modules.sessions.infrastructure import models as session_models  # noqa: F401
from app.shared.config import Settings
from app.shared.database import normalize_async_database_url
from app.shared.sqlalchemy import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def database_url() -> str:
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return configured_url
    return Settings(supabase_url="http://localhost").database_url


config.set_main_option(
    "sqlalchemy.url",
    normalize_async_database_url(database_url()).render_as_string(
        hide_password=False
    ),
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
