from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.modules.audit.infrastructure.models import AuditEventModel
from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
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
from app.modules.sessions.domain.errors import SessionNotFound, UnitNotFound
from app.modules.sessions.infrastructure.models import SessionAssignmentModel
from app.modules.sessions.infrastructure.repository import SqlAlchemySessionRepository
from app.shared.sqlalchemy import Base

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
    return UUID(f"{prefix:08x}-0000-0000-0000-{suffix:012d}")


def manager_scope(suffix: int) -> OrganizationScope:
    return OrganizationScope(
        auth_user_id=identifier(6, suffix),
        profile_id=identifier(5, suffix),
        organization_id=identifier(1, suffix),
        role=OrganizationRole.MANAGER,
        unit_id=None,
    )


async def row_count(session: AsyncSession, model: type[object]) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def seed_organization(
    session: AsyncSession,
    suffix: int,
) -> tuple[UUID, UUID, UUID, UUID]:
    organization_id = identifier(1, suffix)
    site_id = identifier(2, suffix)
    charger_id = identifier(3, suffix)
    import_batch_id = identifier(4, suffix)
    manager_id = identifier(5, suffix)
    session.add_all(
        [
            OrganizationModel(id=organization_id, name=f"Organization {suffix}"),
            SiteModel(
                id=site_id,
                organization_id=organization_id,
                name=f"Site {suffix}",
                timezone="America/Sao_Paulo",
            ),
            ChargerModel(
                id=charger_id,
                organization_id=organization_id,
                site_id=site_id,
                serial=f"CHARGER-{suffix}",
                name=f"Charger {suffix}",
                nominal_power_kw=Decimal("11.000"),
            ),
            ProfileModel(
                id=manager_id,
                auth_user_id=identifier(6, suffix),
                email=f"manager-{suffix}@example.test",
                display_name=f"Manager {suffix}",
            ),
            ImportBatchModel(
                id=import_batch_id,
                organization_id=organization_id,
                source="sems_export",
                checksum=f"{suffix:064d}",
                filename=f"organization-{suffix}.csv",
                storage_path=None,
                status="completed",
                total_count=1,
                valid_count=1,
                invalid_count=0,
                duplicate_count=0,
                created_by=manager_id,
            ),
        ]
    )
    return organization_id, site_id, charger_id, import_batch_id


async def add_session(
    session: AsyncSession,
    *,
    organization_id: UUID,
    site_id: UUID,
    charger_id: UUID,
    import_batch_id: UUID,
    id_suffix: int,
    started_at: datetime,
    status: str = "pending_review",
    card_id_raw: str | None = None,
) -> ChargingSessionModel:
    raw_record = RawImportRecordModel(
        id=identifier(7, id_suffix),
        organization_id=organization_id,
        import_batch_id=import_batch_id,
        row_number=id_suffix,
        raw_payload={},
        classification="valid",
        error_field=None,
        error_code=None,
        error_message=None,
    )
    charging_session = ChargingSessionModel(
        id=identifier(8, id_suffix),
        organization_id=organization_id,
        site_id=site_id,
        charger_id=charger_id,
        import_batch_id=import_batch_id,
        raw_record_id=raw_record.id,
        source="sems_export",
        external_id=f"external-{id_suffix}",
        deduplication_key=f"deduplication-{id_suffix}",
        started_at=started_at,
        ended_at=started_at + timedelta(hours=1),
        energy_kwh=Decimal("7.000"),
        charge_port=1,
        card_id_raw=card_id_raw,
        identity_confidence="unknown",
        provenance="real",
        status=status,
    )
    session.add_all([raw_record, charging_session])
    return charging_session


