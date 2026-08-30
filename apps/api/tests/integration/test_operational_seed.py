import pytest

from app.modules.organizations.infrastructure.models import (
    ChargerModel,
    OrganizationModel,
    SiteModel,
    UnitModel,
)
from scripts.seed_operational_foundation import seed_operational_foundation
from tests.integration.conftest import count_rows

pytestmark = pytest.mark.asyncio


async def test_seed_is_repeatable(async_session) -> None:
    await seed_operational_foundation(async_session)
    await seed_operational_foundation(async_session)

    assert await count_rows(async_session, OrganizationModel) == 1
    assert await count_rows(async_session, SiteModel) == 1
    assert await count_rows(async_session, ChargerModel) == 1
    assert await count_rows(async_session, UnitModel) == 4
