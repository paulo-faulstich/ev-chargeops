from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.infrastructure.models import AuditEventModel
from app.modules.identity.domain.auth import OrganizationScope
from app.modules.ingestion.infrastructure.models import ChargingSessionModel
from app.modules.organizations.infrastructure.models import (
    ChargerModel,
    MembershipModel,
    ProfileModel,
    SiteModel,
    UnitModel,
)
from app.modules.sessions.domain.errors import SessionNotFound, UnitNotFound
from app.modules.sessions.domain.models import (
    AssignmentResult,
    AssignmentUnitView,
    SessionAssignment,
    SessionView,
)
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
            start, end = self._period_bounds(
                period, await self._site_timezone(organization_id)
            )
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

    async def assign_session(
        self,
        scope: OrganizationScope,
        session_id: UUID,
        unit_id: UUID,
        justification: str,
        occurred_at: datetime,
    ) -> AssignmentResult:
        try:
            session_row = (
                await self.session.execute(
                    select(ChargingSessionModel, ChargerModel.serial)
                    .join(
                        ChargerModel,
                        and_(
                            ChargerModel.id == ChargingSessionModel.charger_id,
                            ChargerModel.organization_id == scope.organization_id,
                        ),
                    )
                    .where(
                        ChargingSessionModel.id == session_id,
                        ChargingSessionModel.organization_id
                        == scope.organization_id,
                    )
                )
            ).one_or_none()
            if session_row is None:
                raise SessionNotFound
            charging_session, charger_serial = session_row

            unit_row = (
                await self.session.execute(
                    select(UnitModel, ProfileModel.display_name)
                    .outerjoin(
                        MembershipModel,
                        and_(
                            MembershipModel.organization_id
                            == scope.organization_id,
                            MembershipModel.id
                            == self._resident_membership_id(
                                scope.organization_id
                            ),
                        ),
                    )
                    .outerjoin(
                        ProfileModel,
                        ProfileModel.id == MembershipModel.profile_id,
                    )
                    .where(
                        UnitModel.id == unit_id,
                        UnitModel.organization_id == scope.organization_id,
                    )
                )
            ).one_or_none()
            if unit_row is None:
                raise UnitNotFound
            unit, resident_name = unit_row

            assignment = await self.session.scalar(
                select(SessionAssignmentModel).where(
                    SessionAssignmentModel.organization_id
                    == scope.organization_id,
                    SessionAssignmentModel.charging_session_id == session_id,
                )
            )
            if (
                assignment is not None
                and assignment.unit_id == unit_id
                and assignment.justification == justification
            ):
                return self._assignment_result(
                    assignment,
                    charging_session,
                    charger_serial,
                    unit,
                    resident_name,
                    created=False,
                )

            previous_unit_id = assignment.unit_id if assignment is not None else None
            created = assignment is None
            if assignment is None:
                assignment = SessionAssignmentModel(
                    organization_id=scope.organization_id,
                    charging_session_id=session_id,
                    unit_id=unit_id,
                    assigned_by=scope.profile_id,
                    justification=justification,
                    created_at=occurred_at,
                    updated_at=occurred_at,
                )
                self.session.add(assignment)
            else:
                assignment.unit_id = unit_id
                assignment.assigned_by = scope.profile_id
                assignment.justification = justification
                assignment.updated_at = occurred_at

            charging_session.identity_confidence = "assigned"
            charging_session.status = "ready"
            self.session.add(
                AuditEventModel(
                    organization_id=scope.organization_id,
                    actor_profile_id=scope.profile_id,
                    occurred_at=occurred_at,
                    event_type="session_assigned",
                    entity_type="charging_session",
                    entity_id=session_id,
                    metadata_json={
                        "previous_unit_id": (
                            str(previous_unit_id)
                            if previous_unit_id is not None
                            else None
                        ),
                        "new_unit_id": str(unit_id),
                        "justification": justification,
                    },
                )
            )
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            raise

        return self._assignment_result(
            assignment,
            charging_session,
            charger_serial,
            unit,
            resident_name,
            created=created,
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

    @classmethod
    def _assignment_result(
        cls,
        assignment: SessionAssignmentModel,
        charging_session: ChargingSessionModel,
        charger_serial: str,
        unit: UnitModel,
        resident_name: str | None,
        *,
        created: bool,
    ) -> AssignmentResult:
        return AssignmentResult(
            assignment=SessionAssignment(
                id=assignment.id,
                session_id=assignment.charging_session_id,
                unit_id=assignment.unit_id,
                assigned_by=assignment.assigned_by,
                justification=assignment.justification,
                created_at=cls._as_utc(assignment.created_at),
                updated_at=cls._as_utc(assignment.updated_at),
            ),
            session=SessionView(
                id=charging_session.id,
                started_at=cls._as_utc(charging_session.started_at),
                ended_at=cls._as_utc(charging_session.ended_at),
                energy_kwh=charging_session.energy_kwh,
                charger_serial=charger_serial,
                source=charging_session.source,
                provenance=charging_session.provenance,
                identity_confidence=charging_session.identity_confidence,
                status=charging_session.status,
                unit_id=unit.id,
                unit_code=unit.code,
                unit_name=unit.display_name,
                resident_name=resident_name,
            ),
            created=created,
        )

    async def _site_timezone(self, organization_id: UUID) -> ZoneInfo:
        """The wall clock a monthly period is measured against.

        Falls back to UTC only when the organization has no site yet. Sites in
        different timezones would need the bounds resolved per site; with a
        single site per organization today, one lookup is exact.
        """
        zone = (
            await self.session.execute(
                select(SiteModel.timezone)
                .where(SiteModel.organization_id == organization_id)
                .order_by(SiteModel.name)
                .limit(1)
            )
        ).scalar_one_or_none()
        return ZoneInfo(zone) if zone else ZoneInfo("UTC")

    @staticmethod
    def _period_bounds(period: str, zone: ZoneInfo) -> tuple[datetime, datetime]:
        """Month boundaries in the site's wall clock, expressed in UTC.

        Building these in UTC instead would move every late-evening session of
        the last day of the month into the next period. In São Paulo that is
        everything from 21:00 onwards, which is peak charging time in a
        condominium garage, so the energy would silently leave the close it
        belongs to.
        """
        start = datetime.strptime(period, "%Y-%m").replace(tzinfo=zone)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start.astimezone(UTC), end.astimezone(UTC)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
