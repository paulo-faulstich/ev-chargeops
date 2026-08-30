from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.main import app
from app.modules.audit.infrastructure import models as audit_models  # noqa: F401
from app.modules.ingestion.infrastructure import (
    models as ingestion_models,  # noqa: F401
)
from app.modules.organizations.infrastructure.models import (
    MembershipModel,
    ProfileModel,
)
from app.shared.config import Settings, get_settings
from app.shared.database import get_db_session
from app.shared.sqlalchemy import Base
from scripts.seed_operational_foundation import (
    DEMO_ORGANIZATION_ID,
    seed_operational_foundation,
)

FIXTURE_AUTH_USER_ID = UUID("50000000-0000-0000-0000-000000000001")
FIXTURE_PROFILE_ID = UUID("60000000-0000-0000-0000-000000000001")
FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"


@pytest.fixture
def fixture_token() -> str:
    return "fixture-manager-token"


@pytest_asyncio.fixture
async def async_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def api_client(
    async_session: AsyncSession,
    fixture_token: str,
    tmp_path: Path,
) -> Iterator[TestClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield async_session

    def override_settings() -> Settings:
        return Settings(
            app_env="test",
            auth_mode="fixture",
            database_url="sqlite+aiosqlite:///:memory:",
            supabase_url="https://example.supabase.co",
            fixture_auth_token=fixture_token,
            demo_manager_email="manager@example.test",
            original_file_store="local",
            original_files_root=tmp_path / "original-imports",
        )

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def seeded_scope(async_session: AsyncSession) -> None:
    await seed_operational_foundation(async_session)
    async_session.add(
        ProfileModel(
            id=FIXTURE_PROFILE_ID,
            auth_user_id=FIXTURE_AUTH_USER_ID,
            email="manager@example.test",
            display_name="Demo Manager",
        )
    )
    async_session.add(
        MembershipModel(
            organization_id=DEMO_ORGANIZATION_ID,
            profile_id=FIXTURE_PROFILE_ID,
            unit_id=None,
            role="manager",
        )
    )
    await async_session.commit()


def post_fixture(
    api_client: TestClient,
    fixture_token: str,
    *,
    filename: str = "sems.csv",
) -> object:
    return api_client.post(
        "/v1/import-batches",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": (filename, FIXTURE.read_bytes(), "text/csv")},
    )
