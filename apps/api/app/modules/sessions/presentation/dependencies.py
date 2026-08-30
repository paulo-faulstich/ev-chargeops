from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.identity.presentation.dependencies import current_scope
from app.modules.sessions.application.assign_session import AssignSession
from app.modules.sessions.application.list_assignment_units import ListAssignmentUnits
from app.modules.sessions.application.list_sessions import ListSessions
from app.modules.sessions.application.ports import SessionRepository
from app.modules.sessions.infrastructure.repository import SqlAlchemySessionRepository
from app.shared.database import get_db_session


def get_session_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SessionRepository:
    return SqlAlchemySessionRepository(session)


def get_list_sessions(
    repository: Annotated[SessionRepository, Depends(get_session_repository)],
) -> ListSessions:
    return ListSessions(repository)


def get_list_assignment_units(
    repository: Annotated[SessionRepository, Depends(get_session_repository)],
) -> ListAssignmentUnits:
    return ListAssignmentUnits(repository)


def get_assign_session(
    repository: Annotated[SessionRepository, Depends(get_session_repository)],
) -> AssignSession:
    return AssignSession(repository)


async def manager_scope(
    scope: Annotated[OrganizationScope, Depends(current_scope)],
) -> OrganizationScope:
    if scope.role is not OrganizationRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager role required.",
        )
    return scope
