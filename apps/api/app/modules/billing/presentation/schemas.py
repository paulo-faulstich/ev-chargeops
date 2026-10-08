from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.modules.billing.domain.calculation import energy_value_in_band
from app.modules.billing.domain.invoice import InvoiceItemView, InvoiceView
from app.modules.billing.domain.opinion import (
    ClosingOpinion,
    Finding,
    PersistedFinding,
)
from app.modules.billing.domain.period import BillingPeriodView
from app.modules.billing.domain.readiness import Blocker, Readiness
from app.modules.billing.domain.rendering import (
    InvoiceDocumentContext,
    provenance_label,
)
from app.modules.billing.domain.tariff import TariffBand
from app.modules.billing.domain.vocabulary import (
    band_hours,
    band_label,
    tariff_source_label,
)
from app.modules.ingestion.presentation.schemas import ApiSchema


class BillingPeriodResponse(ApiSchema):
    id: UUID
    site_id: UUID
    site_name: str
    timezone: str
    period_value: str
    status: str
    approved_at: datetime | None
    approved_by_name: str | None
    tariff_snapshot_id: UUID | None
    billing_policy_id: UUID | None
    eligible_energy_kwh: Decimal | None
    invoiced_energy_kwh: Decimal | None
    aggregate_energy_kwh: Decimal | None

    @classmethod
    def from_view(cls, view: BillingPeriodView) -> "BillingPeriodResponse":
        return cls.model_validate(view, from_attributes=True)


class BillingPeriodListResponse(ApiSchema):
    items: list[BillingPeriodResponse]


class OpenBillingPeriodRequest(ApiSchema):
    period_value: str
    site_id: UUID | None = None


class BlockerResponse(ApiSchema):
    code: str
    detail: str
    count: int

    @classmethod
    def from_domain(cls, blocker: Blocker) -> "BlockerResponse":
        return cls.model_validate(blocker, from_attributes=True)


class ReadinessResponse(ApiSchema):
    period_value: str
    status: str
    session_count: int
    billable_count: int
    pending_count: int
    discarded_count: int
    period_energy_kwh: Decimal
    billable_energy_kwh: Decimal
    aggregate_energy_kwh: Decimal | None
    internal_difference_kwh: Decimal
    external_difference_kwh: Decimal | None
    assignment_coverage: Decimal
    unassigned_value_cents: int | None
    can_close: bool
    blockers: list[BlockerResponse]

    @classmethod
    def from_domain(cls, readiness: Readiness) -> "ReadinessResponse":
        return cls(
            period_value=readiness.period_value,
            status=readiness.status,
            session_count=readiness.session_count,
            billable_count=readiness.billable_count,
            pending_count=readiness.pending_count,
            discarded_count=readiness.discarded_count,
            period_energy_kwh=readiness.period_energy_kwh,
            billable_energy_kwh=readiness.billable_energy_kwh,
            aggregate_energy_kwh=readiness.aggregate_energy_kwh,
            internal_difference_kwh=readiness.internal_difference_kwh,
            external_difference_kwh=readiness.external_difference_kwh,
            assignment_coverage=readiness.assignment_coverage,
            unassigned_value_cents=readiness.unassigned_value_cents,
            can_close=readiness.can_close,
            blockers=[
                BlockerResponse.from_domain(blocker) for blocker in readiness.blockers
            ],
        )


class PeriodReadinessResponse(ApiSchema):
    period: BillingPeriodResponse
    readiness: ReadinessResponse


class FindingResponse(ApiSchema):
    code: str
    severity: str
    confidence: str
    explanation: str
    evidence: dict[str, str]
    charging_session_id: UUID | None

    @classmethod
    def from_domain(cls, finding: Finding) -> "FindingResponse":
        return cls(
            code=finding.code,
            severity=finding.severity.value,
            confidence=finding.confidence.value,
            explanation=finding.explanation,
            evidence=finding.evidence,
            charging_session_id=finding.charging_session_id,
        )


class ClosingOpinionResponse(ApiSchema):
    insight_run_id: UUID
    conclusion: str
    severity: str
    confidence: str
    recommendation: str
    sample_size: int
    algorithm_version: str
    parameters: dict[str, str]
    dataset_checksum: str
    findings: list[FindingResponse]

    @classmethod
    def from_domain(
        cls, opinion: ClosingOpinion, insight_run_id: UUID
    ) -> "ClosingOpinionResponse":
        return cls(
            insight_run_id=insight_run_id,
            conclusion=opinion.conclusion.value,
            severity=opinion.severity.value,
            confidence=opinion.confidence.value,
            recommendation=opinion.recommendation,
            sample_size=opinion.sample_size,
            algorithm_version=opinion.algorithm_version,
            parameters=opinion.parameters,
            dataset_checksum=opinion.dataset_checksum,
            findings=[
                FindingResponse.from_domain(finding) for finding in opinion.findings
            ],
        )


class PeriodOpinionResponse(ApiSchema):
    period: BillingPeriodResponse
    opinion: ClosingOpinionResponse


