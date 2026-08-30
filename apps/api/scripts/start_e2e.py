import asyncio
import os
import sys
from pathlib import Path

import uvicorn
from alembic.config import Config

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.shared.config import Settings
from app.shared.database import (
    create_engine_from_settings,
    create_session_factory,
)
from scripts.seed_operational_foundation import (
    seed_operational_foundation,
)


def validate_database_path(database_path: Path, allowed_root: Path) -> Path:
    resolved_database_path = database_path.resolve()
    resolved_allowed_root = allowed_root.resolve()
    if (
        resolved_database_path.suffix != ".sqlite3"
        or resolved_allowed_root not in resolved_database_path.parents
    ):
        raise RuntimeError(
            "E2E database must be a .sqlite3 file under apps/web/test-results"
        )
    return resolved_database_path


def build_e2e_environment(
    database_url: str,
    allowed_root: Path,
) -> dict[str, str]:
    return {
        "APP_ENV": "test",
        "AUTH_MODE": "fixture",
        "FIXTURE_AUTH_TOKEN": "fixture-manager-token",
        "DATABASE_URL": database_url,
        "SUPABASE_URL": "https://lgjohsxipfctgooiuqnv.supabase.co",
        "DEMO_MANAGER_EMAIL": "manager@example.test",
        "ORIGINAL_FILE_STORE": "local",
        "ORIGINAL_FILES_ROOT": str(allowed_root / "original-files"),
        "SUPABASE_SERVICE_ROLE_KEY": "",
    }


def configure_e2e_environment(
    database_url: str,
    allowed_root: Path,
) -> Settings:
    os.environ.update(build_e2e_environment(database_url, allowed_root))
    return Settings()  # type: ignore[call-arg]


async def seed(settings: Settings) -> None:
    engine = create_engine_from_settings(settings)
    async with create_session_factory(engine)() as session:
        await seed_operational_foundation(session)
    await engine.dispose()


def main() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    allowed_root = (repository_root / "apps/web/test-results").resolve()
    database_path = validate_database_path(
        Path(os.environ["E2E_DATABASE_PATH"]),
        allowed_root,
    )
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_path.unlink(missing_ok=True)

    database_url = f"sqlite+aiosqlite:///{database_path}"
    settings = configure_e2e_environment(database_url, allowed_root)
    config = Config(str(repository_root / "apps/api/alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    asyncio.run(seed(settings))
    uvicorn.run("app.main:app", app_dir=str(repository_root / "apps/api"), port=8001)


if __name__ == "__main__":
    main()
