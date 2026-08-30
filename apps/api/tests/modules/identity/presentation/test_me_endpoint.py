from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.modules.identity.domain.auth import AuthPrincipal
from app.modules.identity.presentation.dependencies import get_token_verifier
from app.modules.organizations.infrastructure.models import ProfileModel
from app.shared.config import Settings, get_settings
from app.shared.database import get_db_session
from scripts.seed_operational_foundation import (
    DEMO_ORGANIZATION_ID,
    seed_operational_foundation,
)

pytestmark = pytest.mark.asyncio


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


async def test_me_returns_401_when_bearer_is_missing(
    async_session: AsyncSession,
) -> None:
    response = await request("GET", "/v1/me", async_session)

    assert response.status_code == 401


async def test_me_returns_401_when_bearer_is_invalid(
    async_session: AsyncSession,
) -> None:
    response = await request(
        "GET",
        "/v1/me",
        async_session,
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


@dataclass
class OutsiderVerifier:
    def verify(self, token: str) -> AuthPrincipal:
        assert token == "verified-outsider-token"
        return AuthPrincipal(UUID(int=60), "outsider@example.test")


async def test_me_returns_403_for_verified_user_without_membership(
    async_session: AsyncSession,
) -> None:
    app.dependency_overrides[get_token_verifier] = OutsiderVerifier
    response = await request(
        "GET",
        "/v1/me",
        async_session,
        headers={"Authorization": "Bearer verified-outsider-token"},
    )

    assert response.status_code == 403


async def test_me_returns_only_resolved_organization_scope(
    async_session: AsyncSession,
) -> None:
    await seed_operational_foundation(async_session)

    response = await request(
        "GET",
        "/v1/me",
        async_session,
        headers={"Authorization": "Bearer fixture-manager-token"},
    )

    assert response.status_code == 200
    profile_id = await async_session.scalar(
        select(ProfileModel.id).where(
            ProfileModel.auth_user_id
            == UUID("50000000-0000-0000-0000-000000000001")
        )
    )
    assert response.json() == {
        "profileId": str(profile_id),
        "organizationId": str(DEMO_ORGANIZATION_ID),
        "role": "manager",
        "unitId": None,
    }
