from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain.auth import (
    AuthPrincipal,
    OrganizationRole,
    OrganizationScope,
)
from app.modules.organizations.infrastructure.models import (
    MembershipModel,
    ProfileModel,
)
from scripts.seed_operational_foundation import DEMO_ORGANIZATION_ID


class SqlAlchemyScopeRepository:
    def __init__(
        self,
        session: AsyncSession,
        demo_manager_email: str | None,
    ) -> None:
        self.session = session
        self.demo_manager_email = demo_manager_email

    async def resolve(self, principal: AuthPrincipal) -> OrganizationScope | None:
        scope = await self._resolve_existing(principal)
        if scope is not None:
            return scope

        if principal.email != self.demo_manager_email:
            return None

        try:
            return await self._bootstrap_manager(principal)
        except IntegrityError:
            await self.session.rollback()
            scope = await self._resolve_existing(principal)
            if scope is None:
                raise
            return scope

    async def _resolve_existing(
        self,
        principal: AuthPrincipal,
    ) -> OrganizationScope | None:
        profile = await self.session.scalar(
            select(ProfileModel).where(ProfileModel.auth_user_id == principal.user_id)
        )
        if profile is not None:
            membership = await self._first_membership(profile.id)
            if membership is not None:
                return self._scope(principal, profile, membership)
        return None

    async def _bootstrap_manager(
        self,
        principal: AuthPrincipal,
    ) -> OrganizationScope:
        profile = await self.session.scalar(
            select(ProfileModel).where(ProfileModel.auth_user_id == principal.user_id)
        )
        if profile is None:
            profile = ProfileModel(
                auth_user_id=principal.user_id,
                email=principal.email,
                display_name=principal.email,
            )
            self.session.add(profile)
            await self.session.flush()

        membership = MembershipModel(
            organization_id=DEMO_ORGANIZATION_ID,
            profile_id=profile.id,
            unit_id=None,
            role=OrganizationRole.MANAGER.value,
        )
        self.session.add(membership)
        await self.session.commit()
        return self._scope(principal, profile, membership)

    async def _first_membership(self, profile_id: UUID) -> MembershipModel | None:
        return await self.session.scalar(
            select(MembershipModel)
            .where(MembershipModel.profile_id == profile_id)
            .order_by(MembershipModel.created_at, MembershipModel.id)
            .limit(1)
        )

    @staticmethod
    def _scope(
        principal: AuthPrincipal,
        profile: ProfileModel,
        membership: MembershipModel,
    ) -> OrganizationScope:
        return OrganizationScope(
            auth_user_id=principal.user_id,
            profile_id=profile.id,
            organization_id=membership.organization_id,
            role=OrganizationRole(membership.role),
            unit_id=membership.unit_id,
        )
