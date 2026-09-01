import pytest
from pydantic import ValidationError

from app.shared.config import Settings


def build_settings(**overrides: object) -> Settings:
    """Build settings from the arguments alone.

    `Settings` reads `apps/api/.env` by design, which is right in production
    and wrong in a test: a rule like "demo requires a service role key" would
    be satisfied by whatever the developer happens to have on disk, and the
    suite would pass or fail depending on the machine it ran on. `_env_file`
    set to `None` makes each case state its own world.
    """
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_fixture_auth_is_allowed_for_tests() -> None:
    settings = build_settings(
        app_env="test",
        auth_mode="fixture",
        database_url="sqlite+aiosqlite:///:memory:",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )

    assert settings.supabase_issuer == (
        "https://lgjohsxipfctgooiuqnv.supabase.co/auth/v1"
    )
    assert settings.supabase_jwks_url.endswith("/.well-known/jwks.json")


def test_fixture_auth_fails_closed_in_production() -> None:
    with pytest.raises(ValidationError, match="fixture auth"):
        build_settings(
            app_env="production",
            auth_mode="fixture",
            database_url="postgresql+psycopg://example.invalid/postgres",
            supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
            fixture_auth_token="fixture-manager-token",
        )


def test_demo_requires_supabase_original_file_store_and_service_key() -> None:
    with pytest.raises(ValidationError, match="supabase original file store"):
        build_settings(
            app_env="demo",
            auth_mode="supabase",
            database_url="postgresql://example.invalid/postgres",
            supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
            original_file_store="supabase",
        )


def test_local_settings_default_to_sqlite_without_database_url() -> None:
    settings = build_settings(
        app_env="local",
        auth_mode="fixture",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )

    assert settings.database_url == "sqlite+aiosqlite:///./ev_chargeops_local.db"


def test_production_rejects_non_postgres_database_url() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        build_settings(
            app_env="production",
            auth_mode="supabase",
            database_url="sqlite+aiosqlite:///./ev_chargeops.db",
            supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
            original_file_store="supabase",
            supabase_service_role_key="service-key",
        )
