"""Create tariff, policy, period, invoice and reconciliation tables.

Revision ID: 20260830_0003
Revises: 20260830_0002
Create Date: 2026-08-30

Tables are created in dependency order so the migration also applies on
PostgreSQL, where a forward reference to a table that does not exist yet is a
hard error rather than a no-op.

`billing_periods.closing_insight_run_id` deliberately carries no foreign key.
An opinion is generated for a period before approval, so `insight_runs` already
points at `billing_periods`; adding the reverse key would close a cycle that
neither database can create in one pass and that SQLite cannot patch afterwards
with an ALTER. The value is only ever written inside the close transaction, from
an identifier read moments earlier in the same transaction.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0003"
down_revision: str | None = "20260830_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Integer()
ENERGY = sa.Numeric(precision=12, scale=3)


def upgrade() -> None:
    op.create_table(
        "tariff_snapshots",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_reference", sa.String(length=512), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id"),
    )
    op.create_index(
        "ix_tariff_snapshots_organization_id", "tariff_snapshots", ["organization_id"]
    )
    op.create_index(
        "ix_tariff_snapshots_organization_id_valid_from",
        "tariff_snapshots",
        ["organization_id", "valid_from"],
    )

    op.create_table(
        "tariff_bands",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tariff_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("rate_cents_per_kwh", MONEY, nullable=False),
        sa.Column("windows", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["tariff_snapshot_id"], ["tariff_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "tariff_snapshot_id", "code"),
    )
    op.create_index(
        "ix_tariff_bands_organization_id", "tariff_bands", ["organization_id"]
    )
    op.create_index(
        "ix_tariff_bands_tariff_snapshot_id", "tariff_bands", ["tariff_snapshot_id"]
    )

    op.create_table(
        "billing_policies",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("infra_fee_cents", MONEY, nullable=False),
        sa.Column("loss_basis_points", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id"),
    )
    op.create_index(
        "ix_billing_policies_organization_id", "billing_policies", ["organization_id"]
    )
    op.create_index(
        "ix_billing_policies_organization_id_valid_from",
        "billing_policies",
        ["organization_id", "valid_from"],
    )

    op.create_table(
        "billing_periods",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("period_value", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("tariff_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("billing_policy_id", sa.Uuid(), nullable=True),
        sa.Column("closing_insight_run_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eligible_energy_kwh", ENERGY, nullable=True),
        sa.Column("invoiced_energy_kwh", ENERGY, nullable=True),
        sa.Column("aggregate_energy_kwh", ENERGY, nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["billing_policy_id"], ["billing_policies.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["tariff_snapshot_id"], ["tariff_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id"),
        sa.UniqueConstraint("organization_id", "site_id", "period_value"),
    )
    op.create_index(
        "ix_billing_periods_organization_id", "billing_periods", ["organization_id"]
    )
    op.create_index("ix_billing_periods_site_id", "billing_periods", ["site_id"])

    op.create_table(
        "insight_runs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("billing_period_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("algorithm_version", sa.String(length=32), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("dataset_checksum", sa.String(length=64), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("conclusion", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["billing_period_id"], ["billing_periods.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id"),
    )
    op.create_index(
        "ix_insight_runs_organization_id", "insight_runs", ["organization_id"]
    )
    op.create_index(
        "ix_insight_runs_billing_period_id", "insight_runs", ["billing_period_id"]
    )
    op.create_index(
        "ix_insight_runs_organization_id_kind",
        "insight_runs",
        ["organization_id", "kind"],
    )

    op.create_table(
        "analytical_findings",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("insight_run_id", sa.Uuid(), nullable=False),
        sa.Column("charging_session_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["charging_session_id"], ["charging_sessions.id"]),
        sa.ForeignKeyConstraint(["insight_run_id"], ["insight_runs.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analytical_findings_organization_id",
        "analytical_findings",
        ["organization_id"],
    )
    op.create_index(
        "ix_analytical_findings_insight_run_id",
        "analytical_findings",
        ["insight_run_id"],
    )
    op.create_index(
        "ix_analytical_findings_charging_session_id",
        "analytical_findings",
        ["charging_session_id"],
    )
    op.create_index(
        "ix_analytical_findings_organization_id_insight_run_id",
        "analytical_findings",
        ["organization_id", "insight_run_id"],
    )

    op.create_table(
        "invoices",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("billing_period_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("contact_label", sa.String(length=160), nullable=False),
        sa.Column("energy_kwh", ENERGY, nullable=False),
        sa.Column("energy_value_cents", MONEY, nullable=False),
        sa.Column("infra_fee_cents", MONEY, nullable=False),
        sa.Column("loss_share_cents", MONEY, nullable=False),
        sa.Column("total_cents", MONEY, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["billing_period_id"], ["billing_periods.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id"),
        sa.UniqueConstraint("organization_id", "billing_period_id", "unit_id"),
        sa.UniqueConstraint("organization_id", "number"),
    )
    op.create_index("ix_invoices_organization_id", "invoices", ["organization_id"])
    op.create_index("ix_invoices_billing_period_id", "invoices", ["billing_period_id"])
    op.create_index("ix_invoices_unit_id", "invoices", ["unit_id"])
    op.create_index(
        "ix_invoices_organization_id_unit_id",
        "invoices",
        ["organization_id", "unit_id"],
    )

    op.create_table(
        "invoice_items",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("charging_session_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("energy_kwh", ENERGY, nullable=False),
        sa.Column("band_code", sa.String(length=32), nullable=False),
        sa.Column("rate_cents_per_kwh", MONEY, nullable=False),
        sa.Column("value_cents", MONEY, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["charging_session_id"], ["charging_sessions.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "charging_session_id"),
    )
    op.create_index(
        "ix_invoice_items_organization_id", "invoice_items", ["organization_id"]
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])
    op.create_index(
        "ix_invoice_items_charging_session_id",
        "invoice_items",
        ["charging_session_id"],
    )
    op.create_index(
        "ix_invoice_items_organization_id_invoice_id",
        "invoice_items",
        ["organization_id", "invoice_id"],
    )

    op.create_table(
        "invoice_documents",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "invoice_id"),
    )
    op.create_index(
        "ix_invoice_documents_organization_id", "invoice_documents", ["organization_id"]
    )
    op.create_index(
        "ix_invoice_documents_invoice_id", "invoice_documents", ["invoice_id"]
    )

    op.create_table(
        "charger_energy_readings",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("charger_id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
        sa.Column("period_type", sa.String(length=8), nullable=False),
        sa.Column("period_value", sa.String(length=10), nullable=False),
        sa.Column("energy_kwh", ENERGY, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("provenance", sa.String(length=32), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["charger_id"], ["chargers.id"]),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "charger_id",
            "period_type",
            "period_value",
            name="uq_charger_energy_readings_period",
        ),
    )
    op.create_index(
        "ix_charger_energy_readings_organization_id",
        "charger_energy_readings",
        ["organization_id"],
    )
    op.create_index(
        "ix_charger_energy_readings_charger_id",
        "charger_energy_readings",
        ["charger_id"],
    )
    op.create_index(
        "ix_charger_energy_readings_organization_id_period_value",
        "charger_energy_readings",
        ["organization_id", "period_value"],
    )


def downgrade() -> None:
    op.drop_table("charger_energy_readings")
    op.drop_table("invoice_documents")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("analytical_findings")
    op.drop_table("insight_runs")
    op.drop_table("billing_periods")
    op.drop_table("billing_policies")
    op.drop_table("tariff_bands")
    op.drop_table("tariff_snapshots")
