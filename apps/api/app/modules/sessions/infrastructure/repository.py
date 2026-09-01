from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
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
from app.modules.sessions.domain.errors import (
    CardAlreadyRegistered,
    CardIsTheChargerSerial,
    CardNotFound,
    SessionNotFound,
    UnitNotFound,
)
from app.modules.sessions.domain.models import (
    AssignmentResult,
    AssignmentUnitView,
    ChargingCardView,
    SessionAssignment,
    SessionView,
)
from app.modules.sessions.infrastructure.models import (
    ChargingCardModel,
    SessionAssignmentModel,
)


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
                SessionAssignmentModel.origin,
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
                assignment_origin=assignment_origin,
            )
            for (
                charging_session,
                charger_serial,
                unit_id,
                unit_code,
                unit_name,
                resident_name,
                assignment_origin,
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
                    origin="manual",
                    created_at=occurred_at,
                    updated_at=occurred_at,
                )
                self.session.add(assignment)
            else:
                assignment.unit_id = unit_id
                assignment.assigned_by = scope.profile_id
                assignment.justification = justification
                # A manager overriding a card attribution is a judgement, and
                # the record must stop claiming the card decided it.
                assignment.origin = "manual"
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
                assignment_origin=assignment.origin,
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

    async def attribute_by_registered_card(
        self,
        organization_id: UUID,
        actor_profile_id: UUID,
        import_batch_id: UUID,
    ) -> int:
        """Attribute the batch's sessions whose card is registered to a unit.

        Only sessions that nobody has decided about are touched: a manager's
        judgement always outranks the registry. The raw card id alone never
        identifies anyone — what identifies is a manager having stated, once,
        which unit that card belongs to.
        """
        cards = {
            card.card_id: card
            for card in (
                await self.session.execute(
                    select(ChargingCardModel).where(
                        ChargingCardModel.organization_id == organization_id,
                        ChargingCardModel.revoked_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        }
        if not cards:
            return 0

        pending = (
            (
                await self.session.execute(
                    select(ChargingSessionModel)
                    .outerjoin(
                        SessionAssignmentModel,
                        and_(
                            SessionAssignmentModel.charging_session_id
                            == ChargingSessionModel.id,
                            SessionAssignmentModel.organization_id
                            == organization_id,
                        ),
                    )
                    .where(
                        ChargingSessionModel.organization_id == organization_id,
                        ChargingSessionModel.import_batch_id == import_batch_id,
                        ChargingSessionModel.card_id_raw.is_not(None),
                        SessionAssignmentModel.id.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )

        occurred_at = datetime.now(UTC)
        attributed = 0
        for charging_session in pending:
            card = cards.get(charging_session.card_id_raw or "")
            if card is None:
                continue
            self.session.add(
                SessionAssignmentModel(
                    organization_id=organization_id,
                    charging_session_id=charging_session.id,
                    unit_id=card.unit_id,
                    assigned_by=actor_profile_id,
                    justification=(
                        f"Cartão {card.card_id} registrado para esta unidade "
                        f"({card.label})."
                    ),
                    origin="card",
                    created_at=occurred_at,
                    updated_at=occurred_at,
                )
            )
            # The equipment authenticated the card; the registry says whose it
            # is. That is stronger than a manager's inference, and weaker than
            # nothing only if the registry is wrong — which it is auditable to.
            charging_session.identity_confidence = "confirmed"
            charging_session.status = "ready"
            self.session.add(
                AuditEventModel(
                    organization_id=organization_id,
                    actor_profile_id=actor_profile_id,
                    occurred_at=occurred_at,
                    event_type="session_attributed_by_card",
                    entity_type="charging_session",
                    entity_id=charging_session.id,
                    metadata_json={
                        "card_id": card.card_id,
                        "unit_id": str(card.unit_id),
                        "import_batch_id": str(import_batch_id),
                    },
                )
            )
            attributed += 1

        if attributed:
            await self.session.commit()
        return attributed

    async def list_charging_cards(
        self, organization_id: UUID
    ) -> tuple[ChargingCardView, ...]:
        attributed = (
            select(
                SessionAssignmentModel.unit_id.label("unit_id"),
                func.count().label("total"),
            )
            .where(
                SessionAssignmentModel.organization_id == organization_id,
                SessionAssignmentModel.origin == "card",
            )
            .group_by(SessionAssignmentModel.unit_id)
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(
                    ChargingCardModel,
                    UnitModel,
                    ProfileModel.display_name,
                    attributed.c.total,
                )
                .join(UnitModel, UnitModel.id == ChargingCardModel.unit_id)
                .outerjoin(
                    ProfileModel, ProfileModel.id == ChargingCardModel.registered_by
                )
                .outerjoin(attributed, attributed.c.unit_id == ChargingCardModel.unit_id)
                .where(ChargingCardModel.organization_id == organization_id)
                .order_by(UnitModel.code, ChargingCardModel.card_id)
            )
        ).all()
        return tuple(
            ChargingCardView(
                id=card.id,
                card_id=card.card_id,
                label=card.label,
                unit_id=unit.id,
                unit_code=unit.code,
                unit_name=unit.display_name,
                registered_by_name=registered_by,
                registered_at=self._as_utc(card.created_at),
                revoked_at=card.revoked_at,
                attributed_sessions=int(total or 0),
            )
            for card, unit, registered_by, total in rows
        )

    async def register_charging_card(
        self,
        scope: OrganizationScope,
        card_id: str,
        unit_id: UUID,
        label: str,
    ) -> ChargingCardView:
        """Record that a card answers for a unit, refusing the equipment itself."""
        chargers = (
            (
                await self.session.execute(
                    select(ChargerModel.serial).where(
                        ChargerModel.organization_id == scope.organization_id
                    )
                )
            )
            .scalars()
            .all()
        )
        if card_id in set(chargers):
            raise CardIsTheChargerSerial(card_id)

        unit = await self.session.scalar(
            select(UnitModel).where(
                UnitModel.id == unit_id,
                UnitModel.organization_id == scope.organization_id,
            )
        )
        if unit is None:
            raise UnitNotFound
        existing = await self.session.scalar(
            select(ChargingCardModel).where(
                ChargingCardModel.organization_id == scope.organization_id,
                ChargingCardModel.card_id == card_id,
            )
        )
        if existing is not None:
            raise CardAlreadyRegistered(card_id)

        occurred_at = datetime.now(UTC)
        # The identifier has to exist before the audit event references it: the
        # column default is only applied at flush, and the trail must not be
        # written pointing at nothing.
        card = ChargingCardModel(
            id=uuid4(),
            organization_id=scope.organization_id,
            card_id=card_id,
            unit_id=unit_id,
            label=label,
            registered_by=scope.profile_id,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        self.session.add(card)
        self.session.add(
            AuditEventModel(
                organization_id=scope.organization_id,
                actor_profile_id=scope.profile_id,
                occurred_at=occurred_at,
                event_type="charging_card_registered",
                entity_type="charging_card",
                entity_id=card.id,
                metadata_json={"card_id": card_id, "unit_id": str(unit_id)},
            )
        )
        await self.session.commit()
        for view in await self.list_charging_cards(scope.organization_id):
            if view.card_id == card_id:
                return view
        raise CardNotFound

    async def revoke_charging_card(
        self, scope: OrganizationScope, card_pk: UUID
    ) -> ChargingCardView:
        """Stop a card attributing, without erasing what it already attributed."""
        card = await self.session.scalar(
            select(ChargingCardModel).where(
                ChargingCardModel.id == card_pk,
                ChargingCardModel.organization_id == scope.organization_id,
            )
        )
        if card is None:
            raise CardNotFound
        if card.revoked_at is None:
            occurred_at = datetime.now(UTC)
            card.revoked_at = occurred_at
            self.session.add(
                AuditEventModel(
                    organization_id=scope.organization_id,
                    actor_profile_id=scope.profile_id,
                    occurred_at=occurred_at,
                    event_type="charging_card_revoked",
                    entity_type="charging_card",
                    entity_id=card.id,
                    metadata_json={"card_id": card.card_id},
                )
            )
            await self.session.commit()
        for view in await self.list_charging_cards(scope.organization_id):
            if view.id == card_pk:
                return view
        raise CardNotFound
