"""The resident context: one unit, read-only, audited, short-lived.

These tests go through the HTTP surface on purpose: the guarantee under test is
that the context flows through the same authorization dependency as any other
request, so manager-only endpoints reject it without knowing it exists.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.modules.audit.infrastructure.models import AuditEventModel
from app.modules.identity.infrastructure.models import ResidentContextModel
from app.shared.config import Settings, get_settings
from app.shared.database import get_db_session
from scripts.seed_operational_foundation import (
    DEMO_UNIT_IDS,
    seed_operational_foundation,
)

pytestmark = pytest.mark.asyncio

MANAGER_HEADERS = {"Authorization": "Bearer fixture-manager-token"}
UNIT_ID = next(iter(DEMO_UNIT_IDS.values()))


def identity_settings() -> Settings:
    return Settings(
        app_env="test",
        auth_mode="fixture",
        database_url="sqlite+aiosqlite:///:memory:",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
        demo_manager_email="manager@example.test",
    )


async def request(
    method: str,
    path: str,
    async_session: AsyncSession,
    **kwargs: object,
) -> httpx.Response:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield async_session

    app.dependency_overrides[get_settings] = identity_settings
    app.dependency_overrides[get_db_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.request(method, path, **kwargs)
    finally:
        app.dependency_overrides.clear()


async def enter_context(async_session: AsyncSession) -> dict[str, str]:
    await seed_operational_foundation(async_session)
    response = await request(
        "POST",
        "/v1/resident-context",
        async_session,
        headers=MANAGER_HEADERS,
        json={"unitId": str(UNIT_ID)},
    )
    assert response.status_code == 201
    return dict(response.json())


async def test_entering_returns_the_scoped_context_and_audits(
    async_session: AsyncSession,
) -> None:
    context = await enter_context(async_session)

    assert context["unitId"] == str(UNIT_ID)
    assert context["unitCode"] in DEMO_UNIT_IDS
    audit = (
        (
            await async_session.execute(
                select(AuditEventModel).where(
                    AuditEventModel.event_type == "resident_context_entered"
                )
            )
        )
        .scalars()
        .one()
    )
    assert audit.entity_id == UNIT_ID
    assert audit.metadata_json["resident_context_id"] == context["id"]


async def test_the_context_narrows_me_to_the_resident_role(
    async_session: AsyncSession,
) -> None:
    context = await enter_context(async_session)

    response = await request(
        "GET",
        "/v1/me",
        async_session,
        headers={**MANAGER_HEADERS, "X-Resident-Context": context["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "resident"
    assert body["unitId"] == str(UNIT_ID)


async def test_writes_are_rejected_while_the_context_is_active(
    async_session: AsyncSession,
) -> None:
    """A manager-only endpoint refuses the narrowed scope without knowing
    the resident context exists."""
    context = await enter_context(async_session)

    response = await request(
        "POST",
        "/v1/billing-periods",
        async_session,
        headers={**MANAGER_HEADERS, "X-Resident-Context": context["id"]},
        json={"periodValue": "2026-05"},
    )

    assert response.status_code == 403


async def test_an_expired_context_stops_resolving(
    async_session: AsyncSession,
) -> None:
    context = await enter_context(async_session)
    row = await async_session.get(ResidentContextModel, UUID(context["id"]))
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await async_session.commit()

    response = await request(
        "GET",
        "/v1/me",
        async_session,
        headers={**MANAGER_HEADERS, "X-Resident-Context": context["id"]},
    )

    assert response.status_code == 403


async def test_exit_audits_and_the_context_stops_resolving(
    async_session: AsyncSession,
) -> None:
    context = await enter_context(async_session)

    exit_response = await request(
        "DELETE",
        "/v1/resident-context",
        async_session,
        headers={**MANAGER_HEADERS, "X-Resident-Context": context["id"]},
    )
    assert exit_response.status_code == 204

    me_response = await request(
        "GET",
        "/v1/me",
        async_session,
        headers={**MANAGER_HEADERS, "X-Resident-Context": context["id"]},
    )
    assert me_response.status_code == 403

    audit = (
        (
            await async_session.execute(
                select(AuditEventModel).where(
                    AuditEventModel.event_type == "resident_context_exited"
                )
            )
        )
        .scalars()
        .one()
    )
    assert audit.entity_id == UNIT_ID


async def test_entering_for_an_unknown_unit_is_not_found(
    async_session: AsyncSession,
) -> None:
    await seed_operational_foundation(async_session)

    response = await request(
        "POST",
        "/v1/resident-context",
        async_session,
        headers=MANAGER_HEADERS,
        json={"unitId": str(UUID(int=999))},
    )

    assert response.status_code == 404
