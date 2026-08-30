from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DATABASE_URL = "sqlite+aiosqlite:///./ev_chargeops_local.db"
POSTGRES_DRIVERS = {"postgres", "postgresql", "postgresql+psycopg"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "test", "demo", "production"] = "local"
    auth_mode: Literal["supabase", "fixture"] = "supabase"
    database_url: str = LOCAL_DATABASE_URL
    supabase_url: str
    supabase_jwt_audience: str = "authenticated"
    supabase_service_role_key: str | None = None
    original_file_store: Literal["local", "supabase"] = "local"
    original_files_root: Path = API_ROOT / ".data" / "original-imports"
    fixture_auth_token: str | None = None
    demo_manager_email: str | None = None

    @model_validator(mode="after")
    def validate_environment_safety(self) -> "Settings":
        if self.auth_mode == "fixture" and self.app_env not in {"local", "test"}:
            raise ValueError("fixture auth is allowed only in local or test")
        if self.auth_mode == "fixture" and not self.fixture_auth_token:
            raise ValueError("fixture auth requires FIXTURE_AUTH_TOKEN")
        if self.original_file_store == "supabase" and not self.supabase_service_role_key:
            raise ValueError(
                "supabase original file store requires SUPABASE_SERVICE_ROLE_KEY"
            )
        if (
            self.app_env in {"demo", "production"}
            and self.original_file_store != "supabase"
        ):
            raise ValueError("demo and production require the supabase original file store")
        if self.app_env in {"demo", "production"} and not self.database_url.startswith(
            tuple(f"{driver}://" for driver in POSTGRES_DRIVERS)
        ):
            raise ValueError("demo and production require a PostgreSQL DATABASE_URL")
        return self

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
