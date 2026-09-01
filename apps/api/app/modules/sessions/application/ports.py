from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.auth import OrganizationScope
from app.modules.sessions.domain.models import (
    AssignmentResult,
    AssignmentUnitView,
    ChargingCardView,
    SessionView,
)


class SessionRepository(Protocol):
    async def list_sessions(
        self,
        organization_id: UUID,
        *,
        period: str | None,
        status: str | None,
    ) -> tuple[SessionView, ...]: ...

    async def list_assignment_units(
        self,
        organization_id: UUID,
    ) -> tuple[AssignmentUnitView, ...]: ...

    async def assign_session(
        self,
        scope: OrganizationScope,
        session_id: UUID,
        unit_id: UUID,
        justification: str,
        occurred_at: datetime,
    ) -> AssignmentResult: ...

    async def list_charging_cards(
        self,
        organization_id: UUID,
    ) -> tuple[ChargingCardView, ...]: ...

    async def register_charging_card(
        self,
        scope: OrganizationScope,
        card_id: str,
        unit_id: UUID,
        label: str,
    ) -> ChargingCardView: ...

    async def revoke_charging_card(
        self,
        scope: OrganizationScope,
        card_pk: UUID,
    ) -> ChargingCardView: ...
