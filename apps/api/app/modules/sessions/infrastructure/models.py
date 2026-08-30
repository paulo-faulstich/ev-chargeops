from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.sqlalchemy import Base, TimestampMixin, UuidPrimaryKeyMixin


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
