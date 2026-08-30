from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.sqlalchemy import Base, TimestampMixin, UuidPrimaryKeyMixin


class OrganizationModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(160), nullable=False)


class SiteModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sites"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)


class ChargerModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chargers"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    serial: Mapped[str] = mapped_column(String(96), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    nominal_power_kw: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False
    )

    __table_args__ = (UniqueConstraint("organization_id", "serial"),)


class UnitModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "units"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)

    __table_args__ = (UniqueConstraint("organization_id", "code"),)


class ProfileModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "profiles"

    auth_user_id: Mapped[UUID] = mapped_column(unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)


class MembershipModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memberships"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("units.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (UniqueConstraint("organization_id", "profile_id"),)
