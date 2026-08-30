from uuid import UUID

from app.modules.identity.domain.auth import OrganizationScope
from app.modules.ingestion.application.import_ports import ImportRepository
from app.modules.ingestion.domain.import_batch import ImportBatchResult


class ListImports:
    def __init__(self, repository: ImportRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
    ) -> tuple[ImportBatchResult, ...]:
        return await self.repository.list_batches(scope.organization_id)


class GetImport:
    def __init__(self, repository: ImportRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        batch_id: UUID,
    ) -> ImportBatchResult | None:
        return await self.repository.get_batch(scope.organization_id, batch_id)
