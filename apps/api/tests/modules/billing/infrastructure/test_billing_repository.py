"""The billing repository reads one period, in one organization, in one site."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.modules.billing.domain.errors import PeriodNotFound, SiteNotFound
from app.modules.billing.infrastructure.models import (
    BillingPolicyModel,
    ChargerEnergyReadingModel,
    TariffBandModel,
    TariffSnapshotModel,
)
from app.modules.billing.infrastructure.repository import SqlAlchemyBillingRepository
from app.modules.ingestion.infrastructure.models import (
    ChargingSessionModel,
    ImportBatchModel,
    RawImportRecordModel,
)
from app.modules.organizations.infrastructure.models import (
    ChargerModel,
    OrganizationModel,
    ProfileModel,
    SiteModel,
    UnitModel,
)
from app.modules.sessions.infrastructure.models import SessionAssignmentModel
from app.shared.sqlalchemy import Base

pytestmark = pytest.mark.asyncio


def identifier(prefix: int, suffix: int) -> UUID:
    return UUID(f"{prefix:08x}-0000-0000-0000-{suffix:012d}")


@pytest_asyncio.fixture
async def async_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def seed_tenant(session: AsyncSession, suffix: int) -> dict[str, UUID]:
    ids = {
        "organization": identifier(1, suffix),
        "site": identifier(2, suffix),
        "charger": identifier(3, suffix),
        "batch": identifier(4, suffix),
        "profile": identifier(5, suffix),
        "unit": identifier(6, suffix),
    }
    session.add_all(
        [
            OrganizationModel(id=ids["organization"], name=f"Condomínio {suffix}"),
            SiteModel(
                id=ids["site"],
                organization_id=ids["organization"],
                name=f"Local {suffix}",
                timezone="America/Sao_Paulo",
            ),
            ChargerModel(
                id=ids["charger"],
                organization_id=ids["organization"],
                site_id=ids["site"],
                serial=f"CHARGER-{suffix}",
                name=f"Carregador {suffix}",
                nominal_power_kw=Decimal("11.000"),
            ),
            UnitModel(
                id=ids["unit"],
                organization_id=ids["organization"],
                code=f"A-{suffix}",
                display_name=f"Unidade A-{suffix}",
            ),
            ProfileModel(
                id=ids["profile"],
                auth_user_id=identifier(7, suffix),
                email=f"manager-{suffix}@example.test",
                display_name=f"Síndico {suffix}",
            ),
            ImportBatchModel(
                id=ids["batch"],
                organization_id=ids["organization"],
                source="simulated",
                checksum=f"{suffix:064d}",
                filename=f"cenario-{suffix}.csv",
                storage_path=None,
                status="completed",
                total_count=0,
                valid_count=0,
                invalid_count=0,
                duplicate_count=0,
                created_by=ids["profile"],
            ),
        ]
    )
    await session.flush()
    return ids


async def add_session(
    session: AsyncSession,
    ids: dict[str, UUID],
    *,
    suffix: int,
    started_at: datetime,
    energy: str,
    assigned: bool = True,
    status: str = "ready",
) -> UUID:
    raw_id = identifier(8, suffix)
    session_id = identifier(9, suffix)
    session.add_all(
        [
            RawImportRecordModel(
                id=raw_id,
                organization_id=ids["organization"],
                import_batch_id=ids["batch"],
                row_number=suffix,
                raw_payload={},
                classification="valid",
            ),
            ChargingSessionModel(
                id=session_id,
                organization_id=ids["organization"],
                site_id=ids["site"],
                charger_id=ids["charger"],
                import_batch_id=ids["batch"],
                raw_record_id=raw_id,
                source="simulated",
                external_id=f"external-{suffix}",
                deduplication_key=f"dedup-{suffix}",
                started_at=started_at,
                ended_at=started_at + timedelta(hours=2),
                energy_kwh=Decimal(energy),
                charge_port=1,
                card_id_raw=None,
                identity_confidence="assigned" if assigned else "unknown",
                provenance="simulated",
                status=status,
            ),
        ]
    )
    if assigned:
        session.add(
            SessionAssignmentModel(
                id=identifier(10, suffix),
                organization_id=ids["organization"],
                charging_session_id=session_id,
                unit_id=ids["unit"],
                assigned_by=ids["profile"],
                justification="Cenário de teste",
            )
        )
    await session.flush()
    return session_id


async def add_tariff_and_policy(session: AsyncSession, ids: dict[str, UUID]) -> None:
    tariff_id = identifier(11, 1)
    session.add_all(
        [
            TariffSnapshotModel(
                id=tariff_id,
                organization_id=ids["organization"],
                name="Referência",
                timezone="America/Sao_Paulo",
                source="sprint1_reference",
                source_reference=None,
                captured_at=datetime(2026, 1, 1, tzinfo=UTC),
                valid_from=date(2026, 1, 1),
                valid_to=None,
            ),
            TariffBandModel(
                id=identifier(12, 1),
                organization_id=ids["organization"],
                tariff_snapshot_id=tariff_id,
                code="fora_ponta",
                rate_cents_per_kwh=78,
                windows=[
                    {
                        "start_minute": 0,
                        "end_minute": 1440,
                        "weekdays": [0, 1, 2, 3, 4, 5, 6],
                    }
                ],
            ),
            BillingPolicyModel(
                id=identifier(13, 1),
                organization_id=ids["organization"],
                name="Referência",
                infra_fee_cents=2500,
                loss_basis_points=400,
                valid_from=date(2026, 1, 1),
                valid_to=None,
            ),
        ]
    )
    await session.flush()


async def test_opening_a_period_twice_returns_the_same_one(
    async_session: AsyncSession,
) -> None:
    """A second import for the same month must not create a rival period."""
    ids = await seed_tenant(async_session, 1)
    repository = SqlAlchemyBillingRepository(async_session)

    first = await repository.open_period(ids["organization"], None, "2026-05")
    second = await repository.open_period(ids["organization"], None, "2026-05")

    assert first.id == second.id
    assert first.status == "open"
    assert first.timezone == "America/Sao_Paulo"


async def test_opening_a_period_without_a_site_is_rejected(
    async_session: AsyncSession,
) -> None:
    organization_id = identifier(1, 99)
    async_session.add(OrganizationModel(id=organization_id, name="Sem local"))
    await async_session.flush()
    repository = SqlAlchemyBillingRepository(async_session)

    with pytest.raises(SiteNotFound):
        await repository.open_period(organization_id, None, "2026-05")


async def test_a_period_from_another_organization_is_not_found(
    async_session: AsyncSession,
) -> None:
    """Cross-tenant reads must look exactly like a missing record."""
    first = await seed_tenant(async_session, 1)
    second = await seed_tenant(async_session, 2)
    repository = SqlAlchemyBillingRepository(async_session)
    theirs = await repository.open_period(second["organization"], None, "2026-05")

    with pytest.raises(PeriodNotFound):
        await repository.get_period(first["organization"], theirs.id)


async def test_the_dataset_measures_the_period_in_the_site_timezone(
    async_session: AsyncSession,
) -> None:
    """23:30 on 31 May in São Paulo is already June in UTC, and still bills in May."""
    ids = await seed_tenant(async_session, 1)
    await add_session(
        async_session,
        ids,
        suffix=1,
        started_at=datetime(2026, 6, 1, 2, 30, tzinfo=UTC),
        energy="18",
    )
    await add_session(
        async_session,
        ids,
        suffix=2,
        started_at=datetime(2026, 6, 1, 3, 30, tzinfo=UTC),
        energy="7",
    )
    await async_session.commit()

    repository = SqlAlchemyBillingRepository(async_session)
    may = await repository.open_period(ids["organization"], None, "2026-05")
    june = await repository.open_period(ids["organization"], None, "2026-06")

    may_dataset = await repository.load_dataset(ids["organization"], may)
    june_dataset = await repository.load_dataset(ids["organization"], june)

    assert [item.energy_kwh for item in may_dataset.sessions] == [Decimal("18.000")]
    assert [item.energy_kwh for item in june_dataset.sessions] == [Decimal("7.000")]


async def test_the_dataset_never_reaches_another_organization(
    async_session: AsyncSession,
) -> None:
    first = await seed_tenant(async_session, 1)
    second = await seed_tenant(async_session, 2)
    await add_session(
        async_session,
        first,
        suffix=1,
        started_at=datetime(2026, 5, 4, 22, tzinfo=UTC),
        energy="10",
    )
    await add_session(
        async_session,
        second,
        suffix=2,
        started_at=datetime(2026, 5, 4, 22, tzinfo=UTC),
        energy="99",
    )
    await async_session.commit()

    repository = SqlAlchemyBillingRepository(async_session)
    period = await repository.open_period(first["organization"], None, "2026-05")
    dataset = await repository.load_dataset(first["organization"], period)

    assert [item.energy_kwh for item in dataset.sessions] == [Decimal("10.000")]


async def test_the_aggregate_sums_only_the_days_of_the_period(
    async_session: AsyncSession,
) -> None:
    ids = await seed_tenant(async_session, 1)
    async_session.add_all(
        [
            ChargerEnergyReadingModel(
                id=identifier(14, index),
                organization_id=ids["organization"],
                charger_id=ids["charger"],
                import_batch_id=ids["batch"],
                period_type="day",
                period_value=day,
                energy_kwh=Decimal(energy),
                source="simulated",
                provenance="simulated",
                captured_at=datetime(2026, 6, 1, tzinfo=UTC),
            )
            for index, (day, energy) in enumerate(
                [("2026-05-04", "10.5"), ("2026-05-19", "4.5"), ("2026-06-01", "99")],
                start=1,
            )
        ]
    )
    await async_session.commit()

    repository = SqlAlchemyBillingRepository(async_session)
    period = await repository.open_period(ids["organization"], None, "2026-05")
    dataset = await repository.load_dataset(ids["organization"], period)

    assert dataset.aggregate_energy_kwh == Decimal("15.000")


async def test_a_period_without_readings_has_no_external_reconciliation(
    async_session: AsyncSession,
) -> None:
    ids = await seed_tenant(async_session, 1)
    await async_session.commit()

    repository = SqlAlchemyBillingRepository(async_session)
    period = await repository.open_period(ids["organization"], None, "2026-05")
    dataset = await repository.load_dataset(ids["organization"], period)

    assert dataset.aggregate_energy_kwh is None


async def test_effective_tariff_and_policy_are_detected(
    async_session: AsyncSession,
) -> None:
    ids = await seed_tenant(async_session, 1)
    repository = SqlAlchemyBillingRepository(async_session)
    period = await repository.open_period(ids["organization"], None, "2026-05")

    before = await repository.load_dataset(ids["organization"], period)
    assert not before.has_effective_tariff
    assert not before.has_effective_policy

    await add_tariff_and_policy(async_session, ids)
    await async_session.commit()

    after = await repository.load_dataset(ids["organization"], period)
    assert after.has_effective_tariff
    assert after.has_effective_policy


async def test_unassigned_sessions_arrive_without_a_unit(
    async_session: AsyncSession,
) -> None:
    ids = await seed_tenant(async_session, 1)
    await add_session(
        async_session,
        ids,
        suffix=1,
        started_at=datetime(2026, 5, 4, 22, tzinfo=UTC),
        energy="10",
        assigned=True,
    )
    await add_session(
        async_session,
        ids,
        suffix=2,
        started_at=datetime(2026, 5, 5, 22, tzinfo=UTC),
        energy="4",
        assigned=False,
        status="pending_review",
    )
    await async_session.commit()

    repository = SqlAlchemyBillingRepository(async_session)
    period = await repository.open_period(ids["organization"], None, "2026-05")
    dataset = await repository.load_dataset(ids["organization"], period)

    billable = [item for item in dataset.sessions if item.is_billable]
    pending = [item for item in dataset.sessions if not item.is_billable]
    assert len(billable) == 1
    assert len(pending) == 1
    assert pending[0].unit_id is None
