from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.sessions.application.ports import SessionRepository
from app.modules.sessions.domain.errors import AssignmentForbidden
from app.modules.sessions.domain.models import AssignmentResult, normalize_justification


class AssignSession:
    def __init__(
        self,
        repository: SessionRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(
        self,
        scope: OrganizationScope,
        session_id: UUID,
        unit_id: UUID,
        justification: str,
    ) -> AssignmentResult:
        if scope.role is not OrganizationRole.MANAGER:
            raise AssignmentForbidden

        normalized_justification = normalize_justification(justification)
        return await self.repository.assign_session(
            scope,
            session_id,
            unit_id,
            normalized_justification,
            self.clock(),
        )
