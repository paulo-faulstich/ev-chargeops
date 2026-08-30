from dataclasses import replace
from hashlib import sha256

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
    ) -> None:
        self.source = source
        self.repository = repository
        self.file_store = file_store

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
        storage_path = await self.file_store.put(
            scope.organization_id,
            checksum,
            filename,
            content,
        )
        try:
            return await self.repository.save_import(scope, reviewed, storage_path)
        except Exception:
            await self.file_store.delete(storage_path)
            raise
