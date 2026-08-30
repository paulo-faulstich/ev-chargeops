from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.modules.organizations.infrastructure import (
    models as organization_models,  # noqa: F401
)
from app.shared.sqlalchemy import Base


@dataclass(frozen=True)
class EcKeyPair:
    private: ec.EllipticCurvePrivateKey
    public: ec.EllipticCurvePublicKey


@pytest.fixture
def ec_key_pair() -> EcKeyPair:
    private = ec.generate_private_key(ec.SECP256R1())
    return EcKeyPair(private=private, public=private.public_key())


@pytest_asyncio.fixture
async def async_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
