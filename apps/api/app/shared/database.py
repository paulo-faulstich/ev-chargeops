from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.shared.config import Settings, get_settings


def normalize_async_database_url(database_url: str) -> URL:
    url: URL = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return url


def create_engine_from_settings(settings: Settings) -> AsyncEngine:
    url = normalize_async_database_url(settings.database_url)
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_engine_from_settings(settings)
        _session_factory = create_session_factory(_engine)
    return _session_factory


async def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncSession]:
    async with session_factory(settings)() as session:
        yield session
