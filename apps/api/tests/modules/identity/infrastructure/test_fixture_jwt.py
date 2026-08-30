from uuid import UUID

import pytest

from app.modules.identity.domain.errors import InvalidAccessToken
from app.modules.identity.infrastructure.fixture_jwt import FixtureTokenVerifier
from app.shared.config import Settings


def settings() -> Settings:
    return Settings(
        app_env="test",
        auth_mode="fixture",
        database_url="sqlite+aiosqlite:///:memory:",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
        demo_manager_email="manager@example.test",
    )


def test_fixture_verifier_accepts_only_configured_token() -> None:
    principal = FixtureTokenVerifier(settings()).verify("fixture-manager-token")

    assert principal.user_id == UUID("50000000-0000-0000-0000-000000000001")
    assert principal.email == "manager@example.test"


@pytest.mark.parametrize("token", ["", "fixture-manager-token ", "other-token"])
def test_fixture_verifier_rejects_any_other_token(token: str) -> None:
    with pytest.raises(InvalidAccessToken):
        FixtureTokenVerifier(settings()).verify(token)
