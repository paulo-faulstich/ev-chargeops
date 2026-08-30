from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.sqlalchemy import Base, UuidPrimaryKeyMixin


class AuditEventModel(UuidPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    actor_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index(
            "ix_audit_events_organization_id_actor_profile_id",
            "organization_id",
            "actor_profile_id",
        ),
        Index(
            "ix_audit_events_organization_id_entity_id",
            "organization_id",
            "entity_id",
        ),
    )
