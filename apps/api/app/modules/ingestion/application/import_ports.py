from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.auth import OrganizationScope
from app.modules.ingestion.application.preview_import import ImportPreview
from app.modules.ingestion.domain.import_batch import (
    ImportBatchResult,
    PersistedRawRecord,
)


@dataclass(frozen=True, slots=True)
class StoredOriginalFile:
    path: str
    created: bool


class ImportRepository(Protocol):
    async def existing_keys(
        self,
        organization_id: UUID,
        keys: set[str],
    ) -> set[str]: ...

    async def find_batch_by_checksum(
        self,
        organization_id: UUID,
        checksum: str,
    ) -> ImportBatchResult | None: ...

    async def save_import(
        self,
        scope: OrganizationScope,
        preview: ImportPreview,
        storage_path: str,
    ) -> ImportBatchResult: ...

    async def list_batches(
        self,
        organization_id: UUID,
    ) -> tuple[ImportBatchResult, ...]: ...

    async def get_batch(
        self,
        organization_id: UUID,
        batch_id: UUID,
    ) -> ImportBatchResult | None: ...

    async def get_batch_records(
        self,
        organization_id: UUID,
        batch_id: UUID,
    ) -> tuple[PersistedRawRecord, ...]: ...


class OriginalFileStore(Protocol):
    async def put(
        self,
        organization_id: UUID,
        checksum: str,
        attempt_id: UUID,
        content: bytes,
    ) -> StoredOriginalFile: ...

    async def delete(self, storage_path: str) -> None: ...


class OriginalFileStorageError(RuntimeError):
    """Original import file storage failed with a stable application error."""


class SessionAttributor(Protocol):
    """Attributes freshly imported sessions that carry a registered card.

    Ingestion owns the canonical session; it does not own attribution. This
    port lets the import finish the job a registered card already answers,
    without ingestion knowing how units or assignments work.
    """

    async def attribute_by_registered_card(
        self,
        organization_id: UUID,
        actor_profile_id: UUID,
        import_batch_id: UUID,
    ) -> int: ...
