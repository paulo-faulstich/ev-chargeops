from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain.auth import AuthPrincipal, OrganizationRole
from app.modules.identity.infrastructure.repository import SqlAlchemyScopeRepository
from app.modules.organizations.infrastructure.models import (
    MembershipModel,
    ProfileModel,
)
from scripts.seed_operational_foundation import (
    DEMO_ORGANIZATION_ID,
    DEMO_UNIT_IDS,
    seed_operational_foundation,
)

pytestmark = pytest.mark.asyncio
MANAGER_EMAIL = "manager@example.test"


async def row_count(session: AsyncSession, model: type) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def test_resolve_uses_persisted_membership_scope(
    async_session: AsyncSession,
) -> None:
    await seed_operational_foundation(async_session)
    auth_user_id = UUID(int=40)
    profile = ProfileModel(
        auth_user_id=auth_user_id,
        email="resident@example.test",
        display_name="resident@example.test",
    )
    async_session.add(profile)
    await async_session.flush()
    async_session.add(
        MembershipModel(
            organization_id=DEMO_ORGANIZATION_ID,
            profile_id=profile.id,
            unit_id=DEMO_UNIT_IDS["A-101"],
            role=OrganizationRole.RESIDENT.value,
        )
    )
    await async_session.commit()

    scope = await SqlAlchemyScopeRepository(
        async_session,
        demo_manager_email=MANAGER_EMAIL,
    ).resolve(AuthPrincipal(auth_user_id, "changed@example.test"))

    assert scope is not None
    assert scope.auth_user_id == auth_user_id
    assert scope.profile_id == profile.id
    assert scope.organization_id == DEMO_ORGANIZATION_ID
    assert scope.role is OrganizationRole.RESIDENT
    assert scope.unit_id == DEMO_UNIT_IDS["A-101"]


async def test_bootstrap_creates_allowlisted_manager_only_once(
    async_session: AsyncSession,
) -> None:
    await seed_operational_foundation(async_session)
    repository = SqlAlchemyScopeRepository(
        async_session,
        demo_manager_email=MANAGER_EMAIL,
    )
    principal = AuthPrincipal(UUID(int=50), MANAGER_EMAIL)

    first_scope = await repository.resolve(principal)
    second_scope = await repository.resolve(principal)

    assert first_scope is not None
    assert second_scope == first_scope
    assert first_scope.auth_user_id == principal.user_id
    assert first_scope.organization_id == DEMO_ORGANIZATION_ID
    assert first_scope.role is OrganizationRole.MANAGER
    assert first_scope.unit_id is None
    assert await row_count(async_session, ProfileModel) == 1
    assert await row_count(async_session, MembershipModel) == 1


@pytest.mark.parametrize(
    "email",
    ["other@example.test", "Manager@example.test", "manager@example.test "],
)
async def test_bootstrap_does_not_provision_other_email(
    email: str,
    async_session: AsyncSession,
) -> None:
    await seed_operational_foundation(async_session)
    repository = SqlAlchemyScopeRepository(
        async_session,
        demo_manager_email=MANAGER_EMAIL,
    )

    scope = await repository.resolve(AuthPrincipal(UUID(int=51), email))

    assert scope is None
    assert await row_count(async_session, ProfileModel) == 0
    assert await row_count(async_session, MembershipModel) == 0


async def test_bootstrap_never_runs_without_allowlisted_email(
    async_session: AsyncSession,
) -> None:
    await seed_operational_foundation(async_session)

    scope = await SqlAlchemyScopeRepository(
        async_session,
        demo_manager_email=None,
    ).resolve(AuthPrincipal(UUID(int=52), MANAGER_EMAIL))

    assert scope is None
