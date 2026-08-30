from dataclasses import dataclass
from uuid import UUID

import pytest

from app.modules.identity.application.resolve_scope import ResolveScope
from app.modules.identity.domain.auth import (
    AuthPrincipal,
    OrganizationRole,
    OrganizationScope,
)
from app.modules.identity.domain.errors import OrganizationAccessDenied

pytestmark = pytest.mark.asyncio


@dataclass
class FakeVerifier:
    user_id: UUID
    email: str

    def verify(self, token: str) -> AuthPrincipal:
        assert token == "signed-token"
        return AuthPrincipal(self.user_id, self.email)


class FakeScopeRepository:
    organization_id = UUID(int=20)

    def __init__(self, role: OrganizationRole | None) -> None:
        self.role = role

    async def resolve(self, principal: AuthPrincipal) -> OrganizationScope | None:
        if self.role is None:
            return None
        return OrganizationScope(
            auth_user_id=principal.user_id,
            profile_id=UUID(int=30),
            organization_id=self.organization_id,
            role=self.role,
            unit_id=None,
        )


async def test_resolve_scope_uses_verified_subject_and_membership() -> None:
    verifier = FakeVerifier(user_id=UUID(int=10), email="manager@example.test")
    repository = FakeScopeRepository(role=OrganizationRole.MANAGER)

    scope = await ResolveScope(verifier, repository).execute("signed-token")

    assert scope.auth_user_id == UUID(int=10)
    assert scope.organization_id == repository.organization_id
    assert scope.role is OrganizationRole.MANAGER


async def test_resolve_scope_rejects_user_without_membership() -> None:
    with pytest.raises(OrganizationAccessDenied):
        await ResolveScope(
            FakeVerifier(UUID(int=11), "outsider@example.test"),
            FakeScopeRepository(role=None),
        ).execute("signed-token")
