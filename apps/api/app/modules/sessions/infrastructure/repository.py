from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.infrastructure.models import ChargingSessionModel
from app.modules.organizations.infrastructure.models import (
    ChargerModel,
    MembershipModel,
    ProfileModel,
    UnitModel,
)
from app.modules.sessions.domain.models import AssignmentUnitView, SessionView
from app.modules.sessions.infrastructure.models import SessionAssignmentModel


class SqlAlchemySessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_sessions(
        self,
        organization_id: UUID,
        *,
        period: str | None,
        status: str | None,
    ) -> tuple[SessionView, ...]:
        resident_membership_id = self._resident_membership_id(organization_id)
        statement = (
            select(
                ChargingSessionModel,
                ChargerModel.serial,
                UnitModel.id,
                UnitModel.code,
                UnitModel.display_name,
                ProfileModel.display_name,
            )
            .join(
                ChargerModel,
                and_(
                    ChargerModel.id == ChargingSessionModel.charger_id,
                    ChargerModel.organization_id == organization_id,
                ),
            )
            .outerjoin(
                SessionAssignmentModel,
                and_(
                    SessionAssignmentModel.organization_id == organization_id,
                    SessionAssignmentModel.charging_session_id
                    == ChargingSessionModel.id,
                ),
            )
            .outerjoin(
                UnitModel,
                and_(
                    UnitModel.id == SessionAssignmentModel.unit_id,
                    UnitModel.organization_id == organization_id,
                ),
            )
            .outerjoin(
                MembershipModel,
                and_(
                    MembershipModel.organization_id == organization_id,
                    MembershipModel.id == resident_membership_id,
                ),
            )
            .outerjoin(ProfileModel, ProfileModel.id == MembershipModel.profile_id)
            .where(ChargingSessionModel.organization_id == organization_id)
            .order_by(
                ChargingSessionModel.started_at.desc(),
                ChargingSessionModel.id.desc(),
            )
        )
        if period is not None:
            start, end = self._period_bounds(period)
            statement = statement.where(
                ChargingSessionModel.started_at >= start,
                ChargingSessionModel.started_at < end,
            )
        if status is not None:
            statement = statement.where(ChargingSessionModel.status == status)

        rows = (await self.session.execute(statement)).all()
        return tuple(
            SessionView(
                id=charging_session.id,
                started_at=self._as_utc(charging_session.started_at),
                ended_at=self._as_utc(charging_session.ended_at),
                energy_kwh=charging_session.energy_kwh,
                charger_serial=charger_serial,
                source=charging_session.source,
                provenance=charging_session.provenance,
                identity_confidence=charging_session.identity_confidence,
                status=charging_session.status,
                unit_id=unit_id,
                unit_code=unit_code,
                unit_name=unit_name,
                resident_name=resident_name,
            )
            for (
                charging_session,
                charger_serial,
                unit_id,
                unit_code,
                unit_name,
                resident_name,
            ) in rows
        )

    async def list_assignment_units(
        self,
        organization_id: UUID,
    ) -> tuple[AssignmentUnitView, ...]:
        resident_membership_id = self._resident_membership_id(organization_id)
        statement = (
            select(
                UnitModel.id,
                UnitModel.code,
                UnitModel.display_name,
                ProfileModel.display_name,
            )
            .outerjoin(
                MembershipModel,
                and_(
                    MembershipModel.organization_id == organization_id,
                    MembershipModel.id == resident_membership_id,
                ),
            )
            .outerjoin(ProfileModel, ProfileModel.id == MembershipModel.profile_id)
            .where(UnitModel.organization_id == organization_id)
            .order_by(UnitModel.code.asc(), UnitModel.id.asc())
        )
        rows = (await self.session.execute(statement)).all()
        return tuple(
            AssignmentUnitView(
                id=unit_id,
                code=code,
                display_name=display_name,
                resident_name=resident_name,
            )
            for unit_id, code, display_name, resident_name in rows
        )

    @staticmethod
    def _resident_membership_id(organization_id: UUID):
        return (
            select(MembershipModel.id)
            .where(
                MembershipModel.organization_id == organization_id,
                MembershipModel.unit_id == UnitModel.id,
                MembershipModel.role == "resident",
            )
            .order_by(MembershipModel.created_at.asc(), MembershipModel.id.asc())
            .limit(1)
            .correlate(UnitModel)
            .scalar_subquery()
        )

    @staticmethod
    def _period_bounds(period: str) -> tuple[datetime, datetime]:
        start = datetime.strptime(period, "%Y-%m").replace(tzinfo=UTC)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
