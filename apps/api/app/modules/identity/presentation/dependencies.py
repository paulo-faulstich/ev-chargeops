from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.application.ports import ScopeRepository, TokenVerifier
from app.modules.identity.application.resolve_scope import ResolveScope
from app.modules.identity.domain.auth import OrganizationScope
from app.modules.identity.domain.errors import (
    InvalidAccessToken,
    OrganizationAccessDenied,
)
from app.modules.identity.infrastructure.fixture_jwt import FixtureTokenVerifier
from app.modules.identity.infrastructure.repository import SqlAlchemyScopeRepository
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


async def current_scope(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    repository: Annotated[ScopeRepository, Depends(get_scope_repository)],
) -> OrganizationScope:
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
