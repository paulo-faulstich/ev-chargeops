from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.identity.domain.resident_context import (
    ResidentContextNotActive,
    ResidentContextUnitNotFound,
)
from app.modules.identity.infrastructure.resident_context_repository import (
    SqlAlchemyResidentContextRepository,
)
from app.modules.identity.presentation.dependencies import (
    authenticated_scope,
    current_scope,
)
from app.shared.config import Settings, get_settings
from app.shared.database import get_db_session

router = APIRouter(prefix="/v1", tags=["identity"])


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.title() for part in rest)


class MeResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    profile_id: UUID
    organization_id: UUID
    role: OrganizationRole
    unit_id: UUID | None


@router.get("/me", response_model=MeResponse, response_model_by_alias=True)
async def me(
    scope: Annotated[OrganizationScope, Depends(current_scope)],
) -> MeResponse:
    return MeResponse(
        profile_id=scope.profile_id,
        organization_id=scope.organization_id,
        role=scope.role,
        unit_id=scope.unit_id,
    )


class EnterResidentContextRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    unit_id: UUID


class ResidentContextResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: UUID
    unit_id: UUID
    unit_code: str
    unit_name: str
    expires_at: datetime


def _resident_context_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyResidentContextRepository:
    return SqlAlchemyResidentContextRepository(session)


@router.post(
    "/resident-context",
    response_model=ResidentContextResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def enter_resident_context(
    payload: EnterResidentContextRequest,
    scope: Annotated[OrganizationScope, Depends(authenticated_scope)],
    repository: Annotated[
        SqlAlchemyResidentContextRepository, Depends(_resident_context_repository)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResidentContextResponse:
    """See exactly what this unit's resident would see, for a short while.

    The entrance is audited with actor, unit and instant. The context resolves
    through the same authorization dependency a real resident session would
    use, so every write is rejected while it is active.
    """
    if scope.role is not OrganizationRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager role required.",
        )
    try:
        context = await repository.enter(
            scope.organization_id,
            scope.profile_id,
            payload.unit_id,
            settings.resident_context_ttl_seconds,
        )
    except ResidentContextUnitNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unidade não encontrada.",
        ) from error
    return ResidentContextResponse(
        id=context.id,
        unit_id=context.unit_id,
        unit_code=context.unit_code,
        unit_name=context.unit_name,
        expires_at=context.expires_at,
    )


@router.delete(
    "/resident-context",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def exit_resident_context(
    scope: Annotated[OrganizationScope, Depends(authenticated_scope)],
    repository: Annotated[
        SqlAlchemyResidentContextRepository, Depends(_resident_context_repository)
    ],
    resident_context_id: Annotated[UUID, Header(alias="X-Resident-Context")],
) -> None:
    """One-click exit. The departure is audited like the entrance was."""
    if scope.role is not OrganizationRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager role required.",
        )
    try:
        await repository.exit(
            resident_context_id, scope.organization_id, scope.profile_id
        )
    except ResidentContextNotActive as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contexto de morador não encontrado.",
        ) from error
