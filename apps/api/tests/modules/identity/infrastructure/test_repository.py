import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.modules.identity.domain.auth import AuthPrincipal, OrganizationRole
from app.modules.identity.infrastructure.repository import SqlAlchemyScopeRepository
from app.modules.organizations.infrastructure.models import (
    MembershipModel,
    ProfileModel,
)
from app.shared.sqlalchemy import Base
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


@dataclass
class BootstrapRace:
    reads: int = 0
    both_read: asyncio.Event = field(default_factory=asyncio.Event)
    winner_committed: asyncio.Event = field(default_factory=asyncio.Event)

    async def after_missing_read(self, *, winner: bool) -> None:
        self.reads += 1
        if self.reads == 2:
            self.both_read.set()
        await self.both_read.wait()
        if not winner:
            await self.winner_committed.wait()


class CoordinatedSession:
    def __init__(
        self,
        session: AsyncSession,
        race: BootstrapRace,
        *,
        winner: bool,
    ) -> None:
        self.session = session
        self.race = race
        self.winner = winner
        self.scalar_calls = 0

    async def scalar(self, statement):
        result = await self.session.scalar(statement)
        self.scalar_calls += 1
        if self.scalar_calls == 1:
            assert result is None
            await self.race.after_missing_read(winner=self.winner)
        return result

    def add(self, instance: Any) -> None:
        self.session.add(instance)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
        if self.winner:
            self.race.winner_committed.set()

    async def rollback(self) -> None:
        await self.session.rollback()


async def test_concurrent_bootstrap_resolves_same_scope_for_both_requests(
    tmp_path: Path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bootstrap.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as seed_session:
        await seed_operational_foundation(seed_session)

    principal = AuthPrincipal(UUID(int=53), MANAGER_EMAIL)
    race = BootstrapRace()
    try:
        async with factory() as winner_session, factory() as loser_session:
            winner = SqlAlchemyScopeRepository(
                cast(
                    AsyncSession,
                    CoordinatedSession(winner_session, race, winner=True),
                ),
                demo_manager_email=MANAGER_EMAIL,
            )
            loser = SqlAlchemyScopeRepository(
                cast(
                    AsyncSession,
                    CoordinatedSession(loser_session, race, winner=False),
                ),
                demo_manager_email=MANAGER_EMAIL,
            )

            winner_scope, loser_scope = await asyncio.gather(
                winner.resolve(principal),
                loser.resolve(principal),
            )

        async with factory() as verification_session:
            assert winner_scope == loser_scope
            assert await row_count(verification_session, ProfileModel) == 1
            assert await row_count(verification_session, MembershipModel) == 1
    finally:
        await engine.dispose()


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
