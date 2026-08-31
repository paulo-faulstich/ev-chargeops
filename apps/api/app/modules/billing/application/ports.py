from typing import Protocol
from uuid import UUID

from app.modules.billing.domain.invoice import InvoiceView
from app.modules.billing.domain.opinion import (
    ClosingOpinion,
    OpinionDataset,
    PersistedFinding,
)
from app.modules.billing.domain.period import BillingPeriodView
from app.modules.billing.domain.readiness import PeriodDataset
from app.modules.billing.domain.rendering import InvoiceDocumentContext
from app.modules.billing.domain.tariff import TariffBand


class BillingRepository(Protocol):
    async def open_period(
        self,
        organization_id: UUID,
        site_id: UUID | None,
        period_value: str,
    ) -> BillingPeriodView: ...

    async def list_periods(
        self,
        organization_id: UUID,
    ) -> tuple[BillingPeriodView, ...]: ...

    async def get_period(
        self,
        organization_id: UUID,
        period_id: UUID,
    ) -> BillingPeriodView: ...

    async def load_dataset(
        self,
        organization_id: UUID,
        period: BillingPeriodView,
    ) -> PeriodDataset: ...

    async def load_opinion_dataset(
        self,
        organization_id: UUID,
        period: BillingPeriodView,
    ) -> OpinionDataset: ...

    async def save_opinion(
        self,
        organization_id: UUID,
        period: BillingPeriodView,
        opinion: ClosingOpinion,
    ) -> UUID: ...

    async def close_period(
        self,
        organization_id: UUID,
        period_id: UUID,
        approved_by: UUID,
    ) -> tuple[BillingPeriodView, tuple[InvoiceView, ...]]: ...

    async def list_invoices(
        self,
        organization_id: UUID,
        period_id: UUID | None = None,
        unit_id: UUID | None = None,
    ) -> tuple[InvoiceView, ...]: ...

    async def get_invoice(
        self,
        organization_id: UUID,
        invoice_id: UUID,
        unit_id: UUID | None = None,
    ) -> InvoiceView: ...

    async def load_invoice_document_context(
        self,
        organization_id: UUID,
        invoice_id: UUID,
        unit_id: UUID | None = None,
    ) -> tuple[InvoiceView, InvoiceDocumentContext]: ...

    async def list_findings(
        self,
        organization_id: UUID,
        period_id: UUID,
    ) -> tuple[PersistedFinding, ...]: ...

    async def decide_finding(
        self,
        organization_id: UUID,
        period_id: UUID,
        finding_id: UUID,
        profile_id: UUID,
        note: str,
    ) -> PersistedFinding: ...

    async def load_invoice_detail(
        self,
        organization_id: UUID,
        invoice_id: UUID,
        unit_id: UUID | None = None,
    ) -> tuple[InvoiceView, InvoiceDocumentContext, tuple[TariffBand, ...]]: ...

    async def record_invoice_document(
        self,
        organization_id: UUID,
        invoice_id: UUID,
        checksum: str,
        byte_size: int,
    ) -> None: ...