class InvoiceItemResponse(ApiSchema):
    id: UUID
    charging_session_id: UUID
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    band_code: str
    # The code stays, because it identifies the band across closes; the label is
    # what the resident is shown, and comes from the same table the PDF uses.
    band_label: str
    rate_cents_per_kwh: int
    value_cents: int

    @classmethod
    def from_view(cls, view: InvoiceItemView) -> "InvoiceItemResponse":
        return cls(
            id=view.id,
            charging_session_id=view.charging_session_id,
            started_at=view.started_at,
            ended_at=view.ended_at,
            energy_kwh=view.energy_kwh,
            band_code=view.band_code,
            band_label=band_label(view.band_code),
            rate_cents_per_kwh=view.rate_cents_per_kwh,
            value_cents=view.value_cents,
        )


class InvoiceResponse(ApiSchema):
    id: UUID
    number: str
    billing_period_id: UUID
    period_value: str
    unit_id: UUID
    unit_code: str
    unit_name: str
    contact_label: str
    energy_kwh: Decimal
    energy_value_cents: int
    infra_fee_cents: int
    loss_share_cents: int
    total_cents: int
    issued_at: datetime
    items: list[InvoiceItemResponse]

    @classmethod
    def from_view(cls, view: InvoiceView) -> "InvoiceResponse":
        return cls(
            id=view.id,
            number=view.number,
            billing_period_id=view.billing_period_id,
            period_value=view.period_value,
            unit_id=view.unit_id,
            unit_code=view.unit_code,
            unit_name=view.unit_name,
            contact_label=view.contact_label,
            energy_kwh=view.energy_kwh,
            energy_value_cents=view.energy_value_cents,
            infra_fee_cents=view.infra_fee_cents,
            loss_share_cents=view.loss_share_cents,
            total_cents=view.total_cents,
            issued_at=view.issued_at,
            items=[InvoiceItemResponse.from_view(item) for item in view.items],
        )


class InvoiceListResponse(ApiSchema):
    items: list[InvoiceResponse]


class PersistedFindingResponse(ApiSchema):
    """A finding the manager can act on, with its decision if one was made."""

    id: UUID
    code: str
    severity: str
    confidence: str
    explanation: str
    evidence: dict[str, str]
    charging_session_id: UUID | None
    resolved_at: datetime | None
    resolved_by_name: str | None
    resolution_note: str | None

    @classmethod
    def from_domain(cls, finding: PersistedFinding) -> "PersistedFindingResponse":
        return cls(
            id=finding.id,
            code=finding.code,
            severity=finding.severity,
            confidence=finding.confidence,
            explanation=finding.explanation,
            evidence=finding.evidence,
            charging_session_id=finding.charging_session_id,
            resolved_at=finding.resolved_at,
            resolved_by_name=finding.resolved_by_name,
            resolution_note=finding.resolution_note,
        )


class FindingListResponse(ApiSchema):
    items: list[PersistedFindingResponse]


class DecideFindingRequest(ApiSchema):
    note: str = Field(min_length=3, max_length=2000)


class TariffBandResponse(ApiSchema):
    """A band of the frozen tariff, and this invoice's energy priced in it."""

    code: str
    label: str
    hours: str
    rate_cents_per_kwh: int
    energy_value_cents: int

    @classmethod
    def from_domain(
        cls, band: TariffBand, energies: tuple[Decimal, ...]
    ) -> "TariffBandResponse":
        return cls(
            code=band.code,
            label=band_label(band.code),
            hours=band_hours(band),
            rate_cents_per_kwh=band.rate_cents_per_kwh,
            energy_value_cents=energy_value_in_band(
                energies, band.rate_cents_per_kwh
            ),
        )


class InvoiceContextResponse(ApiSchema):
    """The frozen records the invoice cites, as the document cites them."""

    organization_name: str
    site_name: str
    timezone: str
    tariff_name: str
    tariff_source: str
    tariff_source_label: str
    tariff_source_reference: str | None
    tariff_valid_from: date
    tariff_valid_to: date | None
    policy_name: str
    infra_fee_cents: int
    loss_basis_points: int
    provenance_label: str

    @classmethod
    def from_domain(
        cls, context: InvoiceDocumentContext
    ) -> "InvoiceContextResponse":
        return cls(
            organization_name=context.organization_name,
            site_name=context.site_name,
            timezone=context.timezone,
            tariff_name=context.tariff_name,
            tariff_source=context.tariff_source,
            tariff_source_label=tariff_source_label(context.tariff_source),
            tariff_source_reference=context.tariff_source_reference,
            tariff_valid_from=context.tariff_valid_from,
            tariff_valid_to=context.tariff_valid_to,
            policy_name=context.policy_name,
            infra_fee_cents=context.infra_fee_cents,
            loss_basis_points=context.loss_basis_points,
            # The same wording the PDF prints, so the two cannot disagree about
            # whether the reader is looking at real or simulated data.
            provenance_label=provenance_label(context.provenances),
        )


class InvoiceDetailResponse(ApiSchema):
    invoice: InvoiceResponse
    context: InvoiceContextResponse
    bands: list[TariffBandResponse]


class ClosePeriodResponse(ApiSchema):
    period: BillingPeriodResponse
    invoices: list[InvoiceResponse]


class CloseConflictResponse(ApiSchema):
    """Body of every 409 from the close endpoint.

    `blockers` is filled when the close was attempted with blockers remaining,
    and empty when the conflict is the period's own status (already closed, or
    another close in flight).
    """

    code: str
    message: str
    blockers: list[BlockerResponse]
