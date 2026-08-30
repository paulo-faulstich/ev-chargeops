from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.modules.audit.infrastructure.models import AuditEventModel
from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.ingestion.application.preview_import import PreviewImport
from app.modules.ingestion.infrastructure.models import (
    ChargingSessionModel,
    ImportBatchModel,
    RawImportRecordModel,
)
from app.modules.ingestion.infrastructure.repository import SqlAlchemyImportRepository
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource
from app.modules.organizations.infrastructure.models import (
    ChargerModel,
    OrganizationModel,
    ProfileModel,
    SiteModel,
)
from app.shared.sqlalchemy import Base
from tests.modules.ingestion.application.fakes import (
    fixture_content,
    mixed_content,
    source,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def async_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def identifier(prefix: int, suffix: int) -> UUID:
    return UUID(f"{prefix}0000000-0000-0000-0000-{suffix:012d}")


async def seed_tenant(session: AsyncSession, suffix: int) -> OrganizationScope:
    organization_id = identifier(1, suffix)
    site_id = identifier(2, suffix)
    profile_id = identifier(6, suffix)
    auth_user_id = identifier(5, suffix)
    session.add_all(
        [
            OrganizationModel(
                id=organization_id,
                name=f"Organization {suffix}",
            ),
            SiteModel(
                id=site_id,
                organization_id=organization_id,
                name=f"Site {suffix}",
                timezone="America/Sao_Paulo",
            ),
            ChargerModel(
                id=identifier(3, suffix),
                organization_id=organization_id,
                site_id=site_id,
                serial="97500NAP25BL0008",
                name="GoodWe HCA G2",
                nominal_power_kw=Decimal("11.000"),
            ),
            ProfileModel(
                id=profile_id,
                auth_user_id=auth_user_id,
                email=f"manager-{suffix}@example.test",
                display_name=f"Manager {suffix}",
            ),
        ]
    )
    await session.commit()
    return OrganizationScope(
        auth_user_id=auth_user_id,
        profile_id=profile_id,
        organization_id=organization_id,
        role=OrganizationRole.MANAGER,
        unit_id=None,
    )


async def row_count(
    session: AsyncSession,
    model: type[Base],
    organization_id: UUID | None = None,
) -> int:
    statement = select(func.count()).select_from(model)
    if organization_id is not None:
        statement = statement.where(model.organization_id == organization_id)
    return int(await session.scalar(statement) or 0)


async def test_save_import_persists_raw_sessions_and_sanitized_audit(
    async_session: AsyncSession,
) -> None:
    tenant = await seed_tenant(async_session, 1)
    preview = PreviewImport(source()).execute("sems.csv", mixed_content())
    repository = SqlAlchemyImportRepository(async_session)

    result = await repository.save_import(
        tenant,
        preview,
        f"{tenant.organization_id}/{preview.checksum}/sems.csv",
    )

    assert result.created is True
    assert (result.total_count, result.valid_count, result.invalid_count) == (3, 1, 1)
    assert result.duplicate_count == 1
    assert await row_count(async_session, ImportBatchModel) == 1
    assert await row_count(async_session, RawImportRecordModel) == 3
    assert await row_count(async_session, ChargingSessionModel) == 1
    assert await row_count(async_session, AuditEventModel) == 1

    raw_records = tuple(
        (
            await async_session.scalars(
                select(RawImportRecordModel).order_by(RawImportRecordModel.row_number)
            )
        ).all()
    )
    persisted_session = await async_session.scalar(select(ChargingSessionModel))
    audit = await async_session.scalar(select(AuditEventModel))
    assert [record.classification for record in raw_records] == [
        "valid",
        "invalid",
        "duplicate",
    ]
    assert raw_records[0].raw_payload["Charging Energy(kWh)"] == "7.00"
    assert persisted_session is not None
    assert persisted_session.raw_record_id == raw_records[0].id
    assert persisted_session.charger_id == identifier(3, 1)
    assert persisted_session.site_id == identifier(2, 1)
    assert persisted_session.provenance == "real"
    assert persisted_session.identity_confidence == "unknown"
    assert persisted_session.status == "pending_review"
    assert audit is not None
    assert audit.event_type == "import_completed"
    assert audit.actor_profile_id == tenant.profile_id
    assert audit.metadata_json == {
        "total_count": 3,
        "valid_count": 1,
        "invalid_count": 1,
        "duplicate_count": 1,
    }
    assert "raw" not in audit.metadata_json


async def test_session_keys_and_checksum_are_scoped_by_organization(
    async_session: AsyncSession,
) -> None:
    first_scope = await seed_tenant(async_session, 1)
    second_scope = await seed_tenant(async_session, 2)
    preview = PreviewImport(source()).execute("sems.csv", fixture_content())
    repository = SqlAlchemyImportRepository(async_session)
    candidate_keys = {
        record.session.deduplication_key
        for record in preview.records
        if record.session is not None
    }

    first = await repository.save_import(first_scope, preview, "first/path.csv")

    assert await repository.existing_keys(
        first_scope.organization_id,
        candidate_keys,
    ) == candidate_keys
    assert await repository.existing_keys(
        second_scope.organization_id,
        candidate_keys,
    ) == set()
    assert (
        await repository.find_batch_by_checksum(
            second_scope.organization_id,
            preview.checksum,
        )
        is None
    )

    second = await repository.save_import(second_scope, preview, "second/path.csv")

    assert first.id != second.id
    assert await row_count(async_session, ImportBatchModel) == 2
    assert await row_count(async_session, ChargingSessionModel) == 4


async def test_same_tenant_session_integrity_race_becomes_duplicate_batch(
    async_session: AsyncSession,
) -> None:
    tenant = await seed_tenant(async_session, 1)
    preview = PreviewImport(source()).execute("sems.csv", fixture_content())
    repository = SqlAlchemyImportRepository(async_session)
    await repository.save_import(tenant, preview, "first/path.csv")
    concurrent_preview = replace(
        preview,
        filename="second.csv",
        checksum="b" * 64,
    )

    duplicate = await repository.save_import(
        tenant,
        concurrent_preview,
        "second/path.csv",
    )

    assert duplicate.created is True
    assert duplicate.valid_count == 0
    assert duplicate.duplicate_count == 2
    assert await row_count(async_session, ImportBatchModel) == 2
    assert await row_count(async_session, RawImportRecordModel) == 4
    assert await row_count(async_session, ChargingSessionModel) == 2
    assert await row_count(async_session, AuditEventModel) == 2


async def test_checksum_integrity_race_returns_scoped_replay(
    async_session: AsyncSession,
) -> None:
    tenant = await seed_tenant(async_session, 1)
    preview = PreviewImport(source()).execute("sems.csv", fixture_content())
    repository = SqlAlchemyImportRepository(async_session)
    existing = await repository.save_import(tenant, preview, "first/path.csv")

    replay = await repository.save_import(tenant, preview, "second/path.csv")

    assert replay == replace(existing, created=False)
    assert await row_count(async_session, ImportBatchModel) == 1
    assert await row_count(async_session, RawImportRecordModel) == 2
    assert await row_count(async_session, ChargingSessionModel) == 2
    assert await row_count(async_session, AuditEventModel) == 1


async def test_list_and_get_batches_never_cross_tenants(
    async_session: AsyncSession,
) -> None:
    first_scope = await seed_tenant(async_session, 1)
    second_scope = await seed_tenant(async_session, 2)
    repository = SqlAlchemyImportRepository(async_session)
    preview = PreviewImport(
        SemsCsvSource(source().default_timezone)
    ).execute("sems.csv", fixture_content())
    first = await repository.save_import(first_scope, preview, "first/path.csv")
    second = await repository.save_import(second_scope, preview, "second/path.csv")

    assert await repository.list_batches(first_scope.organization_id) == (first,)
    assert await repository.list_batches(second_scope.organization_id) == (second,)
    assert await repository.get_batch(first_scope.organization_id, second.id) is None
    assert await repository.get_batch(second_scope.organization_id, first.id) is None
