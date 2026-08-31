from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.infrastructure.models import AuditEventModel
from app.modules.billing.domain.calculation import (
    BillableSession,
    InvoiceDraft,
    calculate_invoices,
)
from app.modules.billing.domain.errors import (
    DocumentChecksumMismatch,
    FindingAlreadyDecided,
    FindingNotFound,
    InvoiceNotFound,
    PeriodCloseBlocked,
    PeriodCloseConflict,
    PeriodNotFound,
    SiteNotFound,
)
from app.modules.billing.domain.invoice import InvoiceItemView, InvoiceView
from app.modules.billing.domain.opinion import (
    ClosingOpinion,
    OpinionDataset,
    OpinionSession,
    PersistedFinding,
)
from app.modules.billing.domain.period import (
    BillingPeriodView,
    PeriodStatus,
    period_bounds,
)
from app.modules.billing.domain.policy import BillingPolicy
from app.modules.billing.domain.readiness import (
    PeriodDataset,
    PeriodSession,
    evaluate_readiness,
)
from app.modules.billing.domain.rendering import InvoiceDocumentContext
from app.modules.billing.domain.tariff import TariffBand, TariffSnapshot, TariffWindow
from app.modules.billing.infrastructure.models import (
    AnalyticalFindingModel,
    BillingPeriodModel,
    BillingPolicyModel,
    ChargerEnergyReadingModel,
    InsightRunModel,
    InvoiceDocumentModel,
    InvoiceItemModel,
    InvoiceModel,
    TariffBandModel,
    TariffSnapshotModel,
)
from app.modules.ingestion.infrastructure.models import ChargingSessionModel
from app.modules.organizations.infrastructure.models import (
    ChargerModel,
    MembershipModel,
    OrganizationModel,
    ProfileModel,
    SiteModel,
    UnitModel,
)
from app.modules.sessions.infrastructure.models import SessionAssignmentModel

CRITICAL = "critical"


class SqlAlchemyBillingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _resolve_site(
        self,
        organization_id: UUID,
        site_id: UUID | None,
    ) -> SiteModel:
        statement = select(SiteModel).where(
            SiteModel.organization_id == organization_id
        )
        if site_id is not None:
            statement = statement.where(SiteModel.id == site_id)
        site = (
            await self.session.execute(statement.order_by(SiteModel.name).limit(1))
        ).scalar_one_or_none()
        if site is None:
            raise SiteNotFound
        return site

    def _to_view(
        self,
        period: BillingPeriodModel,
        site: SiteModel,
        approved_by_name: str | None,
    ) -> BillingPeriodView:
        return BillingPeriodView(
            id=period.id,
            site_id=period.site_id,
            site_name=site.name,
            timezone=site.timezone,
            period_value=period.period_value,
            status=period.status,
            approved_at=period.approved_at,
            approved_by_name=approved_by_name,
            tariff_snapshot_id=period.tariff_snapshot_id,
            billing_policy_id=period.billing_policy_id,
            eligible_energy_kwh=period.eligible_energy_kwh,
            invoiced_energy_kwh=period.invoiced_energy_kwh,
            aggregate_energy_kwh=period.aggregate_energy_kwh,
        )

    async def open_period(
        self,
        organization_id: UUID,
        site_id: UUID | None,
        period_value: str,
    ) -> BillingPeriodView:
        site = await self._resolve_site(organization_id, site_id)
        existing = (
            await self.session.execute(
                select(BillingPeriodModel).where(
                    BillingPeriodModel.organization_id == organization_id,
                    BillingPeriodModel.site_id == site.id,
                    BillingPeriodModel.period_value == period_value,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return self._to_view(existing, site, None)

        period = BillingPeriodModel(
            id=uuid4(),
            organization_id=organization_id,
            site_id=site.id,
            period_value=period_value,
            status=PeriodStatus.OPEN.value,
        )
        self.session.add(period)
        await self.session.commit()
        await self.session.refresh(period)
        return self._to_view(period, site, None)

    async def list_periods(
        self,
        organization_id: UUID,
    ) -> tuple[BillingPeriodView, ...]:
        rows = (
            await self.session.execute(
                select(BillingPeriodModel, SiteModel, ProfileModel.display_name)
                .join(
                    SiteModel,
                    and_(
                        SiteModel.id == BillingPeriodModel.site_id,
                        SiteModel.organization_id == organization_id,
                    ),
                )
                .outerjoin(
                    ProfileModel, ProfileModel.id == BillingPeriodModel.approved_by
                )
                .where(BillingPeriodModel.organization_id == organization_id)
                .order_by(BillingPeriodModel.period_value.desc())
            )
        ).all()
        return tuple(
            self._to_view(period, site, approver) for period, site, approver in rows
        )

    async def get_period(
        self,
        organization_id: UUID,
        period_id: UUID,
    ) -> BillingPeriodView:
        row = (
            await self.session.execute(
                select(BillingPeriodModel, SiteModel, ProfileModel.display_name)
                .join(
                    SiteModel,
                    and_(
                        SiteModel.id == BillingPeriodModel.site_id,
                        SiteModel.organization_id == organization_id,
                    ),
                )
                .outerjoin(
                    ProfileModel, ProfileModel.id == BillingPeriodModel.approved_by
                )
                .where(
                    BillingPeriodModel.id == period_id,
                    BillingPeriodModel.organization_id == organization_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise PeriodNotFound
        period, site, approver = row
        return self._to_view(period, site, approver)

    async def load_dataset(
        self,
        organization_id: UUID,
        period: BillingPeriodView,
    ) -> PeriodDataset:
        start, end = period_bounds(period.period_value, period.timezone)

        session_rows = (
            await self.session.execute(
                select(ChargingSessionModel, SessionAssignmentModel.unit_id)
                .outerjoin(
                    SessionAssignmentModel,
                    and_(
                        SessionAssignmentModel.organization_id == organization_id,
                        SessionAssignmentModel.charging_session_id
                        == ChargingSessionModel.id,
                    ),
                )
                .where(
                    ChargingSessionModel.organization_id == organization_id,
                    ChargingSessionModel.site_id == period.site_id,
                    ChargingSessionModel.started_at >= start,
                    ChargingSessionModel.started_at < end,
                )
                .order_by(ChargingSessionModel.started_at)
            )
        ).all()
        sessions = tuple(
            PeriodSession(
                id=row.id,
                unit_id=unit_id,
                started_at=row.started_at,
                ended_at=row.ended_at,
                energy_kwh=row.energy_kwh,
                status=row.status,
            )
            for row, unit_id in session_rows
        )

        aggregate = (
            await self.session.execute(
                select(func.sum(ChargerEnergyReadingModel.energy_kwh)).where(
                    ChargerEnergyReadingModel.organization_id == organization_id,
                    ChargerEnergyReadingModel.period_type == "day",
                    ChargerEnergyReadingModel.period_value.startswith(
                        period.period_value
                    ),
                )
            )
        ).scalar_one_or_none()

        year, month = (int(part) for part in period.period_value.split("-"))
        first_day = date(year, month, 1)
        critical = (
            await self.session.execute(
                select(func.count())
                .select_from(AnalyticalFindingModel)
                .join(
                    InsightRunModel,
                    InsightRunModel.id == AnalyticalFindingModel.insight_run_id,
                )
                .where(
                    AnalyticalFindingModel.organization_id == organization_id,
                    AnalyticalFindingModel.severity == CRITICAL,
                    AnalyticalFindingModel.resolved_at.is_(None),
                    InsightRunModel.billing_period_id == period.id,
                )
            )
        ).scalar_one()

        return PeriodDataset(
            sessions=sessions,
            aggregate_energy_kwh=aggregate,
            has_effective_tariff=await self._has_effective(
                TariffSnapshotModel, organization_id, first_day
            ),
            has_effective_policy=await self._has_effective(
                BillingPolicyModel, organization_id, first_day
            ),
            critical_finding_count=critical,
            has_closing_opinion=(
                await self._latest_opinion_run_id(organization_id, period.id)
            )
            is not None,
        )

    async def _has_effective(
        self,
        model: type[TariffSnapshotModel] | type[BillingPolicyModel],
        organization_id: UUID,
        day: date,
    ) -> bool:
        found = (
            await self.session.execute(
                select(model.id)
                .where(
                    model.organization_id == organization_id,
                    model.valid_from <= day,
                    or_(model.valid_to.is_(None), model.valid_to >= day),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return found is not None

    async def load_opinion_dataset(
        self,
        organization_id: UUID,
        period: BillingPeriodView,
    ) -> OpinionDataset:
        """Sessions with their unit label, plus the charger's nameplate rating.

        The label travels with the session so a finding can name the unit in
        plain language instead of showing a UUID to a building manager.
        """
        start, end = period_bounds(period.period_value, period.timezone)
        rows = (
            await self.session.execute(
                select(
                    ChargingSessionModel,
                    SessionAssignmentModel.unit_id,
                    UnitModel.code,
                )
                .outerjoin(
                    SessionAssignmentModel,
                    and_(
                        SessionAssignmentModel.organization_id == organization_id,
                        SessionAssignmentModel.charging_session_id
                        == ChargingSessionModel.id,
                    ),
                )
                .outerjoin(
                    UnitModel,
                    and_(
                        UnitModel.id == SessionAssignmentModel.unit_id,
                        UnitModel.organization_id == organization_id,
                    ),
                )
                .where(
                    ChargingSessionModel.organization_id == organization_id,
                    ChargingSessionModel.site_id == period.site_id,
                    ChargingSessionModel.started_at >= start,
                    ChargingSessionModel.started_at < end,
                )
                .order_by(ChargingSessionModel.started_at)
            )
        ).all()

        nominal = (
            await self.session.execute(
                select(ChargerModel.nominal_power_kw)
                .where(
                    ChargerModel.organization_id == organization_id,
                    ChargerModel.site_id == period.site_id,
                )
                .order_by(ChargerModel.nominal_power_kw.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        aggregate = (
            await self.session.execute(
                select(func.sum(ChargerEnergyReadingModel.energy_kwh)).where(
                    ChargerEnergyReadingModel.organization_id == organization_id,
                    ChargerEnergyReadingModel.period_type == "day",
                    ChargerEnergyReadingModel.period_value.startswith(
                        period.period_value
                    ),
                )
            )
        ).scalar_one_or_none()

        return OpinionDataset(
            sessions=tuple(
                OpinionSession(
                    id=row.id,
                    unit_id=unit_id,
                    unit_label=unit_code,
                    started_at=row.started_at,
                    ended_at=row.ended_at,
                    energy_kwh=row.energy_kwh,
                    status=row.status,
                )
                for row, unit_id, unit_code in rows
            ),
            nominal_power_kw=nominal if nominal is not None else Decimal(0),
            aggregate_energy_kwh=aggregate,
        )

    async def save_opinion(
        self,
        organization_id: UUID,
        period: BillingPeriodView,
        opinion: ClosingOpinion,
    ) -> UUID:
        """Persist the run and its findings so the approval references what was seen."""
        run = InsightRunModel(
            id=uuid4(),
            organization_id=organization_id,
            billing_period_id=period.id,
            kind="closing_opinion",
            algorithm_version=opinion.algorithm_version,
            parameters=dict(opinion.parameters),
            dataset_checksum=opinion.dataset_checksum,
            sample_size=opinion.sample_size,
            conclusion=opinion.conclusion.value,
            severity=opinion.severity.value,
            confidence=opinion.confidence.value,
            recommendation=opinion.recommendation,
            generated_at=datetime.now(UTC),
        )
        self.session.add(run)
        await self.session.flush()

        for finding in opinion.findings:
            self.session.add(
                AnalyticalFindingModel(
                    id=uuid4(),
                    organization_id=organization_id,
                    insight_run_id=run.id,
                    charging_session_id=finding.charging_session_id,
                    code=finding.code,
                    severity=finding.severity.value,
                    confidence=finding.confidence.value,
                    explanation=finding.explanation,
                    evidence=dict(finding.evidence),
                )
            )
        await self.session.commit()
        return run.id

    async def _latest_opinion_run_id(
        self,
        organization_id: UUID,
        period_id: UUID,
    ) -> UUID | None:
        return (
            await self.session.execute(
                select(InsightRunModel.id)
                .where(
                    InsightRunModel.organization_id == organization_id,
                    InsightRunModel.billing_period_id == period_id,
                    InsightRunModel.kind == "closing_opinion",
                )
                .order_by(InsightRunModel.generated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _effective_tariff(
        self,
        organization_id: UUID,
        day: date,
    ) -> tuple[UUID, TariffSnapshot]:
        """Load the tariff in force on `day` and rebuild the domain object.

        The most recent `valid_from` wins when several snapshots cover the day,
        so registering a correction supersedes without touching the old row.
        """
        row = (
            await self.session.execute(
                select(TariffSnapshotModel)
                .where(
                    TariffSnapshotModel.organization_id == organization_id,
                    TariffSnapshotModel.valid_from <= day,
                    or_(
                        TariffSnapshotModel.valid_to.is_(None),
                        TariffSnapshotModel.valid_to >= day,
                    ),
                )
                .order_by(TariffSnapshotModel.valid_from.desc())
                .limit(1)
            )
        ).scalar_one()
        bands = await self._bands_of(organization_id, row.id)
        return row.id, TariffSnapshot(
            name=row.name, timezone=row.timezone, bands=bands
        )

    async def _bands_of(
        self,
        organization_id: UUID,
        tariff_snapshot_id: UUID,
    ) -> tuple[TariffBand, ...]:
        """Rebuild the bands of one snapshot, addressed by its identifier.

        Reading by identifier rather than by date is what lets an issued
        invoice keep citing the tariff it was calculated with, even after a
        newer snapshot supersedes it.
        """
        band_rows = (
            (
                await self.session.execute(
                    select(TariffBandModel)
                    .where(
                        TariffBandModel.organization_id == organization_id,
                        TariffBandModel.tariff_snapshot_id == tariff_snapshot_id,
                    )
                    .order_by(TariffBandModel.code)
                )
            )
            .scalars()
            .all()
        )
        return tuple(
            TariffBand(
                code=band.code,
                rate_cents_per_kwh=band.rate_cents_per_kwh,
                windows=tuple(
                    TariffWindow(
                        start_minute=int(window["start_minute"]),
                        end_minute=int(window["end_minute"]),
                        weekdays=frozenset(
                            int(weekday) for weekday in window["weekdays"]
                        ),
                    )
                    for window in band.windows
                ),
            )
            for band in band_rows
        )

    async def _effective_policy(
        self,
        organization_id: UUID,
        day: date,
    ) -> tuple[UUID, BillingPolicy]:
        row = (
            await self.session.execute(
                select(BillingPolicyModel)
                .where(
                    BillingPolicyModel.organization_id == organization_id,
                    BillingPolicyModel.valid_from <= day,
                    or_(
                        BillingPolicyModel.valid_to.is_(None),
                        BillingPolicyModel.valid_to >= day,
                    ),
                )
                .order_by(BillingPolicyModel.valid_from.desc())
                .limit(1)
            )
        ).scalar_one()
        return row.id, BillingPolicy(
            name=row.name,
            infra_fee_cents=row.infra_fee_cents,
            loss_basis_points=row.loss_basis_points,
        )

    async def _resident_contacts(self, organization_id: UUID) -> dict[UUID, str]:
        """First resident name per unit, deterministically, for `contact_label`."""
        rows = (
            await self.session.execute(
                select(MembershipModel.unit_id, ProfileModel.display_name)
                .join(ProfileModel, ProfileModel.id == MembershipModel.profile_id)
                .where(
                    MembershipModel.organization_id == organization_id,
                    MembershipModel.role == "resident",
                    MembershipModel.unit_id.is_not(None),
                )
                .order_by(ProfileModel.display_name)
            )
        ).all()
        contacts: dict[UUID, str] = {}
        for unit_id, display_name in rows:
            if unit_id is not None and unit_id not in contacts:
                contacts[unit_id] = display_name
        return contacts

    async def close_period(
        self,
        organization_id: UUID,
        period_id: UUID,
        approved_by: UUID,
    ) -> tuple[BillingPeriodView, tuple[InvoiceView, ...]]:
        """Section 7 of the design, as one transaction.

        The period row is claimed with a compare-and-set from `open` to
        `closing`, so two concurrent closes cannot both proceed: on PostgreSQL
        the second UPDATE waits on the row lock and then matches zero rows; on
        SQLite the statements serialize. The loser gets a conflict and the
        winner's work is untouched. Any failure before commit rolls the whole
        close back, including the claim itself.
        """
        row = (
            await self.session.execute(
                select(BillingPeriodModel, SiteModel)
                .join(
                    SiteModel,
                    and_(
                        SiteModel.id == BillingPeriodModel.site_id,
                        SiteModel.organization_id == organization_id,
                    ),
                )
                .where(
                    BillingPeriodModel.id == period_id,
                    BillingPeriodModel.organization_id == organization_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise PeriodNotFound
        period, site = row

        claim = cast(
            "CursorResult[Any]",
            await self.session.execute(
                update(BillingPeriodModel)
                .where(
                    BillingPeriodModel.id == period_id,
                    BillingPeriodModel.organization_id == organization_id,
                    BillingPeriodModel.status == PeriodStatus.OPEN.value,
                )
                .values(status=PeriodStatus.CLOSING.value)
            ),
        )
        if claim.rowcount == 0:
            await self.session.rollback()
            current = (
                await self.session.execute(
                    select(BillingPeriodModel.status).where(
                        BillingPeriodModel.id == period_id,
                        BillingPeriodModel.organization_id == organization_id,
                    )
                )
            ).scalar_one()
            raise PeriodCloseConflict(current)

        view = self._to_view(period, site, None)
        dataset = await self.load_dataset(organization_id, view)
        readiness = evaluate_readiness(
            period_value=period.period_value,
            status=PeriodStatus.OPEN.value,
            sessions=dataset.sessions,
            aggregate_energy_kwh=dataset.aggregate_energy_kwh,
            has_effective_tariff=dataset.has_effective_tariff,
            has_effective_policy=dataset.has_effective_policy,
            critical_finding_count=dataset.critical_finding_count,
            has_closing_opinion=dataset.has_closing_opinion,
        )
        if readiness.blockers:
            await self.session.rollback()
            raise PeriodCloseBlocked(readiness.blockers)

        year, month = (int(part) for part in period.period_value.split("-"))
        first_day = date(year, month, 1)
        tariff_id, tariff = await self._effective_tariff(organization_id, first_day)
        policy_id, policy = await self._effective_policy(organization_id, first_day)
        opinion_run_id = await self._latest_opinion_run_id(organization_id, period_id)
        if opinion_run_id is None:  # pragma: no cover - blocked above
            await self.session.rollback()
            raise PeriodCloseBlocked(readiness.blockers)

        unit_rows = (
            (
                await self.session.execute(
                    select(UnitModel)
                    .where(UnitModel.organization_id == organization_id)
                    .order_by(UnitModel.code)
                )
            )
            .scalars()
            .all()
        )
        contacts = await self._resident_contacts(organization_id)

        billable = tuple(
            item for item in dataset.sessions if item.is_billable
        )
        eligible_sessions = tuple(
            BillableSession(
                id=item.id,
                unit_id=item.unit_id,
                started_at=item.started_at,
                ended_at=item.ended_at,
                energy_kwh=item.energy_kwh,
            )
            for item in billable
            if item.unit_id is not None
        )
        drafts: tuple[InvoiceDraft, ...] = calculate_invoices(
            eligible_sessions,
            tariff,
            policy,
            tuple(unit.id for unit in unit_rows),
        )

        issued_at = datetime.now(UTC)
        units_by_id = {unit.id: unit for unit in unit_rows}
        for draft in drafts:
            unit = units_by_id[draft.unit_id]
            invoice_id = uuid4()
            self.session.add(
                InvoiceModel(
                    id=invoice_id,
                    organization_id=organization_id,
                    billing_period_id=period_id,
                    unit_id=unit.id,
                    number=f"FAT-{period.period_value}-{unit.code}",
                    contact_label=contacts.get(unit.id, unit.display_name),
                    energy_kwh=draft.energy_kwh,
                    energy_value_cents=draft.energy_value_cents,
                    infra_fee_cents=draft.infra_fee_cents,
                    loss_share_cents=draft.loss_share_cents,
                    total_cents=draft.total_cents,
                    issued_at=issued_at,
                )
            )
            for item in draft.items:
                self.session.add(
                    InvoiceItemModel(
                        id=uuid4(),
                        organization_id=organization_id,
                        invoice_id=invoice_id,
                        charging_session_id=item.charging_session_id,
                        started_at=item.started_at,
                        ended_at=item.ended_at,
                        energy_kwh=item.energy_kwh,
                        band_code=item.band_code,
                        rate_cents_per_kwh=item.rate_cents_per_kwh,
                        value_cents=item.value_cents,
                    )
                )

        billed_ids = [item.id for item in billable]
        if billed_ids:
            await self.session.execute(
                update(ChargingSessionModel)
                .where(
                    ChargingSessionModel.organization_id == organization_id,
                    ChargingSessionModel.id.in_(billed_ids),
                )
                .values(status="billed")
            )

        invoiced_energy = sum(
            (draft.energy_kwh for draft in drafts), Decimal(0)
        )
        period.status = PeriodStatus.CLOSED.value
        period.tariff_snapshot_id = tariff_id
        period.billing_policy_id = policy_id
        period.closing_insight_run_id = opinion_run_id
        period.approved_by = approved_by
        period.approved_at = issued_at
        period.eligible_energy_kwh = readiness.billable_energy_kwh
        period.invoiced_energy_kwh = invoiced_energy
        period.aggregate_energy_kwh = dataset.aggregate_energy_kwh

        self.session.add(
            AuditEventModel(
                organization_id=organization_id,
                actor_profile_id=approved_by,
                occurred_at=issued_at,
                event_type="billing_period_closed",
                entity_type="billing_period",
                entity_id=period_id,
                metadata_json={
                    "period_value": period.period_value,
                    "invoice_count": len(drafts),
                    "invoiced_total_cents": sum(
                        draft.total_cents for draft in drafts
                    ),
                    "tariff_snapshot_id": str(tariff_id),
                    "billing_policy_id": str(policy_id),
                    "closing_insight_run_id": str(opinion_run_id),
                },
            )
        )
        await self.session.commit()

        closed_view = await self.get_period(organization_id, period_id)
        invoices = await self.list_invoices(organization_id, period_id=period_id)
        return closed_view, invoices

    async def list_invoices(
        self,
        organization_id: UUID,
        period_id: UUID | None = None,
        unit_id: UUID | None = None,
    ) -> tuple[InvoiceView, ...]:
        statement = (
            select(InvoiceModel, BillingPeriodModel.period_value, UnitModel)
            .join(
                BillingPeriodModel,
                and_(
                    BillingPeriodModel.id == InvoiceModel.billing_period_id,
                    BillingPeriodModel.organization_id == organization_id,
                ),
            )
            .join(
                UnitModel,
                and_(
                    UnitModel.id == InvoiceModel.unit_id,
                    UnitModel.organization_id == organization_id,
                ),
            )
            .where(InvoiceModel.organization_id == organization_id)
            .order_by(
                BillingPeriodModel.period_value.desc(),
                UnitModel.code,
            )
        )
        if period_id is not None:
            statement = statement.where(
                InvoiceModel.billing_period_id == period_id
            )
        if unit_id is not None:
            statement = statement.where(InvoiceModel.unit_id == unit_id)
        rows = (await self.session.execute(statement)).all()
        items_by_invoice = await self._items_by_invoice(
            organization_id, [invoice.id for invoice, _, _ in rows]
        )
        return tuple(
            self._to_invoice_view(
                invoice,
                period_value,
                unit,
                items_by_invoice.get(invoice.id, ()),
            )
            for invoice, period_value, unit in rows
        )

    async def get_invoice(
        self,
        organization_id: UUID,
        invoice_id: UUID,
        unit_id: UUID | None = None,
    ) -> InvoiceView:
        statement = (
            select(InvoiceModel, BillingPeriodModel.period_value, UnitModel)
            .join(
                BillingPeriodModel,
                and_(
                    BillingPeriodModel.id == InvoiceModel.billing_period_id,
                    BillingPeriodModel.organization_id == organization_id,
                ),
            )
            .join(
                UnitModel,
                and_(
                    UnitModel.id == InvoiceModel.unit_id,
                    UnitModel.organization_id == organization_id,
                ),
            )
            .where(
                InvoiceModel.organization_id == organization_id,
                InvoiceModel.id == invoice_id,
            )
        )
        if unit_id is not None:
            statement = statement.where(InvoiceModel.unit_id == unit_id)
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            raise InvoiceNotFound
        invoice, period_value, unit = row
        items = await self._items_by_invoice(organization_id, [invoice.id])
        return self._to_invoice_view(
            invoice, period_value, unit, items.get(invoice.id, ())
        )

    async def _items_by_invoice(
        self,
        organization_id: UUID,
        invoice_ids: list[UUID],
    ) -> dict[UUID, tuple[InvoiceItemView, ...]]:
        if not invoice_ids:
            return {}
        rows = (
            (
                await self.session.execute(
                    select(InvoiceItemModel)
                    .where(
                        InvoiceItemModel.organization_id == organization_id,
                        InvoiceItemModel.invoice_id.in_(invoice_ids),
                    )
                    .order_by(
                        InvoiceItemModel.started_at,
                        InvoiceItemModel.charging_session_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        grouped: dict[UUID, list[InvoiceItemView]] = {}
        for item in rows:
            grouped.setdefault(item.invoice_id, []).append(
                InvoiceItemView(
                    id=item.id,
                    charging_session_id=item.charging_session_id,
                    started_at=item.started_at,
                    ended_at=item.ended_at,
                    energy_kwh=item.energy_kwh,
                    band_code=item.band_code,
                    rate_cents_per_kwh=item.rate_cents_per_kwh,
                    value_cents=item.value_cents,
                )
            )
        return {key: tuple(value) for key, value in grouped.items()}

    def _to_invoice_view(
        self,
        invoice: InvoiceModel,
        period_value: str,
        unit: UnitModel,
        items: tuple[InvoiceItemView, ...],
    ) -> InvoiceView:
        return InvoiceView(
            id=invoice.id,
            number=invoice.number,
            billing_period_id=invoice.billing_period_id,
            period_value=period_value,
            unit_id=invoice.unit_id,
            unit_code=unit.code,
            unit_name=unit.display_name,
            contact_label=invoice.contact_label,
            energy_kwh=invoice.energy_kwh,
            energy_value_cents=invoice.energy_value_cents,
            infra_fee_cents=invoice.infra_fee_cents,
            loss_share_cents=invoice.loss_share_cents,
            total_cents=invoice.total_cents,
            issued_at=invoice.issued_at,
            items=items,
        )

    async def load_invoice_document_context(
        self,
        organization_id: UUID,
        invoice_id: UUID,
        unit_id: UUID | None = None,
    ) -> tuple[InvoiceView, InvoiceDocumentContext]:
        """The persisted invoice plus the frozen records the document cites.

        The tariff and policy come from the identifiers frozen on the period at
        close, not from whatever is effective today: a tariff registered after
        the close must not change a line of an issued document.
        """
        invoice = await self.get_invoice(organization_id, invoice_id, unit_id)
        row = (
            await self.session.execute(
                select(
                    BillingPeriodModel,
                    SiteModel,
                    OrganizationModel.name,
                )
                .join(
                    SiteModel,
                    and_(
                        SiteModel.id == BillingPeriodModel.site_id,
                        SiteModel.organization_id == organization_id,
                    ),
                )
                .join(
                    OrganizationModel,
                    OrganizationModel.id == BillingPeriodModel.organization_id,
                )
                .where(
                    BillingPeriodModel.id == invoice.billing_period_id,
                    BillingPeriodModel.organization_id == organization_id,
                )
            )
        ).one()
        period, site, organization_name = row
        tariff = await self.session.get(
            TariffSnapshotModel, period.tariff_snapshot_id
        )
        policy = await self.session.get(
            BillingPolicyModel, period.billing_policy_id
        )
        if tariff is None or policy is None:  # pragma: no cover - frozen at close
            raise PeriodNotFound
        provenance_rows = (
            (
                await self.session.execute(
                    select(ChargingSessionModel.provenance)
                    .join(
                        InvoiceItemModel,
                        and_(
                            InvoiceItemModel.charging_session_id
                            == ChargingSessionModel.id,
                            InvoiceItemModel.organization_id == organization_id,
                        ),
                    )
                    .where(
                        InvoiceItemModel.invoice_id == invoice.id,
                        ChargingSessionModel.organization_id == organization_id,
                    )
                    .distinct()
                    .order_by(ChargingSessionModel.provenance)
                )
            )
            .scalars()
            .all()
        )
        context = InvoiceDocumentContext(
            organization_name=organization_name,
            site_name=site.name,
            timezone=site.timezone,
            tariff_name=tariff.name,
            tariff_source=tariff.source,
            tariff_source_reference=tariff.source_reference,
            tariff_valid_from=tariff.valid_from,
            tariff_valid_to=tariff.valid_to,
            policy_name=policy.name,
            infra_fee_cents=policy.infra_fee_cents,
            loss_basis_points=policy.loss_basis_points,
            provenances=tuple(provenance_rows),
        )
        return invoice, context

    async def list_findings(
        self,
        organization_id: UUID,
        period_id: UUID,
    ) -> tuple[PersistedFinding, ...]:
        """The findings of this period's latest opinion, with their decisions.

        Unresolved criticals are what hold the close, so the manager needs them
        addressable, not just readable in a generated report.
        """
        run_id = await self._latest_opinion_run_id(organization_id, period_id)
        if run_id is None:
            return ()
        rows = (
            await self.session.execute(
                select(AnalyticalFindingModel, ProfileModel.display_name)
                .outerjoin(
                    ProfileModel,
                    ProfileModel.id == AnalyticalFindingModel.resolved_by,
                )
                .where(
                    AnalyticalFindingModel.organization_id == organization_id,
                    AnalyticalFindingModel.insight_run_id == run_id,
                )
                .order_by(
                    AnalyticalFindingModel.severity,
                    AnalyticalFindingModel.code,
                )
            )
        ).all()
        return tuple(
            PersistedFinding(
                id=finding.id,
                code=finding.code,
                severity=finding.severity,
                confidence=finding.confidence,
                explanation=finding.explanation,
                evidence={
                    key: str(value) for key, value in finding.evidence.items()
                },
                charging_session_id=finding.charging_session_id,
                resolved_at=finding.resolved_at,
                resolved_by_name=resolver,
                resolution_note=finding.resolution_note,
            )
            for finding, resolver in rows
        )

    async def decide_finding(
        self,
        organization_id: UUID,
        period_id: UUID,
        finding_id: UUID,
        profile_id: UUID,
        note: str,
    ) -> PersistedFinding:
        """Record who accepted a finding and why, and stop it blocking.

        The finding is never deleted or edited: the decision is written beside
        it, so the close remains explainable after the fact.
        """
        run_id = await self._latest_opinion_run_id(organization_id, period_id)
        finding = (
            await self.session.execute(
                select(AnalyticalFindingModel).where(
                    AnalyticalFindingModel.id == finding_id,
                    AnalyticalFindingModel.organization_id == organization_id,
                    AnalyticalFindingModel.insight_run_id == run_id,
                )
            )
        ).scalar_one_or_none()
        if finding is None:
            raise FindingNotFound
        if finding.resolved_at is not None:
            raise FindingAlreadyDecided
        decided_at = datetime.now(UTC)
        finding.resolved_at = decided_at
        finding.resolved_by = profile_id
        finding.resolution_note = note
        self.session.add(
            AuditEventModel(
                organization_id=organization_id,
                actor_profile_id=profile_id,
                occurred_at=decided_at,
                event_type="analytical_finding_decided",
                entity_type="analytical_finding",
                entity_id=finding_id,
                metadata_json={
                    "billing_period_id": str(period_id),
                    "code": finding.code,
                    "severity": finding.severity,
                    "note": note,
                },
            )
        )
        await self.session.commit()
        decided = [
            item
            for item in await self.list_findings(organization_id, period_id)
            if item.id == finding_id
        ]
        return decided[0]

    async def load_invoice_detail(
        self,
        organization_id: UUID,
        invoice_id: UUID,
        unit_id: UUID | None = None,
    ) -> tuple[InvoiceView, InvoiceDocumentContext, tuple[TariffBand, ...]]:
        """The invoice, what its document cites, and the frozen tariff's bands.

        The bands are the whole tariff the invoice was issued under, not only
        the ones its sessions fell into, so the screen can answer what the same
        energy would have cost elsewhere without inventing a baseline.
        """
        invoice, context = await self.load_invoice_document_context(
            organization_id, invoice_id, unit_id
        )
        period = (
            await self.session.execute(
                select(BillingPeriodModel).where(
                    BillingPeriodModel.id == invoice.billing_period_id,
                    BillingPeriodModel.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if period is None or period.tariff_snapshot_id is None:
            raise PeriodNotFound
        bands = await self._bands_of(organization_id, period.tariff_snapshot_id)
        return invoice, context, bands

    async def record_invoice_document(
        self,
        organization_id: UUID,
        invoice_id: UUID,
        checksum: str,
        byte_size: int,
    ) -> None:
        """Record the first render; prove every later one identical.

        The stored checksum is the document's identity: a later render that
        hashes differently is a defect and is refused rather than served.
        """
        existing = (
            await self.session.execute(
                select(InvoiceDocumentModel).where(
                    InvoiceDocumentModel.organization_id == organization_id,
                    InvoiceDocumentModel.invoice_id == invoice_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.checksum != checksum:
                raise DocumentChecksumMismatch(existing.checksum, checksum)
            return
        self.session.add(
            InvoiceDocumentModel(
                id=uuid4(),
                organization_id=organization_id,
                invoice_id=invoice_id,
                checksum=checksum,
                byte_size=byte_size,
                generated_at=datetime.now(UTC),
            )
        )
        await self.session.commit()
