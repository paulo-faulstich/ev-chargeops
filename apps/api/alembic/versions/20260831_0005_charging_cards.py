"""Register RFID cards against units and record how a session was attributed.

Revision ID: 20260831_0005
Revises: 20260831_0004
Create Date: 2026-08-31

The charger already authenticates a card and the SEMS+ charging report already
carries `Card ID` and `RFID Card Name`. What is missing between the equipment
and a bill is the statement that a given card belongs to a given unit. This
table is that statement, made once by a manager and audited.

`session_assignments.origin` keeps the two paths distinguishable forever: a
card-matched attribution and a manager's judgement are both legitimate, and an
auditor must be able to tell which one produced a charge.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260831_0005"
down_revision: str | None = "20260831_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "charging_cards",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.String(length=128), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("registered_by", sa.Uuid(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.ForeignKeyConstraint(["registered_by"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "card_id",
            name="uq_charging_cards_organization_id_card_id",
        ),
    )
    op.create_index(
        "ix_charging_cards_organization_id",
        "charging_cards",
        ["organization_id"],
    )
    op.create_index("ix_charging_cards_unit_id", "charging_cards", ["unit_id"])
    op.create_index(
        "ix_charging_cards_organization_id_unit_id",
        "charging_cards",
        ["organization_id", "unit_id"],
    )

    op.add_column(
        "session_assignments",
        sa.Column(
            "origin",
            sa.String(length=16),
            nullable=False,
            server_default="manual",
        ),
    )


def downgrade() -> None:
    op.drop_column("session_assignments", "origin")
    op.drop_index(
        "ix_charging_cards_organization_id_unit_id", table_name="charging_cards"
    )
    op.drop_index("ix_charging_cards_organization_id", table_name="charging_cards")
    op.drop_index("ix_charging_cards_unit_id", table_name="charging_cards")
    op.drop_table("charging_cards")
