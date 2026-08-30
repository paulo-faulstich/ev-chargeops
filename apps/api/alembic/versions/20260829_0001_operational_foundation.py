"""Create the operational persistence foundation.

Revision ID: 20260829_0001
Revises:
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def create_unique_constraint(
    name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_unique_constraint(name, columns)
        return
    op.create_unique_constraint(name, table_name, columns)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sites",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sites_organization_id", "sites", ["organization_id"])
    op.create_table(
        "chargers",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("serial", sa.String(length=96), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("nominal_power_kw", sa.Numeric(10, 3), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    create_unique_constraint(
        "uq_chargers_organization_id_serial",
        "chargers",
        ["organization_id", "serial"],
    )
    op.create_index("ix_chargers_organization_id", "chargers", ["organization_id"])
    op.create_index("ix_chargers_site_id", "chargers", ["site_id"])
    op.create_table(
        "units",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    create_unique_constraint(
        "uq_units_organization_id_code",
        "units",
        ["organization_id", "code"],
    )
    op.create_index("ix_units_organization_id", "units", ["organization_id"])
    op.create_table(
        "profiles",
        sa.Column("auth_user_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_profiles_auth_user_id",
        "profiles",
        ["auth_user_id"],
        unique=True,
    )
    op.create_table(
        "memberships",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    create_unique_constraint(
        "uq_memberships_organization_id_profile_id",
        "memberships",
        ["organization_id", "profile_id"],
    )
    op.create_index(
        "ix_memberships_organization_id", "memberships", ["organization_id"]
    )
    op.create_index("ix_memberships_profile_id", "memberships", ["profile_id"])
    op.create_table(
        "import_batches",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("valid_count", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    create_unique_constraint(
        "uq_import_batches_organization_id_checksum",
        "import_batches",
        ["organization_id", "checksum"],
    )
    op.create_index(
        "ix_import_batches_organization_id", "import_batches", ["organization_id"]
    )
    op.create_table(
        "raw_import_records",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("error_field", sa.String(length=128), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    create_unique_constraint(
        "uq_raw_import_records_import_batch_id_row_number",
        "raw_import_records",
        ["import_batch_id", "row_number"],
    )
    op.create_index(
        "ix_raw_import_records_import_batch_id",
        "raw_import_records",
        ["import_batch_id"],
    )
    op.create_index(
        "ix_raw_import_records_organization_id",
        "raw_import_records",
        ["organization_id"],
    )
    op.create_table(
        "charging_sessions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("charger_id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("raw_record_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=True),
        sa.Column("deduplication_key", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("energy_kwh", sa.Numeric(12, 3), nullable=False),
        sa.Column("charge_port", sa.Integer(), nullable=True),
        sa.Column("card_id_raw", sa.String(length=160), nullable=True),
        sa.Column("identity_confidence", sa.String(length=32), nullable=False),
        sa.Column("provenance", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["charger_id"], ["chargers.id"]),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["raw_record_id"], ["raw_import_records.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    create_unique_constraint(
        "uq_charging_sessions_raw_record_id",
        "charging_sessions",
        ["raw_record_id"],
    )
    create_unique_constraint(
        "uq_charging_sessions_organization_id_deduplication_key",
        "charging_sessions",
        ["organization_id", "deduplication_key"],
    )
    op.create_index(
        "ix_charging_sessions_charger_id", "charging_sessions", ["charger_id"]
    )
    op.create_index(
        "ix_charging_sessions_import_batch_id",
        "charging_sessions",
        ["import_batch_id"],
    )
    op.create_index(
        "ix_charging_sessions_organization_id",
        "charging_sessions",
        ["organization_id"],
    )
    op.create_index("ix_charging_sessions_site_id", "charging_sessions", ["site_id"])
    op.create_table(
        "audit_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("actor_profile_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_actor_profile_id", "audit_events", ["actor_profile_id"]
    )
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index(
        "ix_audit_events_organization_id", "audit_events", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("charging_sessions")
    op.drop_table("raw_import_records")
    op.drop_table("import_batches")
    op.drop_table("memberships")
    op.drop_table("profiles")
    op.drop_table("units")
    op.drop_table("chargers")
    op.drop_table("sites")
    op.drop_table("organizations")
