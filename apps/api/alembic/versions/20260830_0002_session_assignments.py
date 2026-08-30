"""Create session assignments.

Revision ID: 20260830_0002
Revises: 20260829_0001
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0002"
down_revision: str | None = "20260829_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_assignments",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("charging_session_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by"], ["profiles.id"]),
        sa.ForeignKeyConstraint(
            ["charging_session_id"], ["charging_sessions.id"]
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "charging_session_id",
            name="uq_session_assignments_organization_id_charging_session_id",
        ),
    )
    op.create_index(
        "ix_session_assignments_organization_id",
        "session_assignments",
        ["organization_id"],
    )
    op.create_index(
        "ix_session_assignments_charging_session_id",
        "session_assignments",
        ["charging_session_id"],
    )
    op.create_index(
        "ix_session_assignments_unit_id",
        "session_assignments",
        ["unit_id"],
    )
    op.create_index(
        "ix_session_assignments_assigned_by",
        "session_assignments",
        ["assigned_by"],
    )
    op.create_index(
        "ix_session_assignments_organization_id_unit_id",
        "session_assignments",
        ["organization_id", "unit_id"],
    )


def downgrade() -> None:
    op.drop_table("session_assignments")
