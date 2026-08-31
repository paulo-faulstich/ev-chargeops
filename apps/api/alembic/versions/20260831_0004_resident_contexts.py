"""Create the resident context table.

Revision ID: 20260831_0004
Revises: 20260830_0003
Create Date: 2026-08-31

The context is a row, not a token: resolution happens on every request, so
expiry and explicit exit take effect immediately, and the trail of who saw
which unit's invoice, and when, survives in the table and in audit events.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260831_0004"
down_revision: str | None = "20260830_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resident_contexts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("manager_profile_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["manager_profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_resident_contexts_organization_id",
        "resident_contexts",
        ["organization_id"],
    )
    op.create_index(
        "ix_resident_contexts_manager_profile_id",
        "resident_contexts",
        ["manager_profile_id"],
    )
    op.create_index(
        "ix_resident_contexts_unit_id", "resident_contexts", ["unit_id"]
    )
    op.create_index(
        "ix_resident_contexts_organization_id_manager_profile_id",
        "resident_contexts",
        ["organization_id", "manager_profile_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_resident_contexts_organization_id_manager_profile_id",
        table_name="resident_contexts",
    )
    op.drop_index("ix_resident_contexts_unit_id", table_name="resident_contexts")
    op.drop_index(
        "ix_resident_contexts_manager_profile_id", table_name="resident_contexts"
    )
    op.drop_index(
        "ix_resident_contexts_organization_id", table_name="resident_contexts"
    )
    op.drop_table("resident_contexts")
