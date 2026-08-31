"""The close is one transaction: it issues everything or it changes nothing."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.modules.audit.infrastructure.models import AuditEventModel
from app.modules.billing.application.manage_periods import (
    GetInvoiceDetail,
    ListInvoices,
)
from app.modules.billing.application.render_invoice import RenderInvoiceDocument
from app.modules.billing.domain.errors import (
    DocumentChecksumMismatch,
    FindingAlreadyDecided,
    FindingNotFound,
    InvoiceNotFound,
    PeriodCloseBlocked,
    PeriodCloseConflict,
)
from app.modules.billing.domain.readiness import (
    NO_CLOSING_OPINION,
    UNASSIGNED_ENERGY,
)
from app.modules.billing.infrastructure.models import (
    AnalyticalFindingModel,
    BillingPeriodModel,
    BillingPolicyModel,
    InsightRunModel,
    InvoiceDocumentModel,
    InvoiceItemModel,
    InvoiceModel,
    TariffBandModel,
    TariffSnapshotModel,
)
from app.modules.billing.infrastructure.pdf_renderer import PdfInvoiceRenderer
from app.modules.billing.infrastructure.repository import SqlAlchemyBillingRepository
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
from app.modules.sessions.infrastructure.models import SessionAssignmentModel
from app.shared.sqlalchemy import Base

pytestmark = pytest.mark.asyncio

PERIOD = "2026-05"


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


async def seed_tenant(session: AsyncSession) -> dict[str, UUID]:
    ids = {
        "organization": identifier(1, 1),
        "site": identifier(2, 1),
        "charger": identifier(3, 1),
        "batch": identifier(4, 1),
        "profile": identifier(5, 1),
        "unit": identifier(6, 1),
        "idle_unit": identifier(6, 2),
        "resident": identifier(5, 2),
    }
    session.add_all(
        [
            OrganizationModel(id=ids["organization"], name="Condomínio"),
            SiteModel(
                id=ids["site"],
                organization_id=ids["organization"],
                name="Garagem",
                timezone="America/Sao_Paulo",
            ),
            ChargerModel(
                id=ids["charger"],
                organization_id=ids["organization"],
                site_id=ids["site"],
                serial="CHARGER-1",
                name="Carregador",
                nominal_power_kw=Decimal("11.000"),
            ),
            UnitModel(
                id=ids["unit"],
                organization_id=ids["organization"],
                code="A-101",
                display_name="Unidade A-101",
            ),
            UnitModel(
                id=ids["idle_unit"],
                organization_id=ids["organization"],
                code="B-202",
                display_name="Unidade B-202",
            ),
            ProfileModel(
                id=ids["profile"],
                auth_user_id=identifier(7, 1),
                email="manager@example.test",
                display_name="Síndico",
            ),
            ProfileModel(
                id=ids["resident"],
                auth_user_id=identifier(7, 2),
                email="resident@example.test",
                display_name="Moradora A-101",
            ),
            MembershipModel(
                id=identifier(14, 1),
                organization_id=ids["organization"],
                profile_id=ids["resident"],
                unit_id=ids["unit"],
                role="resident",
            ),
            ImportBatchModel(
                id=ids["batch"],
                organization_id=ids["organization"],
                source="simulated",
                checksum=f"{1:064d}",
                filename="cenario.csv",
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
                status="ready" if assigned else "pending_review",
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


async def add_opinion_run(
    session: AsyncSession, ids: dict[str, UUID], period_id: UUID
) -> UUID:
    run_id = identifier(15, 1)
    session.add(
        InsightRunModel(
            id=run_id,
            organization_id=ids["organization"],
            billing_period_id=period_id,
            kind="closing_opinion",
            algorithm_version="test-1",
            parameters={},
            dataset_checksum="0" * 64,
            sample_size=2,
            conclusion="approve",
            severity="info",
            confidence="high",
            recommendation="Nada impede o fechamento.",
            generated_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
    )
    await session.flush()
    return run_id


async def ready_to_close(
    session: AsyncSession,
) -> tuple[SqlAlchemyBillingRepository, dict[str, UUID], UUID, UUID]:
    """A period with two billable sessions and everything the close needs."""
    ids = await seed_tenant(session)
    await add_tariff_and_policy(session, ids)
    repository = SqlAlchemyBillingRepository(session)
    period = await repository.open_period(ids["organization"], None, PERIOD)
    await add_session(
        session,
        ids,
        suffix=1,
        started_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
        energy="10.5",
    )
    await add_session(
        session,
        ids,
        suffix=2,
        started_at=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
        energy="7.203",
    )
    run_id = await add_opinion_run(session, ids, period.id)
    await session.commit()
    return repository, ids, period.id, run_id


async def count_rows(session: AsyncSession, model: type[Base]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def test_close_issues_invoices_and_freezes_the_period(
    async_session: AsyncSession,
) -> None:
    repository, ids, period_id, run_id = await ready_to_close(async_session)

    view, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )

    assert view.status == "closed"
    assert view.approved_by_name == "Síndico"
    assert view.approved_at is not None
    assert view.tariff_snapshot_id == identifier(11, 1)
    assert view.billing_policy_id == identifier(13, 1)
    assert view.eligible_energy_kwh == Decimal("17.703")
    assert view.invoiced_energy_kwh == Decimal("17.703")

    frozen = await async_session.get(BillingPeriodModel, period_id)
    assert frozen is not None
    assert frozen.closing_insight_run_id == run_id

    assert [invoice.unit_code for invoice in invoices] == ["A-101", "B-202"]
    active, idle = invoices

    # 10.5 × 78 = 819; 7.203 × 78 = 561.834 → 562: rounded once per session.
    assert [item.value_cents for item in active.items] == [819, 562]
    assert active.energy_value_cents == 819 + 562
    assert active.infra_fee_cents == 2500
    assert active.loss_share_cents == 55  # 4% de 1381 = 55.24 → 55
    assert active.total_cents == 819 + 562 + 2500 + 55
    assert active.number == f"FAT-{PERIOD}-A-101"
    assert active.contact_label == "Moradora A-101"

    assert idle.items == ()
    assert idle.total_cents == 0
    assert idle.infra_fee_cents == 0
    assert idle.contact_label == "Unidade B-202"

    statuses = (
        (
            await async_session.execute(
                select(ChargingSessionModel.status).where(
                    ChargingSessionModel.organization_id == ids["organization"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert statuses == ["billed", "billed"]

    audit = (
        (
            await async_session.execute(
                select(AuditEventModel).where(
                    AuditEventModel.event_type == "billing_period_closed"
                )
            )
        )
        .scalars()
        .one()
    )
    assert audit.entity_id == period_id
    assert audit.metadata_json["invoice_count"] == 2
    assert audit.metadata_json["closing_insight_run_id"] == str(run_id)


async def test_close_with_blockers_changes_nothing(
    async_session: AsyncSession,
) -> None:
    repository, ids, period_id, _ = await ready_to_close(async_session)
    await add_session(
        async_session,
        ids,
        suffix=3,
        started_at=datetime(2026, 5, 12, 12, 0, tzinfo=UTC),
        energy="5.0",
        assigned=False,
    )
    await async_session.commit()

    with pytest.raises(PeriodCloseBlocked) as blocked:
        await repository.close_period(ids["organization"], period_id, ids["profile"])

    codes = [blocker.code for blocker in blocked.value.blockers]
    assert UNASSIGNED_ENERGY in codes

    period = await async_session.get(BillingPeriodModel, period_id)
    assert period is not None
    assert period.status == "open"
    assert period.approved_at is None
    assert await count_rows(async_session, InvoiceModel) == 0
    assert await count_rows(async_session, InvoiceItemModel) == 0


async def test_close_requires_a_closing_opinion(
    async_session: AsyncSession,
) -> None:
    """The approval must reference the opinion the manager reviewed."""
    ids = await seed_tenant(async_session)
    await add_tariff_and_policy(async_session, ids)
    repository = SqlAlchemyBillingRepository(async_session)
    period = await repository.open_period(ids["organization"], None, PERIOD)
    await add_session(
        async_session,
        ids,
        suffix=1,
        started_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
        energy="10.5",
    )
    await async_session.commit()

    with pytest.raises(PeriodCloseBlocked) as blocked:
        await repository.close_period(ids["organization"], period.id, ids["profile"])

    codes = [blocker.code for blocker in blocked.value.blockers]
    assert codes == [NO_CLOSING_OPINION]


async def test_closing_an_already_closed_period_conflicts_and_changes_nothing(
    async_session: AsyncSession,
) -> None:
    repository, ids, period_id, _ = await ready_to_close(async_session)
    view, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )
    first_approved_at = view.approved_at

    with pytest.raises(PeriodCloseConflict) as conflict:
        await repository.close_period(ids["organization"], period_id, ids["profile"])

    assert conflict.value.status == "closed"
    assert await count_rows(async_session, InvoiceModel) == len(invoices)
    period = await async_session.get(BillingPeriodModel, period_id)
    assert period is not None
    assert first_approved_at is not None
    # O instante congelado é o mesmo, e volta do banco com fuso.
    assert period.approved_at == first_approved_at


async def test_a_close_already_in_flight_wins_the_race(
    async_session: AsyncSession,
) -> None:
    """The claim is a compare-and-set from `open`: a second close loses cleanly.

    SQLite serializes the two statements, so the race is simulated by leaving
    the period in `closing`, exactly what the loser of the row lock would see
    on PostgreSQL.
    """
    repository, ids, period_id, _ = await ready_to_close(async_session)
    period = await async_session.get(BillingPeriodModel, period_id)
    assert period is not None
    period.status = "closing"
    await async_session.commit()

    with pytest.raises(PeriodCloseConflict) as conflict:
        await repository.close_period(ids["organization"], period_id, ids["profile"])

    assert conflict.value.status == "closing"
    assert await count_rows(async_session, InvoiceModel) == 0


async def test_issued_invoice_ignores_later_tariff_and_policy_changes(
    async_session: AsyncSession,
) -> None:
    """Changing the tariff after issue must not move a single cent."""
    repository, ids, period_id, _ = await ready_to_close(async_session)
    _, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )
    issued = invoices[0]

    band = await async_session.get(TariffBandModel, identifier(12, 1))
    policy = await async_session.get(BillingPolicyModel, identifier(13, 1))
    assert band is not None and policy is not None
    band.rate_cents_per_kwh = 999
    policy.infra_fee_cents = 9999
    policy.loss_basis_points = 2500
    await async_session.commit()

    reread = await repository.get_invoice(ids["organization"], issued.id)
    assert reread.energy_value_cents == issued.energy_value_cents
    assert reread.infra_fee_cents == issued.infra_fee_cents
    assert reread.loss_share_cents == issued.loss_share_cents
    assert reread.total_cents == issued.total_cents
    assert [item.value_cents for item in reread.items] == [
        item.value_cents for item in issued.items
    ]


async def test_contact_label_survives_the_resident_moving_out(
    async_session: AsyncSession,
) -> None:
    repository, ids, period_id, _ = await ready_to_close(async_session)
    _, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )
    issued = invoices[0]
    assert issued.contact_label == "Moradora A-101"

    resident = await async_session.get(ProfileModel, ids["resident"])
    assert resident is not None
    resident.display_name = "Outro Nome"
    await async_session.commit()

    reread = await repository.get_invoice(ids["organization"], issued.id)
    assert reread.contact_label == "Moradora A-101"


async def test_document_context_uses_the_frozen_tariff_not_todays(
    async_session: AsyncSession,
) -> None:
    """A tariff registered after the close must not change the document."""
    repository, ids, period_id, _ = await ready_to_close(async_session)
    _, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )
    tariff = await async_session.get(TariffSnapshotModel, identifier(11, 1))
    assert tariff is not None
    tariff.valid_to = date(2026, 5, 31)
    async_session.add(
        TariffSnapshotModel(
            id=identifier(11, 2),
            organization_id=ids["organization"],
            name="Tarifa nova",
            timezone="America/Sao_Paulo",
            source="manual",
            source_reference=None,
            captured_at=datetime(2026, 7, 1, tzinfo=UTC),
            valid_from=date(2026, 1, 15),
            valid_to=None,
        )
    )
    await async_session.commit()

    _, context = await repository.load_invoice_document_context(
        ids["organization"], invoices[0].id
    )

    assert context.tariff_name == "Referência"
    assert context.policy_name == "Referência"
    assert context.provenances == ("simulated",)
    assert context.organization_name == "Condomínio"


async def _critical_finding(
    session: AsyncSession, ids: dict[str, UUID], run_id: UUID
) -> UUID:
    finding_id = identifier(16, 1)
    session.add(
        AnalyticalFindingModel(
            id=finding_id,
            organization_id=ids["organization"],
            insight_run_id=run_id,
            charging_session_id=None,
            code="POWER_EXCEEDS_RATED",
            severity="critical",
            confidence="high",
            explanation="Potência média acima da nominal do carregador.",
            evidence={"observed_kw": "31.4"},
        )
    )
    await session.commit()
    return finding_id


async def test_an_undecided_critical_finding_blocks_the_close(
    async_session: AsyncSession,
) -> None:
    """The analysis refusing to let a period close silently is the point."""
    repository, ids, period_id, run_id = await ready_to_close(async_session)
    await _critical_finding(async_session, ids, run_id)

    with pytest.raises(PeriodCloseBlocked) as blocked:
        await repository.close_period(
            ids["organization"], period_id, ids["profile"]
        )

    assert [b.code for b in blocked.value.blockers] == ["CRITICAL_FINDING"]
    assert await count_rows(async_session, InvoiceModel) == 0


async def test_a_decided_finding_stops_blocking_and_keeps_its_reason(
    async_session: AsyncSession,
) -> None:
    """Deciding clears the blocker without erasing what was found."""
    repository, ids, period_id, run_id = await ready_to_close(async_session)
    finding_id = await _critical_finding(async_session, ids, run_id)

    decided = await repository.decide_finding(
        ids["organization"],
        period_id,
        finding_id,
        ids["profile"],
        "Medidor aferido; leitura de pico confirmada com a concessionária.",
    )

    assert decided.resolved_at is not None
    assert decided.resolved_by_name == "Síndico"
    assert decided.resolution_note.startswith("Medidor aferido")
    assert decided.code == "POWER_EXCEEDS_RATED"

    view, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )
    assert view.status == "closed"
    assert len(invoices) == 2


async def test_a_finding_carries_one_decision_only(
    async_session: AsyncSession,
) -> None:
    repository, ids, period_id, run_id = await ready_to_close(async_session)
    finding_id = await _critical_finding(async_session, ids, run_id)
    await repository.decide_finding(
        ids["organization"], period_id, finding_id, ids["profile"], "Primeira."
    )

    with pytest.raises(FindingAlreadyDecided):
        await repository.decide_finding(
            ids["organization"],
            period_id,
            finding_id,
            ids["profile"],
            "Segunda.",
        )


async def test_deciding_a_finding_of_another_organization_is_not_found(
    async_session: AsyncSession,
) -> None:
    repository, ids, period_id, run_id = await ready_to_close(async_session)
    finding_id = await _critical_finding(async_session, ids, run_id)

    with pytest.raises(FindingNotFound):
        await repository.decide_finding(
            identifier(1, 9), period_id, finding_id, ids["profile"], "Alheia."
        )


async def test_listing_findings_shows_the_decision_beside_the_finding(
    async_session: AsyncSession,
) -> None:
    repository, ids, period_id, run_id = await ready_to_close(async_session)
    finding_id = await _critical_finding(async_session, ids, run_id)

    before = await repository.list_findings(ids["organization"], period_id)
    assert [f.id for f in before] == [finding_id]
    assert before[0].resolved_at is None

    await repository.decide_finding(
        ids["organization"], period_id, finding_id, ids["profile"], "Aferido."
    )

    after = await repository.list_findings(ids["organization"], period_id)
    assert after[0].resolved_at is not None
    assert after[0].resolution_note == "Aferido."


async def test_invoice_times_survive_the_round_trip_through_the_database(
    async_session: AsyncSession,
) -> None:
    """Persisted instants come back aware, so rendering cannot guess the zone.

    A naive datetime out of the database is read by `astimezone` as the
    *server's* local time, which silently shifts every printed timestamp by
    whatever offset the machine runs in — enough to print a 31 May charge as
    1 June and make an honest invoice look wrong. The rendering tests build
    their own aware datetimes, so only a round trip catches this.
    """
    repository, ids, period_id, _ = await ready_to_close(async_session)
    _, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )

    reread = await repository.get_invoice(ids["organization"], invoices[0].id)

    assert reread.issued_at.tzinfo is not None
    for item in reread.items:
        assert item.started_at.tzinfo is not None
        assert item.ended_at.tzinfo is not None
    # The first billable session was seeded on 10 May, 12:00 UTC.
    first = reread.items[0].started_at
    assert first == datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
    assert first.astimezone(ZoneInfo("America/Sao_Paulo")).hour == 9


async def test_invoice_detail_cites_the_frozen_tariff_bands(
    async_session: AsyncSession,
) -> None:
    """A tariff registered later must not change the bands the invoice cites.

    The page explains what the same energy would cost in other bands, so the
    band set it reads has to be the one the invoice was issued under.
    """
    repository, ids, period_id, _ = await ready_to_close(async_session)
    _, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )
    async_session.add_all(
        [
            TariffSnapshotModel(
                id=identifier(11, 3),
                organization_id=ids["organization"],
                name="Tarifa posterior",
                timezone="America/Sao_Paulo",
                source="manual",
                source_reference=None,
                captured_at=datetime(2026, 7, 1, tzinfo=UTC),
                valid_from=date(2026, 6, 1),
                valid_to=None,
            ),
            TariffBandModel(
                id=identifier(12, 9),
                organization_id=ids["organization"],
                tariff_snapshot_id=identifier(11, 3),
                code="faixa_nova",
                rate_cents_per_kwh=1234,
                windows=[
                    {
                        "start_minute": 0,
                        "end_minute": 1440,
                        "weekdays": [0, 1, 2, 3, 4, 5, 6],
                    }
                ],
            ),
        ]
    )
    await async_session.commit()

    invoice, context, bands = await repository.load_invoice_detail(
        ids["organization"], invoices[0].id
    )

    assert invoice.id == invoices[0].id
    assert [band.code for band in bands] == ["fora_ponta"]
    assert [band.rate_cents_per_kwh for band in bands] == [78]
    assert context.tariff_name == "Referência"


async def test_invoice_detail_refuses_another_units_invoice(
    async_session: AsyncSession,
) -> None:
    repository, ids, period_id, _ = await ready_to_close(async_session)
    _, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )
    _, other = invoices

    with pytest.raises(InvoiceNotFound):
        await repository.load_invoice_detail(
            ids["organization"], other.id, unit_id=ids["unit"]
        )


async def test_document_checksum_is_recorded_once_and_verified_after(
    async_session: AsyncSession,
) -> None:
    repository, ids, period_id, _ = await ready_to_close(async_session)
    _, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )
    invoice_id = invoices[0].id

    await repository.record_invoice_document(
        ids["organization"], invoice_id, "a" * 64, 1000
    )
    await repository.record_invoice_document(
        ids["organization"], invoice_id, "a" * 64, 1000
    )
    assert await count_rows(async_session, InvoiceDocumentModel) == 1

    with pytest.raises(DocumentChecksumMismatch):
        await repository.record_invoice_document(
            ids["organization"], invoice_id, "b" * 64, 1000
        )


def _resident_scope(ids: dict[str, UUID], unit_key: str) -> OrganizationScope:
    return OrganizationScope(
        auth_user_id=identifier(7, 1),
        profile_id=ids["profile"],
        organization_id=ids["organization"],
        role=OrganizationRole.RESIDENT,
        unit_id=ids[unit_key],
    )


async def test_resident_scope_sees_only_its_own_invoice(
    async_session: AsyncSession,
) -> None:
    repository, ids, period_id, _ = await ready_to_close(async_session)
    await repository.close_period(ids["organization"], period_id, ids["profile"])

    listed = await ListInvoices(repository).execute(
        _resident_scope(ids, "unit"), period_id=period_id
    )

    assert [invoice.unit_code for invoice in listed] == ["A-101"]


async def test_resident_scope_cannot_read_another_units_invoice(
    async_session: AsyncSession,
) -> None:
    """Another unit's invoice resolves like one that does not exist."""
    repository, ids, period_id, _ = await ready_to_close(async_session)
    _, invoices = await repository.close_period(
        ids["organization"], period_id, ids["profile"]
    )
    own, other = invoices  # A-101 belongs to the resident; B-202 does not.

    scope = _resident_scope(ids, "unit")
    fetched, _, _ = await GetInvoiceDetail(repository).execute(scope, own.id)
    assert fetched.unit_code == "A-101"

    with pytest.raises(InvoiceNotFound):
        await GetInvoiceDetail(repository).execute(scope, other.id)

    with pytest.raises(InvoiceNotFound):
        await RenderInvoiceDocument(repository, PdfInvoiceRenderer()).execute(
            scope, other.id
        )
