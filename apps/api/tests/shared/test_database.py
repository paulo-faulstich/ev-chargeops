import pytest
from sqlalchemy import text

from app.shared.config import Settings
from app.shared.database import create_engine_from_settings, create_session_factory


@pytest.mark.asyncio
async def test_async_session_executes_against_test_database() -> None:
    settings = Settings(
        app_env="test",
        auth_mode="fixture",
        database_url="sqlite+aiosqlite:///:memory:",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )
    engine = create_engine_from_settings(settings)
    factory = create_session_factory(engine)

    async with factory() as session:
        assert await session.scalar(text("select 1")) == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_plain_postgres_url_uses_async_psycopg_driver() -> None:
    settings = Settings(
        app_env="local",
        auth_mode="fixture",
        database_url="postgresql://example.invalid/postgres",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )

    engine = create_engine_from_settings(settings)

    assert engine.url.drivername == "postgresql+psycopg"
    await engine.dispose()
