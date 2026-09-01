from uuid import UUID

from app.modules.billing.application.ports import BillingRepository
from app.modules.billing.domain.errors import BillingForbidden
from app.modules.billing.domain.invoice import InvoiceView
from app.modules.billing.domain.opinion import (
    ClosingOpinion,
    PersistedFinding,
    analyze_period,
)
from app.modules.billing.domain.period import (
    BillingPeriodView,
    normalize_period_value,
)
from app.modules.billing.domain.readiness import Readiness, evaluate_readiness
from app.modules.billing.domain.rendering import InvoiceDocumentContext
from app.modules.billing.domain.tariff import TariffBand
from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope


def _require_manager(scope: OrganizationScope) -> None:
    if scope.role is not OrganizationRole.MANAGER:
        raise BillingForbidden


def reader_unit_filter(scope: OrganizationScope) -> UUID | None:
    """How far this scope can see into invoices.

    A manager sees the organization; a resident context sees exactly one unit.
    The filter travels into the repository query, so an invoice outside the
    scope resolves like one that does not exist.
    """
    if scope.role is OrganizationRole.MANAGER:
        return None
    if scope.role is OrganizationRole.RESIDENT and scope.unit_id is not None:
        return scope.unit_id
    raise BillingForbidden


class OpenBillingPeriod:
    """Open the period for a month, or return the one already open.

    Opening is idempotent: a manager who imports a second batch for the same
    month must land on the same period, not create a rival one.
    """

    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        period_value: str,
        site_id: UUID | None = None,
    ) -> BillingPeriodView:
        _require_manager(scope)
        return await self.repository.open_period(
            scope.organization_id,
            site_id,
            normalize_period_value(period_value),
        )


class ListBillingPeriods:
    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
    ) -> tuple[BillingPeriodView, ...]:
        _require_manager(scope)
        return await self.repository.list_periods(scope.organization_id)


class GetPeriodReadiness:
    """Answer whether the period can be closed, and what stands in the way."""

    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        period_id: UUID,
    ) -> tuple[BillingPeriodView, Readiness]:
        _require_manager(scope)
        period = await self.repository.get_period(scope.organization_id, period_id)
        dataset = await self.repository.load_dataset(scope.organization_id, period)
        readiness = evaluate_readiness(
            period_value=period.period_value,
            status=period.status,
            sessions=dataset.sessions,
            aggregate_energy_kwh=dataset.aggregate_energy_kwh,
            has_effective_tariff=dataset.has_effective_tariff,
            has_effective_policy=dataset.has_effective_policy,
            critical_finding_count=dataset.critical_finding_count,
            has_closing_opinion=dataset.has_closing_opinion,
            tariff=dataset.tariff,
        )
        return period, readiness


class GenerateClosingOpinion:
    """Run the analytical opinion over the period and record the run.

    The opinion is generated on demand rather than cached, because the data it
    reads changes as the manager assigns sessions. Each run is persisted, so the
    approval can point at exactly the opinion the manager was looking at.
    """

    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        period_id: UUID,
    ) -> tuple[BillingPeriodView, ClosingOpinion, UUID]:
        _require_manager(scope)
        period = await self.repository.get_period(scope.organization_id, period_id)
        dataset = await self.repository.load_opinion_dataset(
            scope.organization_id, period
        )
        opinion = analyze_period(dataset)
        run_id = await self.repository.save_opinion(
            scope.organization_id, period, opinion
        )
        return period, opinion, run_id


class CloseBillingPeriod:
    """Approve the close and issue the period's invoices, atomically.

    The repository re-evaluates every blocker inside the same transaction that
    writes the invoices, so the answer the manager saw on the readiness screen
    cannot silently drift between the check and the approval.
    """

    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        period_id: UUID,
    ) -> tuple[BillingPeriodView, tuple[InvoiceView, ...]]:
        _require_manager(scope)
        return await self.repository.close_period(
            scope.organization_id, period_id, scope.profile_id
        )


class ListInvoices:
    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        period_id: UUID | None = None,
        unit_id: UUID | None = None,
    ) -> tuple[InvoiceView, ...]:
        scope_unit = reader_unit_filter(scope)
        effective_unit = scope_unit if scope_unit is not None else unit_id
        return await self.repository.list_invoices(
            scope.organization_id, period_id=period_id, unit_id=effective_unit
        )


class GetInvoiceDetail:
    """Everything the invoice page states, read under the caller's own scope.

    A resident context narrows this to its own unit through the same filter the
    rest of the module uses, so the page needs no separate resident route.
    """

    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        invoice_id: UUID,
    ) -> tuple[InvoiceView, InvoiceDocumentContext, tuple[TariffBand, ...]]:
        return await self.repository.load_invoice_detail(
            scope.organization_id, invoice_id, unit_id=reader_unit_filter(scope)
        )


class ListFindings:
    """The findings of the period's latest opinion, for the manager to act on."""

    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        period_id: UUID,
    ) -> tuple[PersistedFinding, ...]:
        _require_manager(scope)
        return await self.repository.list_findings(
            scope.organization_id, period_id
        )


class DecideFinding:
    """Record the decision that lets a critical finding stop blocking.

    Deciding is a manager act and is audited with actor, finding and reason.
    The finding is never removed: the close stays explainable afterwards.
    """

    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        period_id: UUID,
        finding_id: UUID,
        note: str,
    ) -> PersistedFinding:
        _require_manager(scope)
        return await self.repository.decide_finding(
            scope.organization_id,
            period_id,
            finding_id,
            scope.profile_id,
            note,
        )
