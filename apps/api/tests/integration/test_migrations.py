from io import StringIO
from pathlib import Path
from typing import NoReturn

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext import asyncio as sqlalchemy_asyncio

from alembic import command

OPERATIONAL_TABLES = {
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
}


def upgrade_database(
    tmp_path: Path,
    revision: str = "head",
) -> tuple[Config, Path]:
    database = tmp_path / "migration.db"
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    command.upgrade(config, revision)
    return config, database


def test_initial_migration_creates_operational_tables(tmp_path: Path) -> None:
    _, database = upgrade_database(tmp_path)

    tables = set(inspect(create_engine(f"sqlite:///{database}")).get_table_names())
    assert OPERATIONAL_TABLES <= tables


def test_operational_constraints_and_lookups_are_organization_scoped(
    tmp_path: Path,
) -> None:
    _, database = upgrade_database(tmp_path)
    inspector = inspect(create_engine(f"sqlite:///{database}"))

    raw_unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("raw_import_records")
    }
    assert ("organization_id", "import_batch_id", "row_number") in raw_unique_columns
    assert ("import_batch_id", "row_number") not in raw_unique_columns
    assert ("organization_id", "id") in raw_unique_columns

    session_unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("charging_sessions")
    }
    assert ("organization_id", "raw_record_id") in session_unique_columns
    assert ("raw_record_id",) not in session_unique_columns

    session_foreign_keys = {
        (
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
        )
        for foreign_key in inspector.get_foreign_keys("charging_sessions")
    }
    assert (
        ("organization_id", "raw_record_id"),
        "raw_import_records",
        ("organization_id", "id"),
    ) in session_foreign_keys

    expected_indexes = {
        "chargers": {("organization_id", "site_id")},
        "memberships": {("organization_id", "profile_id")},
        "raw_import_records": {("organization_id", "import_batch_id")},
        "charging_sessions": {
            ("organization_id", "site_id"),
            ("organization_id", "charger_id"),
            ("organization_id", "import_batch_id"),
        },
        "audit_events": {
            ("organization_id", "actor_profile_id"),
            ("organization_id", "entity_id"),
        },
    }
    for table_name, expected_column_sets in expected_indexes.items():
        actual_column_sets = {
            tuple(index["column_names"]) for index in inspector.get_indexes(table_name)
        }
        assert expected_column_sets <= actual_column_sets


def test_initial_migration_downgrades_to_empty_schema(tmp_path: Path) -> None:
    config, database = upgrade_database(tmp_path)

    command.downgrade(config, "base")

    tables = set(inspect(create_engine(f"sqlite:///{database}")).get_table_names())
    assert OPERATIONAL_TABLES.isdisjoint(tables)


def test_session_assignment_migration_creates_scoped_assignment_table(
    tmp_path: Path,
) -> None:
    _, database = upgrade_database(tmp_path, "20260830_0002")
    inspector = inspect(create_engine(f"sqlite:///{database}"))

    columns = {
        column["name"] for column in inspector.get_columns("session_assignments")
    }
    assert {
        "organization_id",
        "charging_session_id",
        "unit_id",
        "assigned_by",
        "justification",
    } <= columns

    unique_constraints = {
        constraint["name"]: tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("session_assignments")
    }
    assert unique_constraints[
        "uq_session_assignments_organization_id_charging_session_id"
    ] == ("organization_id", "charging_session_id")


def test_session_assignment_migration_downgrade_removes_only_assignment_table(
    tmp_path: Path,
) -> None:
    config, database = upgrade_database(tmp_path, "20260830_0002")
    engine = create_engine(f"sqlite:///{database}")
    before_downgrade = set(inspect(engine).get_table_names())

    command.downgrade(config, "20260829_0001")

    after_downgrade = set(inspect(engine).get_table_names())
    assert after_downgrade == before_downgrade - {"session_assignments"}


class CapturedAlembicUrl(Exception):
    def __init__(self, url: str) -> None:
        self.url = url


def test_alembic_normalizes_plain_postgresql_url_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = Config("apps/api/alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        "postgresql://chargeops@example.invalid/chargeops",
    )

    def capture_url(configuration: dict[str, str], **_: object) -> NoReturn:
        raise CapturedAlembicUrl(configuration["sqlalchemy.url"])

    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_engine_from_config",
        capture_url,
    )

    with pytest.raises(CapturedAlembicUrl) as captured:
        command.current(config)

    assert captured.value.url == (
        "postgresql+psycopg://chargeops@example.invalid/chargeops"
    )


def test_alembic_accepts_percent_encoded_password_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://chargeops:synthetic%21@example.invalid/chargeops",
    )
    config = Config("apps/api/alembic.ini")

    def capture_url(configuration: dict[str, str], **_: object) -> NoReturn:
        raise CapturedAlembicUrl(configuration["sqlalchemy.url"])

    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_engine_from_config",
        capture_url,
    )

    with pytest.raises(CapturedAlembicUrl) as captured:
        command.current(config)

    assert captured.value.url == (
        "postgresql+psycopg://chargeops:synthetic%21@example.invalid/chargeops"
    )


def test_postgresql_offline_upgrade_compiles_complete_scoped_schema() -> None:
    output = StringIO()
    config = Config("apps/api/alembic.ini", output_buffer=output)
    config.set_main_option(
        "sqlalchemy.url",
        "postgresql://chargeops@example.invalid/chargeops",
    )

    command.upgrade(config, "head", sql=True)

    sql = output.getvalue()
    assert "UNIQUE (organization_id, import_batch_id, row_number)" in sql
    assert "INSERT INTO alembic_version" in sql
    assert "20260829_0001" in sql
    assert sql.rstrip().endswith("COMMIT;")
