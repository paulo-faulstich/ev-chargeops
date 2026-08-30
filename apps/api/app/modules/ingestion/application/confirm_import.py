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
        stored_file = await self.file_store.put(
            scope.organization_id,
            checksum,
            filename,
            content,
        )
        try:
            return await self.repository.save_import(
                scope,
                reviewed,
                stored_file.path,
            )
        except Exception as persistence_error:
            winner_check_failed = False
            try:
                winner = await self.repository.find_batch_by_checksum(
                    scope.organization_id,
                    checksum,
                )
            except Exception:  # noqa: BLE001
                persistence_error.add_note(
                    "Checksum winner verification failed after import persistence failure."
                )
                winner_check_failed = True
                winner = None

            if winner_check_failed:
                raise

            if winner is not None:
                return replace(winner, created=False)

            if stored_file.created:
                try:
                    await self.file_store.delete(stored_file.path)
                except Exception:  # noqa: BLE001
                    persistence_error.add_note(
                        "Original file cleanup failed after import persistence failure."
                    )
            raise
