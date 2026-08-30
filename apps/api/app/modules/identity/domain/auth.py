from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class OrganizationRole(StrEnum):
    MANAGER = "manager"
    RESIDENT = "resident"
    TECHNICAL_OPERATOR = "technical_operator"


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    user_id: UUID
    email: str


@dataclass(frozen=True, slots=True)
class OrganizationScope:
    auth_user_id: UUID
    profile_id: UUID
    organization_id: UUID
    role: OrganizationRole
    unit_id: UUID | None
