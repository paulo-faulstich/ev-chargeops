from dataclasses import replace

from app.modules.identity.domain.auth import OrganizationScope
from app.modules.ingestion.application.import_ports import ImportRepository
from app.modules.ingestion.application.preview_import import ImportPreview


class ReviewImport:
    def __init__(self, repository: ImportRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        scope: OrganizationScope,
        preview: ImportPreview,
    ) -> ImportPreview:
        candidate_keys = {
            record.session.deduplication_key
            for record in preview.records
            if record.session is not None
        }
        existing_keys = await self.repository.existing_keys(
            scope.organization_id,
            candidate_keys,
        )
        records = tuple(
            replace(record, classification="duplicate")
            if (
                record.classification == "valid"
                and record.session is not None
                and record.session.deduplication_key in existing_keys
            )
            else record
            for record in preview.records
        )
        return replace(preview, records=records)
