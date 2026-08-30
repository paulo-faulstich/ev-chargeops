import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.modules.audit.infrastructure.models import AuditEventModel
from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.ingestion.application.confirm_import import ConfirmImport
from app.modules.ingestion.application.preview_import import (
    ImportPreview,
    PreviewImport,
)
from app.modules.ingestion.domain.import_batch import ImportBatchResult
from app.modules.ingestion.infrastructure.file_store import LocalOriginalFileStore
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


class RecoveryRecordingImportRepository(SqlAlchemyImportRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.checksum_recovery_queries = 0
        self.session_recovery_queries = 0

    async def find_batch_by_checksum(
        self,
        organization_id: UUID,
        checksum: str,
    ) -> ImportBatchResult | None:
        self.checksum_recovery_queries += 1
        return await super().find_batch_by_checksum(organization_id, checksum)

    async def existing_keys(
        self,
        organization_id: UUID,
        keys: set[str],
    ) -> set[str]:
        self.session_recovery_queries += 1
        return await super().existing_keys(organization_id, keys)


class ConfirmRace:
    def __init__(self) -> None:
        self.initial_lookups = 0
        self.save_attempts = 0
        self.both_checked = asyncio.Event()
        self.both_ready_to_save = asyncio.Event()
        self.winner_committed = asyncio.Event()

    async def after_initial_lookup(self) -> None:
        self.initial_lookups += 1
        if self.initial_lookups == 2:
            self.both_checked.set()
        await self.both_checked.wait()

    async def before_save(self) -> None:
        self.save_attempts += 1
        if self.save_attempts == 2:
            self.both_ready_to_save.set()
        await self.both_ready_to_save.wait()


class CoordinatedImportRepository(SqlAlchemyImportRepository):
    def __init__(
        self,
        session: AsyncSession,
        race: ConfirmRace,
        *,
        winner: bool,
    ) -> None:
        super().__init__(session)
        self.race = race
        self.winner = winner
        self.initial_lookup = True

    async def find_batch_by_checksum(
        self,
        organization_id: UUID,
        checksum: str,
    ) -> ImportBatchResult | None:
        result = await super().find_batch_by_checksum(organization_id, checksum)
        if self.initial_lookup:
            self.initial_lookup = False
            assert result is None
            await self.race.after_initial_lookup()
        return result

    async def save_import(
        self,
        scope: OrganizationScope,
        preview: ImportPreview,
        storage_path: str,
    ) -> ImportBatchResult:
        await self.race.before_save()
        if self.winner:
            try:
                return await super().save_import(scope, preview, storage_path)
            finally:
                self.race.winner_committed.set()

        await self.race.winner_committed.wait()
        await self.session.rollback()
        return await super().save_import(scope, preview, storage_path)


class OperationalFailureImportRepository(SqlAlchemyImportRepository):
    async def _save_once(
        self,
        scope: OrganizationScope,
        preview: ImportPreview,
        storage_path: str,
    ) -> ImportBatchResult:
        raise OperationalError(
            "insert into import_batches",
            {},
            RuntimeError("database unavailable"),
        )


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


async def test_unknown_integrity_error_propagates_without_recovery_queries(
    async_session: AsyncSession,
) -> None:
    tenant = await seed_tenant(async_session, 1)
    preview = PreviewImport(source()).execute("sems.csv", mixed_content())
    duplicate_row_number = replace(preview.records[1], row_number=2)
    malformed_preview = replace(
        preview,
        records=(preview.records[0], duplicate_row_number, preview.records[2]),
    )
    repository = RecoveryRecordingImportRepository(async_session)

    with pytest.raises(IntegrityError):
        await repository.save_import(tenant, malformed_preview, "canonical/source.csv")

    assert repository.checksum_recovery_queries == 0
    assert repository.session_recovery_queries == 0
    assert await row_count(async_session, ImportBatchModel) == 0


async def test_other_database_error_rolls_back_before_propagating(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = await seed_tenant(async_session, 1)
    repository = OperationalFailureImportRepository(async_session)
    rollback_calls = 0
    original_rollback = async_session.rollback

    async def recording_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        await original_rollback()

    monkeypatch.setattr(async_session, "rollback", recording_rollback)

    with pytest.raises(OperationalError):
        await repository.save_import(
            tenant,
            PreviewImport(source()).execute("sems.csv", fixture_content()),
            "canonical/source.csv",
        )

    assert rollback_calls == 1


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


@pytest.mark.parametrize(
    ("first_filename", "second_filename"),
    [("sems.csv", "sems.csv"), ("first.csv", "renamed.csv")],
    ids=["same-filename", "different-filenames"],
)
async def test_concurrent_confirms_share_one_canonical_object_and_batch(
    tmp_path: Path,
    first_filename: str,
    second_filename: str,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'imports.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as seed_session:
        tenant = await seed_tenant(seed_session, 1)

    original_root = tmp_path / "originals"
    store = LocalOriginalFileStore(original_root)
    race = ConfirmRace()
    content = fixture_content()
    try:
        async with factory() as first_session, factory() as second_session:
            first_use_case = ConfirmImport(
                source(),
                CoordinatedImportRepository(first_session, race, winner=True),
                store,
            )
            second_use_case = ConfirmImport(
                source(),
                CoordinatedImportRepository(second_session, race, winner=False),
                store,
            )

            first_result, second_result = await asyncio.gather(
                first_use_case.execute(tenant, first_filename, content),
                second_use_case.execute(tenant, second_filename, content),
            )

        expected_path = (
            original_root
            / str(tenant.organization_id)
            / first_result.checksum
            / "source.csv"
        )
        assert first_result.created is True
        assert second_result == replace(first_result, created=False)
        assert [path for path in original_root.rglob("*") if path.is_file()] == [
            expected_path,
        ]
        assert expected_path.read_bytes() == content

        async with factory() as verification_session:
            batch = await verification_session.scalar(select(ImportBatchModel))
            assert batch is not None
            assert batch.filename == first_filename
            assert batch.storage_path == (
                f"{tenant.organization_id}/{first_result.checksum}/source.csv"
            )
            assert await row_count(verification_session, ImportBatchModel) == 1
            assert await row_count(verification_session, RawImportRecordModel) == 2
            assert await row_count(verification_session, ChargingSessionModel) == 2
            assert await row_count(verification_session, AuditEventModel) == 1
    finally:
        await engine.dispose()
