from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_initial_migration_creates_operational_tables(tmp_path: Path) -> None:
    database = tmp_path / "migration.db"
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")

    command.upgrade(config, "head")

    tables = set(inspect(create_engine(f"sqlite:///{database}")).get_table_names())
    assert {
        "organizations",
        "sites",
        "chargers",
        "units",
        "profiles",
        "memberships",
        "import_batches",
        "raw_import_records",
        "charging_sessions",
        "audit_events",
    } <= tables
