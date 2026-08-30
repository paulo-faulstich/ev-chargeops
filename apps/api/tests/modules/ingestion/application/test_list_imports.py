import pytest

from app.modules.ingestion.application.list_imports import GetImport, ListImports
from tests.modules.ingestion.application.fakes import (
    FakeImportRepository,
    existing_batch,
    scope,
)

pytestmark = pytest.mark.asyncio


async def test_list_imports_uses_authorized_organization_scope() -> None:
    repository = FakeImportRepository(existing_batch=existing_batch())

    batches = await ListImports(repository).execute(scope())

    assert batches == (existing_batch(),)
    assert repository.list_batch_calls == [scope().organization_id]


async def test_get_import_uses_authorized_organization_scope() -> None:
    repository = FakeImportRepository(existing_batch=existing_batch())

    batch = await GetImport(repository).execute(scope(), existing_batch().id)

    assert batch == existing_batch()
    assert repository.get_batch_calls == [
        (scope().organization_id, existing_batch().id),
    ]
