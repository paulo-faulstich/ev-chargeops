import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parents[1]))

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organizations.infrastructure.models import (
    ChargerModel,
    OrganizationModel,
    SiteModel,
    UnitModel,
)
from app.shared.config import get_settings
from app.shared.database import (
    create_engine_from_settings,
    create_session_factory,
)
from app.shared.sqlalchemy import UuidPrimaryKeyMixin

DEMO_ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
DEMO_SITE_ID = UUID("20000000-0000-0000-0000-000000000001")
DEMO_CHARGER_ID = UUID("30000000-0000-0000-0000-000000000001")
DEMO_UNIT_IDS = {
    code: UUID(f"40000000-0000-0000-0000-{index:012d}")
    for index, code in enumerate(("A-101", "A-102", "A-103", "A-104"), start=1)
}


async def add_if_missing(
    session: AsyncSession,
    instance: UuidPrimaryKeyMixin,
) -> None:
    if await session.get(type(instance), instance.id) is None:
        session.add(instance)


async def seed_operational_foundation(session: AsyncSession) -> None:
    await add_if_missing(
        session,
        OrganizationModel(
            id=DEMO_ORGANIZATION_ID,
            name="LAB FIAP Eco Smart Home",
        ),
    )
    await add_if_missing(
        session,
        SiteModel(
            id=DEMO_SITE_ID,
            organization_id=DEMO_ORGANIZATION_ID,
            name="LAB FIAP Eco Smart Home",
            timezone="America/Sao_Paulo",
        ),
    )
    await add_if_missing(
        session,
        ChargerModel(
            id=DEMO_CHARGER_ID,
            organization_id=DEMO_ORGANIZATION_ID,
            site_id=DEMO_SITE_ID,
            serial="97500NAP25BL0008",
            name="GoodWe HCA G2",
            nominal_power_kw=Decimal("11.000"),
        ),
    )
    for code, identifier in DEMO_UNIT_IDS.items():
        await add_if_missing(
            session,
            UnitModel(
                id=identifier,
                organization_id=DEMO_ORGANIZATION_ID,
                code=code,
                display_name=f"Unidade {code}",
            ),
        )
    await session.commit()


async def main() -> None:
    engine = create_engine_from_settings(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            await seed_operational_foundation(session)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
