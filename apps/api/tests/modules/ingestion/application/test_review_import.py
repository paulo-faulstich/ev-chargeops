import pytest

from app.modules.ingestion.application.review_import import ReviewImport
from tests.modules.ingestion.application.fakes import (
    FakeImportRepository,
    preview_for_fixture,
    scope,
)

pytestmark = pytest.mark.asyncio


async def test_review_marks_existing_database_session_duplicate() -> None:
    preview = preview_for_fixture()
    session = preview.records[0].session
    assert session is not None
    repository = FakeImportRepository(
        existing_keys={session.deduplication_key},
    )

    reviewed = await ReviewImport(repository).execute(scope(), preview)

    assert reviewed.records[0].classification == "duplicate"
    assert reviewed.duplicate_count == 1
    assert reviewed.valid_count == 1


async def test_review_queries_candidate_keys_once_for_the_tenant() -> None:
    preview = preview_for_fixture()
    repository = FakeImportRepository()

    reviewed = await ReviewImport(repository).execute(scope(), preview)

    expected_keys = {
        record.session.deduplication_key
        for record in preview.records
        if record.session is not None
    }
    assert reviewed == preview
    assert repository.existing_key_calls == [
        (scope().organization_id, expected_keys),
    ]
