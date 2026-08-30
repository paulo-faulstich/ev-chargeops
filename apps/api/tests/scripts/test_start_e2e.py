from pathlib import Path

import pytest

from scripts.start_e2e import validate_database_path


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

