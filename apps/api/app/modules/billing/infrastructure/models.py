from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.sqlalchemy import Base, TimestampMixin, UtcDateTime, UuidPrimaryKeyMixin


class TariffSnapshotModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A versioned tariff. Immutable once an invoice references it."""

    __tablename__ = "tariff_snapshots"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False
    )
    valid_from: Mapped[date] = mapped_column(nullable=False)
    valid_to: Mapped[date | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        Index(
            "ix_tariff_snapshots_organization_id_valid_from",
            "organization_id",
            "valid_from",
        ),
    )


class TariffBandModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A rate and the local-time windows it applies to.

    Windows live in JSON because they are always read together with their band
    and never queried individually.
    """

    __tablename__ = "tariff_bands"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    tariff_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("tariff_snapshots.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    rate_cents_per_kwh: Mapped[int] = mapped_column(nullable=False)
    windows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "tariff_snapshot_id", "code"),
    )


class BillingPolicyModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned apportionment rules for the shared costs."""

    __tablename__ = "billing_policies"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    infra_fee_cents: Mapped[int] = mapped_column(nullable=False)
    loss_basis_points: Mapped[int] = mapped_column(nullable=False)
    valid_from: Mapped[date] = mapped_column(nullable=False)
    valid_to: Mapped[date | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        Index(
            "ix_billing_policies_organization_id_valid_from",
            "organization_id",
            "valid_from",
        ),
    )


class InsightRunModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A reproducible analytical execution.

    Holds everything needed to re-run and audit the result: algorithm version,
    parameters, and a checksum of the dataset it read. The closing opinion is a
    run of kind `closing_opinion`; forecasting and segmentation will add kinds
    without changing the shape.
    """

    __tablename__ = "insight_runs"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    billing_period_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("billing_periods.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    dataset_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_size: Mapped[int] = mapped_column(nullable=False)
    conclusion: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        Index(
            "ix_insight_runs_organization_id_kind",
            "organization_id",
            "kind",
        ),
    )


class AnalyticalFindingModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One explainable finding produced by an insight run.

    `evidence` carries the values that triggered the rule, so the manager and a
    later auditor see why it fired without re-running anything.
    """

    __tablename__ = "analytical_findings"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    insight_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("insight_runs.id"), index=True
    )
    charging_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("charging_sessions.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    resolved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.id"), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_analytical_findings_organization_id_insight_run_id",
            "organization_id",
            "insight_run_id",
        ),
    )


class BillingPeriodModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A monthly close for one site.

    The tariff and policy identifiers are frozen here at approval rather than
    copied onto every invoice: both referenced records are themselves immutable,
    so one reference is enough and there is a single source of truth per close.
    """

    __tablename__ = "billing_periods"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    period_value: Mapped[str] = mapped_column(String(7), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    tariff_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tariff_snapshots.id"), nullable=True
    )
    billing_policy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("billing_policies.id"), nullable=True
    )
    # No foreign key on purpose: `insight_runs` already points back here, and
    # closing the cycle is not creatable in one pass on PostgreSQL nor patchable
    # afterwards on SQLite. The value is written only inside the close
    # transaction, from an id read moments earlier in that same transaction.
    closing_insight_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    eligible_energy_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    invoiced_energy_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    aggregate_energy_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "site_id", "period_value"),
    )


class InvoiceModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """An issued bill for one unit in one period.

    `contact_label` is denormalized on purpose: a resident who moves out must
    not change a bill already issued in their name.
    """

    __tablename__ = "invoices"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    billing_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_periods.id"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id"), index=True)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_label: Mapped[str] = mapped_column(String(160), nullable=False)
    energy_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    energy_value_cents: Mapped[int] = mapped_column(nullable=False)
    infra_fee_cents: Mapped[int] = mapped_column(nullable=False)
    loss_share_cents: Mapped[int] = mapped_column(nullable=False)
    total_cents: Mapped[int] = mapped_column(nullable=False)
    issued_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "billing_period_id", "unit_id"),
        UniqueConstraint("organization_id", "number"),
        Index("ix_invoices_organization_id_unit_id", "organization_id", "unit_id"),
    )


class InvoiceItemModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One charging session on an invoice.

    Observed measurements are copied rather than joined, so the invoice renders
    and defends itself without re-reading the session, and cannot drift.
    """

    __tablename__ = "invoice_items"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    charging_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("charging_sessions.id"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False
    )
    ended_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    energy_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    band_code: Mapped[str] = mapped_column(String(32), nullable=False)
    rate_cents_per_kwh: Mapped[int] = mapped_column(nullable=False)
    value_cents: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "charging_session_id"),
        Index(
            "ix_invoice_items_organization_id_invoice_id",
            "organization_id",
            "invoice_id",
        ),
    )


class InvoiceDocumentModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """Evidence that two downloads of one invoice are the same document."""

    __tablename__ = "invoice_documents"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False
    )

    __table_args__ = (UniqueConstraint("organization_id", "invoice_id"),)


class ChargerEnergyReadingModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """Energy the equipment itself reports for a period.

    This is the external control total for reconciliation. It is never a
    billable charging session and never reaches an invoice.
    """

    __tablename__ = "charger_energy_readings"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    charger_id: Mapped[UUID] = mapped_column(ForeignKey("chargers.id"), index=True)
    import_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("import_batches.id"), nullable=True
    )
    period_type: Mapped[str] = mapped_column(String(8), nullable=False)
    period_value: Mapped[str] = mapped_column(String(10), nullable=False)
    energy_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "charger_id",
            "period_type",
            "period_value",
            name="uq_charger_energy_readings_period",
        ),
        Index(
            "ix_charger_energy_readings_organization_id_period_value",
            "organization_id",
            "period_value",
        ),
    )
