from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.sqlalchemy import Base, TimestampMixin, UtcDateTime, UuidPrimaryKeyMixin


class ResidentContextModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A manager temporarily seeing exactly what one unit's resident would see.

    The row is the context: short-lived, revocable, and auditable. Resolution
    happens on every request, so expiry and explicit exit take effect
    immediately instead of waiting for a token to age out.
    """

    __tablename__ = "resident_contexts"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    manager_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False
    )
    exited_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )

    __table_args__ = (
        Index(
            "ix_resident_contexts_organization_id_manager_profile_id",
            "organization_id",
            "manager_profile_id",
        ),
    )
