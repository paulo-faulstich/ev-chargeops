from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.sqlalchemy import Base, TimestampMixin, UuidPrimaryKeyMixin


class ImportBatchModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_batches"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total_count: Mapped[int] = mapped_column(nullable=False)
    valid_count: Mapped[int] = mapped_column(nullable=False)
    invalid_count: Mapped[int] = mapped_column(nullable=False)
    duplicate_count: Mapped[int] = mapped_column(nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))

    __table_args__ = (UniqueConstraint("organization_id", "checksum"),)


class RawImportRecordModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "raw_import_records"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    import_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_batches.id"), index=True
    )
    row_number: Mapped[int] = mapped_column(nullable=False)
    raw_payload: Mapped[dict[str, str | None]] = mapped_column(JSON, nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    error_field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "import_batch_id", "row_number"),
        Index(
            "ix_raw_import_records_organization_id_import_batch_id",
            "organization_id",
            "import_batch_id",
        ),
    )


class ChargingSessionModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "charging_sessions"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    charger_id: Mapped[UUID] = mapped_column(ForeignKey("chargers.id"), index=True)
    import_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_batches.id"), index=True
    )
    raw_record_id: Mapped[UUID] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    deduplication_key: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    energy_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    charge_port: Mapped[int | None] = mapped_column(nullable=True)
    card_id_raw: Mapped[str | None] = mapped_column(String(160), nullable=True)
    identity_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ("organization_id", "raw_record_id"),
            ("raw_import_records.organization_id", "raw_import_records.id"),
        ),
        UniqueConstraint("organization_id", "raw_record_id"),
        UniqueConstraint("organization_id", "deduplication_key"),
        Index(
            "ix_charging_sessions_organization_id_site_id",
            "organization_id",
            "site_id",
        ),
        Index(
            "ix_charging_sessions_organization_id_charger_id",
            "organization_id",
            "charger_id",
        ),
        Index(
            "ix_charging_sessions_organization_id_import_batch_id",
            "organization_id",
            "import_batch_id",
        ),
    )
