from dataclasses import replace
from uuid import UUID

import pytest

from app.modules.ingestion.application.confirm_import import ConfirmImport
from app.modules.ingestion.application.import_ports import OriginalFileStorageError
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

ATTEMPT_ID = UUID("80000000-0000-0000-0000-000000000001")


def use_case(
    repository: FakeImportRepository,
    store: FakeOriginalFileStore,
) -> ConfirmImport:
    return ConfirmImport(
        source(),
        repository,
        store,
        attempt_id_factory=lambda: ATTEMPT_ID,
    )


async def test_confirm_persists_batch_raw_records_and_only_valid_sessions() -> None:
    repository = FakeImportRepository()
    store = FakeOriginalFileStore(path="imports/org/source.csv")

    result = await use_case(repository, store).execute(
        scope(), "sems.csv", mixed_content()
    )

    assert result.created is True
    assert result.total_count == 3
    assert len(repository.saved_raw_records) == 3
    assert len(repository.saved_sessions) == 1
    assert repository.saved_sessions[0].raw_record_id is not None
    assert repository.saved_storage_paths == ["imports/org/source.csv"]
    assert store.put_calls == [
        (
            scope().organization_id,
            result.checksum,
            ATTEMPT_ID,
            mixed_content(),
        )
    ]


async def test_confirm_replays_existing_checksum_without_new_writes() -> None:
    repository = FakeImportRepository(existing_batch=existing_batch())
    store = FakeOriginalFileStore()

    def unexpected_attempt_id() -> UUID:
        raise AssertionError("pre-storage replay must not allocate an attempt")

    result = await ConfirmImport(
        source(),
        repository,
        store,
        attempt_id_factory=unexpected_attempt_id,
    ).execute(scope(), "sems.csv", fixture_content())

    assert result.id == existing_batch().id
    assert result.created is False
    assert repository.save_calls == 0
    assert store.put_calls == []


async def test_confirm_deletes_original_when_database_persistence_fails() -> None:
    primary_error = RuntimeError("database unavailable")
    repository = FakeImportRepository(save_error=primary_error)
    store = FakeOriginalFileStore(path="imports/org/source.csv", created=True)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await use_case(repository, store).execute(
            scope(), "sems.csv", fixture_content()
        )

    assert store.deleted_paths == ["imports/org/source.csv"]
    assert len(repository.find_batch_calls) == 1


async def test_confirm_never_deletes_reused_object_after_database_failure() -> None:
    primary_error = RuntimeError("database unavailable")
    repository = FakeImportRepository(save_error=primary_error)
    store = FakeOriginalFileStore(created=False)

    with pytest.raises(RuntimeError) as error:
        await use_case(repository, store).execute(
            scope(), "sems.csv", fixture_content()
        )

    assert error.value is primary_error
    assert store.deleted_paths == []
    assert len(repository.find_batch_calls) == 1


async def test_confirm_deletes_its_attempt_after_repository_returns_replay() -> None:
    winner = replace(existing_batch(), created=False)
    repository = FakeImportRepository(save_result=winner)
    store = FakeOriginalFileStore(created=True)

    result = await use_case(repository, store).execute(
        scope(), "renamed.csv", fixture_content()
    )

    assert result is winner
    assert store.deleted_paths == ["imports/org/source.csv"]


async def test_confirm_never_deletes_reused_attempt_after_repository_replay() -> None:
    winner = replace(existing_batch(), created=False)
    repository = FakeImportRepository(save_result=winner)
    store = FakeOriginalFileStore(created=False)

    result = await use_case(repository, store).execute(
        scope(), "renamed.csv", fixture_content()
    )

    assert result is winner
    assert store.deleted_paths == []


async def test_cleanup_failure_preserves_primary_database_exception() -> None:
    primary_error = RuntimeError("database unavailable")
    repository = FakeImportRepository(save_error=primary_error)
    store = FakeOriginalFileStore(
        created=True,
        delete_error=OriginalFileStorageError("sensitive cleanup detail"),
    )

    with pytest.raises(RuntimeError) as error:
        await use_case(repository, store).execute(
            scope(), "sems.csv", fixture_content()
        )

    assert error.value is primary_error
    assert error.value.__notes__ == [
        "Original file cleanup failed after import persistence failure."
    ]
