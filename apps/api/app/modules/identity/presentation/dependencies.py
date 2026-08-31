from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.application.ports import ScopeRepository, TokenVerifier
from app.modules.identity.application.resolve_scope import ResolveScope
from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.identity.domain.errors import (
    InvalidAccessToken,
    OrganizationAccessDenied,
)
from app.modules.identity.domain.resident_context import ResidentContextNotActive
from app.modules.identity.infrastructure.fixture_jwt import FixtureTokenVerifier
from app.modules.identity.infrastructure.repository import SqlAlchemyScopeRepository
from app.modules.identity.infrastructure.resident_context_repository import (
    SqlAlchemyResidentContextRepository,
)
from app.modules.identity.infrastructure.supabase_jwt import SupabaseJwtVerifier
from app.shared.config import Settings, get_settings
from app.shared.database import get_db_session

bearer_scheme = HTTPBearer(auto_error=False)


def get_token_verifier(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenVerifier:
    if settings.auth_mode == "fixture":
        return FixtureTokenVerifier(settings)
    return SupabaseJwtVerifier(settings)


def get_scope_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ScopeRepository:
    return SqlAlchemyScopeRepository(session, settings.demo_manager_email)


async def authenticated_scope(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    repository: Annotated[ScopeRepository, Depends(get_scope_repository)],
) -> OrganizationScope:
    """Who the bearer token says this is, before any resident context."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return await ResolveScope(verifier, repository).execute(credentials.credentials)
    except InvalidAccessToken as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except OrganizationAccessDenied as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required.",
        ) from error


async def current_scope(
    scope: Annotated[OrganizationScope, Depends(authenticated_scope)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    resident_context_id: Annotated[
        UUID | None, Header(alias="X-Resident-Context")
    ] = None,
) -> OrganizationScope:
    """The effective scope: the same dependency a real resident session uses.

    With an active resident context, the manager's scope narrows to the
    `resident` role and one unit, exactly the scope a resident login would
    produce. Every manager-only endpoint therefore rejects it, which is what
    makes the context read-only by construction rather than by discipline.
    """
    if resident_context_id is None:
        return scope
    if scope.role is not OrganizationRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers can act under a resident context.",
        )
    try:
        context = await SqlAlchemyResidentContextRepository(session).resolve_active(
            resident_context_id, scope.organization_id, scope.profile_id
        )
    except ResidentContextNotActive as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resident context is not active.",
        ) from error
    return OrganizationScope(
        auth_user_id=scope.auth_user_id,
        profile_id=scope.profile_id,
        organization_id=scope.organization_id,
        role=OrganizationRole.RESIDENT,
        unit_id=context.unit_id,
    )
