from datetime import datetime
from uuid import UUID

from app.modules.identity.domain.auth import OrganizationScope
from app.modules.sessions.application.ports import SessionRepository
from app.modules.sessions.domain.models import (
    AssignmentResult,
    AssignmentUnitView,
    SessionView,
)


class RecordingSessionRepository(SessionRepository):
    def __init__(
        self,
        *,
        sessions: tuple[SessionView, ...] = (),
        units: tuple[AssignmentUnitView, ...] = (),
    ) -> None:
        self.sessions = sessions
        self.units = units
        self.list_session_calls: list[tuple[UUID, str | None, str | None]] = []
        self.list_assignment_unit_calls: list[UUID] = []

    async def list_sessions(
        self,
        organization_id: UUID,
        *,
        period: str | None,
        status: str | None,
    ) -> tuple[SessionView, ...]:
        self.list_session_calls.append((organization_id, period, status))
        return self.sessions

    async def list_assignment_units(
        self,
        organization_id: UUID,
    ) -> tuple[AssignmentUnitView, ...]:
        self.list_assignment_unit_calls.append(organization_id)
        return self.units

    async def assign_session(
        self,
        scope: OrganizationScope,
        session_id: UUID,
        unit_id: UUID,
        justification: str,
        occurred_at: datetime,
    ) -> AssignmentResult:
        raise NotImplementedError
