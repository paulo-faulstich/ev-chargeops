from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from uuid import UUID, uuid4

from app.modules.identity.domain.auth import OrganizationScope
from app.modules.ingestion.application.import_ports import (
    ImportRepository,
    OriginalFileStore,
)
from app.modules.ingestion.application.ports import ChargingSessionSource
from app.modules.ingestion.application.preview_import import PreviewImport
from app.modules.ingestion.application.review_import import ReviewImport
from app.modules.ingestion.domain.import_batch import ImportBatchResult


class ConfirmImport:
    def __init__(
        self,
        source: ChargingSessionSource,
        repository: ImportRepository,
        file_store: OriginalFileStore,
        *,
        attempt_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self.source = source
        self.repository = repository
        self.file_store = file_store
        self.attempt_id_factory = attempt_id_factory

    async def execute(
        self,
        scope: OrganizationScope,
        filename: str,
        content: bytes,
    ) -> ImportBatchResult:
        checksum = sha256(content).hexdigest()
        existing = await self.repository.find_batch_by_checksum(
            scope.organization_id,
            checksum,
        )
        if existing is not None:
            return replace(existing, created=False)

        preview = PreviewImport(self.source).execute(filename, content)
        reviewed = await ReviewImport(self.repository).execute(scope, preview)
        stored_file = await self.file_store.put(
            scope.organization_id,
            checksum,
            self.attempt_id_factory(),
            content,
        )
        try:
            result = await self.repository.save_import(
                scope,
                reviewed,
                stored_file.path,
            )
        except Exception as persistence_error:
            if stored_file.created:
                try:
                    await self.file_store.delete(stored_file.path)
                except Exception:  # noqa: BLE001
                    persistence_error.add_note(
                        "Original file cleanup failed after import persistence failure."
                    )
            raise

        if not result.created and stored_file.created:
            await self.file_store.delete(stored_file.path)
        return result