async def test_list_sessions_is_organization_scoped_and_does_not_trust_card_id(
    async_session: AsyncSession,
) -> None:
    first_organization_id, first_site_id, first_charger_id, first_batch_id = (
        await seed_organization(async_session, 1)
    )
    second_organization_id, second_site_id, second_charger_id, second_batch_id = (
        await seed_organization(async_session, 2)
    )
    first_session = await add_session(
        async_session,
        organization_id=first_organization_id,
        site_id=first_site_id,
        charger_id=first_charger_id,
        import_batch_id=first_batch_id,
        id_suffix=1,
        started_at=datetime(2026, 8, 31, 23, 59, tzinfo=UTC),
        card_id_raw="RAW-CARD-MUST-NOT-ASSIGN",
    )
    later_matching_session = await add_session(
        async_session,
        organization_id=first_organization_id,
        site_id=first_site_id,
        charger_id=first_charger_id,
        import_batch_id=first_batch_id,
        id_suffix=4,
        started_at=datetime(2026, 8, 31, 23, 59, tzinfo=UTC),
    )
    await add_session(
        async_session,
        organization_id=first_organization_id,
        site_id=first_site_id,
        charger_id=first_charger_id,
        import_batch_id=first_batch_id,
        id_suffix=5,
        started_at=datetime(2026, 8, 31, 23, 58, tzinfo=UTC),
        status="completed",
    )
    await add_session(
        async_session,
        organization_id=first_organization_id,
        site_id=first_site_id,
        charger_id=first_charger_id,
        import_batch_id=first_batch_id,
        id_suffix=2,
        started_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    second_session = await add_session(
        async_session,
        organization_id=second_organization_id,
        site_id=second_site_id,
        charger_id=second_charger_id,
        import_batch_id=second_batch_id,
        id_suffix=3,
        started_at=datetime(2026, 8, 31, 23, 59, tzinfo=UTC),
    )
    second_unit = UnitModel(
        id=identifier(9, 2),
        organization_id=second_organization_id,
        code="201",
        display_name="Apartment 201",
    )
    async_session.add_all(
        [
            second_unit,
            SessionAssignmentModel(
                id=identifier(10, 2),
                organization_id=second_organization_id,
                charging_session_id=second_session.id,
                unit_id=second_unit.id,
                assigned_by=identifier(5, 2),
                justification="Verified for the other organization",
            ),
        ]
    )
    await async_session.commit()

    repository = SqlAlchemySessionRepository(async_session)

    items = await repository.list_sessions(
        first_organization_id,
        period="2026-08",
        status="pending_review",
    )

    assert [item.id for item in items] == [
        later_matching_session.id,
        first_session.id,
    ]
    assert items[1].identity_confidence == "unknown"
    assert items[1].unit_id is None
    assert items[1].unit_code is None
    assert items[1].resident_name is None


async def test_list_sessions_includes_explicit_assignment_and_resident(
    async_session: AsyncSession,
) -> None:
    organization_id, site_id, charger_id, import_batch_id = await seed_organization(
        async_session,
        1,
    )
    assigned_session = await add_session(
        async_session,
        organization_id=organization_id,
        site_id=site_id,
        charger_id=charger_id,
        import_batch_id=import_batch_id,
        id_suffix=1,
        started_at=datetime(2026, 8, 29, 17, tzinfo=UTC),
    )
    unit = UnitModel(
        id=identifier(9, 1),
        organization_id=organization_id,
        code="101",
        display_name="Apartment 101",
    )
    resident = ProfileModel(
        id=identifier(11, 1),
        auth_user_id=identifier(12, 1),
        email="resident@example.test",
        display_name="Resident One",
    )
    resident_with_tied_created_at = ProfileModel(
        id=identifier(11, 2),
        auth_user_id=identifier(12, 2),
        email="resident-tie@example.test",
        display_name="Resident Tie",
    )
    later_resident = ProfileModel(
        id=identifier(11, 3),
        auth_user_id=identifier(12, 3),
        email="resident-later@example.test",
        display_name="Resident Later",
    )
    async_session.add_all(
        [
            unit,
            resident,
            resident_with_tied_created_at,
            later_resident,
            MembershipModel(
                id=identifier(13, 0),
                organization_id=organization_id,
                profile_id=identifier(5, 1),
                unit_id=unit.id,
                role="manager",
                created_at=datetime(2026, 8, 1, tzinfo=UTC),
            ),
            MembershipModel(
                id=identifier(13, 3),
                organization_id=organization_id,
                profile_id=later_resident.id,
                unit_id=unit.id,
                role="resident",
                created_at=datetime(2026, 8, 3, tzinfo=UTC),
            ),
            MembershipModel(
                id=identifier(13, 1),
                organization_id=organization_id,
                profile_id=resident.id,
                unit_id=unit.id,
                role="resident",
                created_at=datetime(2026, 8, 2, tzinfo=UTC),
            ),
            MembershipModel(
                id=identifier(13, 2),
                organization_id=organization_id,
                profile_id=resident_with_tied_created_at.id,
                unit_id=unit.id,
                role="resident",
                created_at=datetime(2026, 8, 2, tzinfo=UTC),
            ),
            SessionAssignmentModel(
                id=identifier(10, 1),
                organization_id=organization_id,
                charging_session_id=assigned_session.id,
                unit_id=unit.id,
                assigned_by=identifier(5, 1),
                justification="Confirmed by manager",
            ),
        ]
    )
    await async_session.commit()

    items = await SqlAlchemySessionRepository(async_session).list_sessions(
        organization_id,
        period="2026-08",
        status="pending_review",
    )

    assert [item.id for item in items] == [assigned_session.id]
    assert items[0].unit_id == unit.id
    assert items[0].unit_code == "101"
    assert items[0].unit_name == "Apartment 101"
    assert items[0].resident_name == "Resident One"


async def test_list_assignment_units_is_scoped_and_keeps_vacant_units(
    async_session: AsyncSession,
) -> None:
    first_organization_id, _, _, _ = await seed_organization(async_session, 1)
    second_organization_id, _, _, _ = await seed_organization(async_session, 2)
    occupied_unit = UnitModel(
        id=identifier(9, 1),
        organization_id=first_organization_id,
        code="101",
        display_name="Apartment 101",
    )
    vacant_unit = UnitModel(
        id=identifier(9, 3),
        organization_id=first_organization_id,
        code="102",
        display_name="Apartment 102",
    )
    other_organization_unit = UnitModel(
        id=identifier(9, 2),
        organization_id=second_organization_id,
        code="201",
        display_name="Apartment 201",
    )
    resident = ProfileModel(
        id=identifier(11, 1),
        auth_user_id=identifier(12, 1),
        email="resident@example.test",
        display_name="Resident One",
    )
    other_resident = ProfileModel(
        id=identifier(11, 2),
        auth_user_id=identifier(12, 2),
        email="other-resident@example.test",
        display_name="Resident Two",
    )
    async_session.add_all(
        [
            vacant_unit,
            occupied_unit,
            other_organization_unit,
            resident,
            other_resident,
            MembershipModel(
                id=identifier(13, 1),
                organization_id=first_organization_id,
                profile_id=resident.id,
                unit_id=occupied_unit.id,
                role="resident",
            ),
            MembershipModel(
                id=identifier(13, 2),
                organization_id=second_organization_id,
                profile_id=other_resident.id,
                unit_id=other_organization_unit.id,
                role="resident",
            ),
        ]
    )
    await async_session.commit()

    repository = SqlAlchemySessionRepository(async_session)

    items = await repository.list_assignment_units(first_organization_id)

    assert [(item.code, item.resident_name) for item in items] == [
        ("101", "Resident One"),
        ("102", None),
    ]
    assert all(not hasattr(item, "email") for item in items)


async def test_assign_session_creates_audited_assignment_without_changing_observations(
    async_session: AsyncSession,
) -> None:
    organization_id, site_id, charger_id, import_batch_id = await seed_organization(
        async_session,
        1,
    )
    charging_session = await add_session(
        async_session,
        organization_id=organization_id,
        site_id=site_id,
        charger_id=charger_id,
        import_batch_id=import_batch_id,
        id_suffix=1,
        started_at=datetime(2026, 8, 29, 17, tzinfo=UTC),
        card_id_raw="RAW-CARD-MUST-STAY-UNTRUSTED",
    )
    unit = UnitModel(
        id=identifier(9, 1),
        organization_id=organization_id,
        code="A-101",
        display_name="Apartment A-101",
    )
    async_session.add(unit)
    await async_session.commit()
    observed_values = (
        charging_session.organization_id,
        charging_session.site_id,
        charging_session.charger_id,
        charging_session.import_batch_id,
        charging_session.raw_record_id,
        charging_session.source,
        charging_session.external_id,
        charging_session.deduplication_key,
        charging_session.started_at,
        charging_session.ended_at,
        charging_session.energy_kwh,
        charging_session.charge_port,
        charging_session.card_id_raw,
        charging_session.provenance,
    )
    occurred_at = datetime(2026, 8, 30, 18, tzinfo=UTC)

    result = await SqlAlchemySessionRepository(async_session).assign_session(
        manager_scope(1),
        charging_session.id,
        unit.id,
        "Confirmado pelo síndico",
        occurred_at,
    )

    assignment = await async_session.scalar(select(SessionAssignmentModel))
    audit = await async_session.scalar(select(AuditEventModel))
    assert assignment is not None
    assert audit is not None
    assert await row_count(async_session, SessionAssignmentModel) == 1
    assert await row_count(async_session, AuditEventModel) == 1
    assert assignment.organization_id == organization_id
    assert assignment.charging_session_id == charging_session.id
    assert assignment.unit_id == unit.id
    assert assignment.assigned_by == manager_scope(1).profile_id
    assert assignment.justification == "Confirmado pelo síndico"
    assert as_utc(assignment.created_at) == occurred_at
    assert as_utc(assignment.updated_at) == occurred_at
    assert not hasattr(assignment, "card_id_raw")
    assert charging_session.identity_confidence == "assigned"
    assert charging_session.status == "ready"
    assert (
        charging_session.organization_id,
        charging_session.site_id,
        charging_session.charger_id,
        charging_session.import_batch_id,
        charging_session.raw_record_id,
        charging_session.source,
        charging_session.external_id,
        charging_session.deduplication_key,
        charging_session.started_at,
        charging_session.ended_at,
        charging_session.energy_kwh,
        charging_session.charge_port,
        charging_session.card_id_raw,
        charging_session.provenance,
    ) == observed_values
    assert audit.organization_id == organization_id
    assert audit.actor_profile_id == manager_scope(1).profile_id
    assert as_utc(audit.occurred_at) == occurred_at
    assert audit.event_type == "session_assigned"
    assert audit.entity_type == "charging_session"
    assert audit.entity_id == charging_session.id
    assert audit.metadata_json == {
        "previous_unit_id": None,
        "new_unit_id": str(unit.id),
        "justification": "Confirmado pelo síndico",
    }
    assert result.created is True
    assert result.assignment.id == assignment.id
    assert result.session.identity_confidence == "assigned"
    assert result.session.status == "ready"
    assert result.session.unit_id == unit.id
    assert result.session.unit_code == "A-101"


async def test_assign_session_exact_replay_is_idempotent(
    async_session: AsyncSession,
) -> None:
    organization_id, site_id, charger_id, import_batch_id = await seed_organization(
        async_session,
        1,
    )
    charging_session = await add_session(
        async_session,
        organization_id=organization_id,
        site_id=site_id,
        charger_id=charger_id,
        import_batch_id=import_batch_id,
        id_suffix=1,
        started_at=datetime(2026, 8, 29, 17, tzinfo=UTC),
    )
    unit = UnitModel(
        id=identifier(9, 1),
        organization_id=organization_id,
        code="A-101",
        display_name="Apartment A-101",
    )
    async_session.add(unit)
    await async_session.commit()
    repository = SqlAlchemySessionRepository(async_session)
    first_occurred_at = datetime(2026, 8, 30, 18, tzinfo=UTC)
    first = await repository.assign_session(
        manager_scope(1),
        charging_session.id,
        unit.id,
        "Confirmado pelo síndico",
        first_occurred_at,
    )

    replay = await repository.assign_session(
        manager_scope(1),
        charging_session.id,
        unit.id,
        "Confirmado pelo síndico",
        first_occurred_at + timedelta(minutes=5),
    )

    assert await row_count(async_session, SessionAssignmentModel) == 1
    assert await row_count(async_session, AuditEventModel) == 1
    assert replay.created is False
    assert replay.assignment == first.assignment
    assert replay.session == first.session


async def test_assign_session_reassignment_updates_current_row_and_appends_audit(
    async_session: AsyncSession,
) -> None:
    organization_id, site_id, charger_id, import_batch_id = await seed_organization(
        async_session,
        1,
    )
    charging_session = await add_session(
        async_session,
        organization_id=organization_id,
        site_id=site_id,
        charger_id=charger_id,
        import_batch_id=import_batch_id,
        id_suffix=1,
        started_at=datetime(2026, 8, 29, 17, tzinfo=UTC),
    )
    unit_a = UnitModel(
        id=identifier(9, 1),
        organization_id=organization_id,
        code="A-101",
        display_name="Apartment A-101",
    )
    unit_b = UnitModel(
        id=identifier(9, 2),
        organization_id=organization_id,
        code="A-102",
        display_name="Apartment A-102",
    )
    async_session.add_all([unit_a, unit_b])
    await async_session.commit()
    repository = SqlAlchemySessionRepository(async_session)
    first_occurred_at = datetime(2026, 8, 30, 18, tzinfo=UTC)
    first = await repository.assign_session(
        manager_scope(1),
        charging_session.id,
        unit_a.id,
        "Confirmação inicial",
        first_occurred_at,
    )
    corrected_at = first_occurred_at + timedelta(minutes=5)

    reassigned = await repository.assign_session(
        manager_scope(1),
        charging_session.id,
        unit_b.id,
        "Correção",
        corrected_at,
    )

    assignment = await async_session.scalar(select(SessionAssignmentModel))
    audits = tuple(
        (
            await async_session.scalars(
                select(AuditEventModel).order_by(AuditEventModel.occurred_at)
            )
        ).all()
    )
    assert assignment is not None
    assert await row_count(async_session, SessionAssignmentModel) == 1
    assert len(audits) == 2
    assert assignment.id == first.assignment.id
    assert assignment.unit_id == unit_b.id
    assert assignment.justification == "Correção"
    assert as_utc(assignment.updated_at) == corrected_at
    assert audits[-1].metadata_json == {
        "previous_unit_id": str(unit_a.id),
        "new_unit_id": str(unit_b.id),
        "justification": "Correção",
    }
    assert reassigned.created is False
    assert reassigned.assignment.unit_id == unit_b.id
    assert reassigned.session.unit_id == unit_b.id


async def test_assign_session_hides_cross_tenant_session_and_unit_ids(
    async_session: AsyncSession,
) -> None:
    first_ids = await seed_organization(async_session, 1)
    second_ids = await seed_organization(async_session, 2)
    first_session = await add_session(
        async_session,
        organization_id=first_ids[0],
        site_id=first_ids[1],
        charger_id=first_ids[2],
        import_batch_id=first_ids[3],
        id_suffix=1,
        started_at=datetime(2026, 8, 29, 17, tzinfo=UTC),
    )
    second_session = await add_session(
        async_session,
        organization_id=second_ids[0],
        site_id=second_ids[1],
        charger_id=second_ids[2],
        import_batch_id=second_ids[3],
        id_suffix=2,
        started_at=datetime(2026, 8, 29, 18, tzinfo=UTC),
    )
    first_unit = UnitModel(
        id=identifier(9, 1),
        organization_id=first_ids[0],
        code="A-101",
        display_name="Apartment A-101",
    )
    second_unit = UnitModel(
        id=identifier(9, 2),
        organization_id=second_ids[0],
        code="B-201",
        display_name="Apartment B-201",
    )
    async_session.add_all([first_unit, second_unit])
    await async_session.commit()
    repository = SqlAlchemySessionRepository(async_session)
    occurred_at = datetime(2026, 8, 30, 18, tzinfo=UTC)

    with pytest.raises(SessionNotFound):
        await repository.assign_session(
            manager_scope(1),
            second_session.id,
            first_unit.id,
            "Tentativa inválida",
            occurred_at,
        )
    with pytest.raises(UnitNotFound):
        await repository.assign_session(
            manager_scope(1),
            first_session.id,
            second_unit.id,
            "Tentativa inválida",
            occurred_at,
        )

    assert await row_count(async_session, SessionAssignmentModel) == 0
    assert await row_count(async_session, AuditEventModel) == 0


async def test_assign_session_rolls_back_all_changes_when_audit_insert_fails(
    async_session: AsyncSession,
) -> None:
    organization_id, site_id, charger_id, import_batch_id = await seed_organization(
        async_session,
        1,
    )
    charging_session = await add_session(
        async_session,
        organization_id=organization_id,
        site_id=site_id,
        charger_id=charger_id,
        import_batch_id=import_batch_id,
        id_suffix=1,
        started_at=datetime(2026, 8, 29, 17, tzinfo=UTC),
    )
    unit = UnitModel(
        id=identifier(9, 1),
        organization_id=organization_id,
        code="A-101",
        display_name="Apartment A-101",
    )
    async_session.add(unit)
    await async_session.commit()
    charging_session_id = charging_session.id
    sync_engine = async_session.sync_session.bind
    assert sync_engine is not None

    def fail_audit_insert(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        if "INSERT INTO audit_events" in statement:
            raise SQLAlchemyError("forced audit insert failure")

    event.listen(sync_engine, "before_cursor_execute", fail_audit_insert)
    try:
        with pytest.raises(SQLAlchemyError, match="forced audit insert failure"):
            await SqlAlchemySessionRepository(async_session).assign_session(
                manager_scope(1),
                charging_session.id,
                unit.id,
                "Confirmado pelo síndico",
                datetime(2026, 8, 30, 18, tzinfo=UTC),
            )
    finally:
        event.remove(sync_engine, "before_cursor_execute", fail_audit_insert)

    persisted_session = await async_session.scalar(
        select(ChargingSessionModel)
        .where(ChargingSessionModel.id == charging_session_id)
        .execution_options(populate_existing=True)
    )
    assert persisted_session is not None
    assert persisted_session.identity_confidence == "unknown"
    assert persisted_session.status == "pending_review"
    assert await row_count(async_session, SessionAssignmentModel) == 0
    assert await row_count(async_session, AuditEventModel) == 0
