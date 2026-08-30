from app.modules.identity.domain.auth import OrganizationScope
from app.modules.sessions.application.ports import SessionRepository
from app.modules.sessions.domain.models import AssignmentUnitView


class ListAssignmentUnits:
    def __init__(self, repository: SessionRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
    ) -> tuple[AssignmentUnitView, ...]:
        return await self.repository.list_assignment_units(scope.organization_id)
