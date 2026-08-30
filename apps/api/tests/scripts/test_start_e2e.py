import os
from pathlib import Path

import pytest

from app.shared.config import Settings
from scripts.start_e2e import (
    build_e2e_environment,
    configure_e2e_environment,
    validate_database_path,
)


def test_accepts_sqlite_database_inside_playwright_results(tmp_path: Path) -> None:
    allowed_root = tmp_path / "apps" / "web" / "test-results"
    database_path = allowed_root / "ev-chargeops-e2e.sqlite3"

    assert validate_database_path(database_path, allowed_root) == database_path.resolve()


@pytest.mark.parametrize(
    "database_path",
    [
        Path("apps/api/ev-chargeops-e2e.sqlite3"),
        Path("apps/web/test-results/ev-chargeops-e2e.db"),
        Path("apps/web/test-results.sqlite3"),
    ],
)
def test_rejects_database_outside_playwright_results_or_wrong_suffix(
    tmp_path: Path,
    database_path: Path,
) -> None:
    allowed_root = (tmp_path / "apps" / "web" / "test-results").resolve()

    with pytest.raises(
        RuntimeError,
        match="E2E database must be a .sqlite3 file under apps/web/test-results",
    ):
        validate_database_path(tmp_path / database_path, allowed_root)


def test_forces_local_credential_free_file_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allowed_root = (tmp_path / "apps" / "web" / "test-results").resolve()
    environment_before = dict(os.environ)
    database_url = (
        f"sqlite+aiosqlite:///{allowed_root / 'ev-chargeops-e2e.sqlite3'}"
    )

    with monkeypatch.context() as isolated_environment:
        for key in build_e2e_environment(database_url, allowed_root):
            isolated_environment.setenv(key, os.environ.get(key, ""))
        isolated_environment.setenv("ORIGINAL_FILE_STORE", "supabase")
        isolated_environment.setenv(
            "SUPABASE_SERVICE_ROLE_KEY",
            "synthetic-service-role-key",
        )

        settings = configure_e2e_environment(
            database_url,
            allowed_root,
        )

        assert settings.original_file_store == "local"
        assert settings.original_files_root == allowed_root / "original-files"
        assert not settings.supabase_service_role_key

    assert dict(os.environ) == environment_before
    local_settings = Settings(
        app_env="local",
        auth_mode="fixture",
        supabase_url="https://lgjohsxipfctgooiuqnv.supabase.co",
        fixture_auth_token="fixture-manager-token",
    )
    assert local_settings.database_url == "sqlite+aiosqlite:///./ev_chargeops_local.db"
