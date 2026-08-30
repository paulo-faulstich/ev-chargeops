import pytest

from app.modules.ingestion.application.confirm_import import ConfirmImport
from tests.modules.ingestion.application.fakes import (
    FakeImportRepository,
    FakeOriginalFileStore,
    existing_batch,
    fixture_content,
    mixed_content,
    scope,
    source,
)

pytestmark = pytest.mark.asyncio


async def test_confirm_persists_batch_raw_records_and_only_valid_sessions() -> None:
    repository = FakeImportRepository()
    store = FakeOriginalFileStore(path="imports/org/checksum.csv")

    result = await ConfirmImport(source(), repository, store).execute(
        scope(), "sems.csv", mixed_content()
    )

    assert result.created is True
    assert result.total_count == 3
    assert len(repository.saved_raw_records) == 3
    assert len(repository.saved_sessions) == 1
    assert repository.saved_sessions[0].raw_record_id is not None


async def test_confirm_replays_existing_checksum_without_new_writes() -> None:
    repository = FakeImportRepository(existing_batch=existing_batch())
    store = FakeOriginalFileStore()

    result = await ConfirmImport(source(), repository, store).execute(
        scope(), "sems.csv", fixture_content()
    )

    assert result.id == existing_batch().id
    assert result.created is False
    assert repository.save_calls == 0
    assert store.put_calls == []


async def test_confirm_deletes_original_when_database_persistence_fails() -> None:
    repository = FakeImportRepository(save_error=RuntimeError("database unavailable"))
    store = FakeOriginalFileStore(path="imports/org/checksum.csv")

    with pytest.raises(RuntimeError, match="database unavailable"):
        await ConfirmImport(source(), repository, store).execute(
            scope(), "sems.csv", fixture_content()
        )

    assert store.deleted_paths == ["imports/org/checksum.csv"]
