from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
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
from app.modules.identity.domain.auth import AuthPrincipal
from app.modules.identity.domain.errors import InvalidAccessToken
from app.modules.identity.presentation.dependencies import get_token_verifier
from app.modules.ingestion.infrastructure.models import (
    ChargingSessionModel,
    ImportBatchModel,
    RawImportRecordModel,
)
from app.modules.organizations.infrastructure.models import (
    ChargerModel,
    MembershipModel,
    OrganizationModel,
    ProfileModel,
    SiteModel,
    UnitModel,
)
from app.shared.config import Settings, get_settings
from app.shared.database import get_db_session
from app.shared.sqlalchemy import Base
from scripts.seed_operational_foundation import (
    DEMO_ORGANIZATION_ID,
    seed_operational_foundation,
)

MANAGER_AUTH_USER_ID = UUID("50000000-0000-0000-0000-000000000001")
MANAGER_PROFILE_ID = UUID("60000000-0000-0000-0000-000000000001")
RESIDENT_AUTH_USER_ID = UUID("50000000-0000-0000-0000-000000000002")
RESIDENT_PROFILE_ID = UUID("60000000-0000-0000-0000-000000000002")
OTHER_ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000002")
OTHER_PROFILE_ID = UUID("60000000-0000-0000-0000-000000000003")
OTHER_UNIT_ID = UUID("40000000-0000-0000-0000-000000000005")
OTHER_SESSION_ID = UUID("90000000-0000-0000-0000-000000000001")
FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"


@dataclass(frozen=True)
class PresentationTokenVerifier:
    def verify(self, token: str) -> AuthPrincipal:
        if token == "fixture-manager-token":
            return AuthPrincipal(MANAGER_AUTH_USER_ID, "manager@example.test")
        if token == "fixture-resident-token":
            return AuthPrincipal(RESIDENT_AUTH_USER_ID, "resident@example.test")
        raise InvalidAccessToken


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer fixture-manager-token"}


@pytest.fixture
def resident_headers() -> dict[str, str]:
    return {"Authorization": "Bearer fixture-resident-token"}


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
            fixture_auth_token="fixture-manager-token",
            demo_manager_email="manager@example.test",
            original_file_store="local",
            original_files_root=tmp_path / "original-imports",
        )

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_token_verifier] = PresentationTokenVerifier
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def seeded_scope(async_session: AsyncSession) -> None:
    await seed_operational_foundation(async_session)
    async_session.add_all(
        [
            ProfileModel(
                id=MANAGER_PROFILE_ID,
                auth_user_id=MANAGER_AUTH_USER_ID,
                email="manager@example.test",
                display_name="Demo Manager",
            ),
            MembershipModel(
                organization_id=DEMO_ORGANIZATION_ID,
                profile_id=MANAGER_PROFILE_ID,
                unit_id=None,
                role="manager",
            ),
            ProfileModel(
                id=RESIDENT_PROFILE_ID,
                auth_user_id=RESIDENT_AUTH_USER_ID,
                email="resident@example.test",
                display_name="Demo Resident",
            ),
            MembershipModel(
                organization_id=DEMO_ORGANIZATION_ID,
                profile_id=RESIDENT_PROFILE_ID,
                unit_id=None,
                role="resident",
            ),
        ]
    )
    await _seed_other_tenant(async_session)
    await async_session.commit()


async def _seed_other_tenant(session: AsyncSession) -> None:
    site_id = UUID("20000000-0000-0000-0000-000000000002")
    charger_id = UUID("30000000-0000-0000-0000-000000000002")
    batch_id = UUID("70000000-0000-0000-0000-000000000002")
    raw_record_id = UUID("80000000-0000-0000-0000-000000000002")
    session.add_all(
        [
            OrganizationModel(
                id=OTHER_ORGANIZATION_ID,
                name="Other condominium",
            ),
            SiteModel(
                id=site_id,
                organization_id=OTHER_ORGANIZATION_ID,
                name="Other site",
                timezone="America/Sao_Paulo",
            ),
            ChargerModel(
                id=charger_id,
                organization_id=OTHER_ORGANIZATION_ID,
                site_id=site_id,
                serial="OTHER-CHARGER",
                name="Other charger",
                nominal_power_kw=Decimal("11.000"),
            ),
            UnitModel(
                id=OTHER_UNIT_ID,
                organization_id=OTHER_ORGANIZATION_ID,
                code="B-201",
                display_name="Unit B-201",
            ),
            ProfileModel(
                id=OTHER_PROFILE_ID,
                auth_user_id=UUID("50000000-0000-0000-0000-000000000003"),
                email="other-manager@example.test",
                display_name="Other Manager",
            ),
            MembershipModel(
                organization_id=OTHER_ORGANIZATION_ID,
                profile_id=OTHER_PROFILE_ID,
                unit_id=None,
                role="manager",
            ),
            ImportBatchModel(
                id=batch_id,
                organization_id=OTHER_ORGANIZATION_ID,
                source="sems_export",
                checksum="other-checksum",
                filename="other.csv",
                storage_path=None,
                status="completed",
                total_count=1,
                valid_count=1,
                invalid_count=0,
                duplicate_count=0,
                created_by=OTHER_PROFILE_ID,
            ),
            RawImportRecordModel(
                id=raw_record_id,
                organization_id=OTHER_ORGANIZATION_ID,
                import_batch_id=batch_id,
                row_number=1,
                raw_payload={"Card ID": "PRIVATE-OTHER-CARD"},
                classification="valid",
                error_field=None,
                error_code=None,
                error_message=None,
            ),
            ChargingSessionModel(
                id=OTHER_SESSION_ID,
                organization_id=OTHER_ORGANIZATION_ID,
                site_id=site_id,
                charger_id=charger_id,
                import_batch_id=batch_id,
                raw_record_id=raw_record_id,
                source="sems_export",
                external_id=None,
                deduplication_key="other-deduplication-key",
                started_at=datetime(2026, 8, 29, 20, tzinfo=UTC),
                ended_at=datetime(2026, 8, 29, 21, tzinfo=UTC),
                energy_kwh=Decimal("9.500"),
                charge_port=1,
                card_id_raw="PRIVATE-OTHER-CARD",
                identity_confidence="unknown",
                provenance="observed",
                status="pending_review",
            ),
        ]
    )


def import_fixture(api_client: TestClient, auth_headers: dict[str, str]) -> None:
    response = api_client.post(
        "/v1/import-batches",
        headers=auth_headers,
        files={"file": ("sems.csv", FIXTURE.read_bytes(), "text/csv")},
    )
    assert response.status_code == 201
