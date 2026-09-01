"""Registering which unit a charging card answers for.

The charger authenticates the card and the SEMS+ report carries its id. What
neither can know is who pays for it. These use cases are where a manager says
so, once, on the record — and where the product refuses to accept the
equipment's own serial as if it were a person.
"""

from uuid import UUID

from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.sessions.application.ports import SessionRepository
from app.modules.sessions.domain.errors import AssignmentForbidden
from app.modules.sessions.domain.models import ChargingCardView


def _require_manager(scope: OrganizationScope) -> None:
    if scope.role is not OrganizationRole.MANAGER:
        raise AssignmentForbidden


class ListChargingCards:
    def __init__(self, repository: SessionRepository) -> None:
        self.repository = repository

    async def execute(
        self, scope: OrganizationScope
    ) -> tuple[ChargingCardView, ...]:
        _require_manager(scope)
        return await self.repository.list_charging_cards(scope.organization_id)


class RegisterChargingCard:
    def __init__(self, repository: SessionRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        card_id: str,
        unit_id: UUID,
        label: str,
    ) -> ChargingCardView:
        _require_manager(scope)
        return await self.repository.register_charging_card(
            scope, card_id.strip(), unit_id, label.strip()
        )


class RevokeChargingCard:
    def __init__(self, repository: SessionRepository) -> None:
        self.repository = repository

    async def execute(
        self, scope: OrganizationScope, card_pk: UUID
    ) -> ChargingCardView:
        _require_manager(scope)
        return await self.repository.revoke_charging_card(scope, card_pk)
