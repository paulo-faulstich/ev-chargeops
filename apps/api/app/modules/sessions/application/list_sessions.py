from datetime import UTC, datetime

from app.modules.identity.domain.auth import OrganizationScope
from app.modules.sessions.application.ports import SessionRepository
from app.modules.sessions.domain.errors import InvalidPeriod
from app.modules.sessions.domain.models import SessionView


class ListSessions:
    def __init__(self, repository: SessionRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        *,
        period: str | None,
        status: str | None,
    ) -> tuple[SessionView, ...]:
        self._validate_period(period)
        return await self.repository.list_sessions(
            scope.organization_id,
            period=period,
            status=status,
        )

    @staticmethod
    def _validate_period(period: str | None) -> None:
        if period is None:
            return
        try:
            parsed = datetime.strptime(period, "%Y-%m").replace(tzinfo=UTC)
        except ValueError as error:
            raise InvalidPeriod from error
        if parsed.strftime("%Y-%m") != period:
            raise InvalidPeriod
