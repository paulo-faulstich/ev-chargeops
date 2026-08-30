from app.modules.identity.application.ports import ScopeRepository, TokenVerifier
from app.modules.identity.domain.auth import OrganizationScope
from app.modules.identity.domain.errors import OrganizationAccessDenied


class ResolveScope:
    def __init__(self, verifier: TokenVerifier, repository: ScopeRepository) -> None:
        self.verifier = verifier
        self.repository = repository

    async def execute(self, token: str) -> OrganizationScope:
        principal = self.verifier.verify(token)
        scope = await self.repository.resolve(principal)
        if scope is None:
            raise OrganizationAccessDenied
        return scope
