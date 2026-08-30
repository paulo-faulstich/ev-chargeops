import pytest
from pydantic import ValidationError

from app.shared.config import Settings


def test_fixture_auth_is_allowed_for_tests() -> None:
    settings = Settings(
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
        Settings(
            app_env="production",
            auth_mode="fixture",
            database_url="postgresql+psycopg://example.invalid/postgres",
            supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
            fixture_auth_token="fixture-manager-token",
        )


def test_demo_requires_supabase_original_file_store_and_service_key() -> None:
    with pytest.raises(ValidationError, match="supabase original file store"):
        Settings(
            app_env="demo",
            auth_mode="supabase",
            database_url="postgresql://example.invalid/postgres",
            supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
            original_file_store="supabase",
        )


def test_local_settings_default_to_sqlite_without_database_url() -> None:
    settings = Settings(
        app_env="local",
        auth_mode="fixture",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )

    assert settings.database_url == "sqlite+aiosqlite:///./ev_chargeops_local.db"


def test_production_rejects_non_postgres_database_url() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(
            app_env="production",
            auth_mode="supabase",
            database_url="sqlite+aiosqlite:///./ev_chargeops.db",
            supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
            original_file_store="supabase",
            supabase_service_role_key="service-key",
        )
