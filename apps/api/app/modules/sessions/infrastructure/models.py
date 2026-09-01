from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.sqlalchemy import (
    Base,
    TimestampMixin,
    UtcDateTime,
    UuidPrimaryKeyMixin,
)


class SessionAssignmentModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "session_assignments"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    charging_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("charging_sessions.id"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id"), index=True)
    assigned_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    justification: Mapped[str] = mapped_column(Text(), nullable=False)
    # "manual" or "card". A charge attributed by a registered card and one
    # attributed by a manager's judgement are both legitimate, and an auditor
    # must be able to tell them apart years later.
    origin: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="manual", default="manual"
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "charging_session_id",
            name="uq_session_assignments_organization_id_charging_session_id",
        ),
        Index(
            "ix_session_assignments_organization_id_unit_id",
            "organization_id",
            "unit_id",
        ),
    )


class ChargingCardModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """The statement that an RFID card belongs to a condominium unit.

    The charger authenticates the card and the SEMS+ report carries its id; what
    the equipment cannot know is which unit pays for it. A manager says so once,
    here, and every later session carrying that card attributes itself.
    """

    __tablename__ = "charging_cards"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    card_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id"), index=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    registered_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "card_id",
            name="uq_charging_cards_organization_id_card_id",
        ),
        Index(
            "ix_charging_cards_organization_id_unit_id",
            "organization_id",
            "unit_id",
        ),
    )
