from pathlib import Path

import pytest

from scripts.start_e2e import configure_e2e_environment, validate_database_path


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
    monkeypatch.setenv("ORIGINAL_FILE_STORE", "supabase")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "synthetic-service-role-key")

    settings = configure_e2e_environment(
        f"sqlite+aiosqlite:///{allowed_root / 'ev-chargeops-e2e.sqlite3'}",
        allowed_root,
    )

    assert settings.original_file_store == "local"
    assert settings.original_files_root == allowed_root / "original-files"
    assert not settings.supabase_service_role_key
