from typing import Protocol

from app.modules.identity.domain.auth import AuthPrincipal, OrganizationScope


class TokenVerifier(Protocol):
    def verify(self, token: str) -> AuthPrincipal: ...


class ScopeRepository(Protocol):
    async def resolve(self, principal: AuthPrincipal) -> OrganizationScope | None: ...
