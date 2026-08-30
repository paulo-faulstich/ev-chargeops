from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.identity.presentation.dependencies import current_scope

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
