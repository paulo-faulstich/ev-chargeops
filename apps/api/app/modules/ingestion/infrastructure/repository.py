from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.infrastructure.models import AuditEventModel
from app.modules.identity.domain.auth import OrganizationScope
from app.modules.ingestion.application.preview_import import ImportPreview
from app.modules.ingestion.application.review_import import ReviewImport
from app.modules.ingestion.domain.import_batch import ImportBatchResult
from app.modules.ingestion.infrastructure.models import (
    ChargingSessionModel,
    ImportBatchModel,
    RawImportRecordModel,
)
from app.modules.organizations.infrastructure.models import ChargerModel


class SqlAlchemyImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def existing_keys(
        self,
        organization_id: UUID,
        keys: set[str],
    ) -> set[str]:
        if not keys:
            return set()
        return set(
            (
                await self.session.scalars(
                    select(ChargingSessionModel.deduplication_key).where(
                        ChargingSessionModel.organization_id == organization_id,
                        ChargingSessionModel.deduplication_key.in_(keys),
                    )
                )
            ).all()
        )

    async def find_batch_by_checksum(
        self,
        organization_id: UUID,
        checksum: str,
    ) -> ImportBatchResult | None:
        batch = await self.session.scalar(
            select(ImportBatchModel).where(
                ImportBatchModel.organization_id == organization_id,
                ImportBatchModel.checksum == checksum,
            )
        )
        if batch is None:
            return None
        return self._result(batch)

    async def save_import(
        self,
        scope: OrganizationScope,
        preview: ImportPreview,
        storage_path: str,
    ) -> ImportBatchResult:
        reviewed = preview
        while True:
            try:
                return await self._save_once(scope, reviewed, storage_path)
            except IntegrityError:
                await self.session.rollback()
                replay = await self.find_batch_by_checksum(
                    scope.organization_id,
                    preview.checksum,
                )
                if replay is not None:
                    return replace(replay, created=False)

                rereviewed = await ReviewImport(self).execute(scope, reviewed)
                if rereviewed == reviewed:
                    raise
                reviewed = rereviewed

    async def list_batches(
        self,
        organization_id: UUID,
    ) -> tuple[ImportBatchResult, ...]:
        batches = (
            await self.session.scalars(
                select(ImportBatchModel)
                .where(ImportBatchModel.organization_id == organization_id)
                .order_by(
                    ImportBatchModel.created_at.desc(),
                    ImportBatchModel.id.desc(),
                )
            )
        ).all()
        return tuple(self._result(batch) for batch in batches)

    async def get_batch(
        self,
        organization_id: UUID,
        batch_id: UUID,
    ) -> ImportBatchResult | None:
        batch = await self.session.scalar(
            select(ImportBatchModel).where(
                ImportBatchModel.organization_id == organization_id,
                ImportBatchModel.id == batch_id,
            )
        )
        if batch is None:
            return None
        return self._result(batch)

    async def _save_once(
        self,
        scope: OrganizationScope,
        preview: ImportPreview,
        storage_path: str,
    ) -> ImportBatchResult:
        chargers = await self._chargers_for_preview(scope.organization_id, preview)
        batch = ImportBatchModel(
            organization_id=scope.organization_id,
            source=preview.source,
            checksum=preview.checksum,
            filename=preview.filename,
            storage_path=storage_path,
            status="completed",
            total_count=preview.total_count,
            valid_count=preview.valid_count,
            invalid_count=preview.invalid_count,
            duplicate_count=preview.duplicate_count,
            created_by=scope.profile_id,
        )
        self.session.add(batch)
        await self.session.flush()

        for record in preview.records:
            raw_record = RawImportRecordModel(
                organization_id=scope.organization_id,
                import_batch_id=batch.id,
                row_number=record.row_number,
                raw_payload=dict(record.raw),
                classification=record.classification,
                error_field=record.error_field,
                error_code=record.error_code,
                error_message=record.error_message,
            )
            self.session.add(raw_record)
            await self.session.flush()

            if record.classification != "valid" or record.session is None:
                continue
            candidate = record.session
            charger = chargers[candidate.charger_serial]
            self.session.add(
                ChargingSessionModel(
                    organization_id=scope.organization_id,
                    site_id=charger.site_id,
                    charger_id=charger.id,
                    import_batch_id=batch.id,
                    raw_record_id=raw_record.id,
                    source=candidate.source.value,
                    external_id=candidate.external_id,
                    deduplication_key=candidate.deduplication_key,
                    started_at=candidate.started_at,
                    ended_at=candidate.ended_at,
                    energy_kwh=candidate.energy_kwh,
                    charge_port=candidate.charge_port,
                    card_id_raw=candidate.card_id_raw,
                    identity_confidence=candidate.identity_confidence.value,
                    provenance=candidate.provenance.value,
                    status="pending_review",
                )
            )

        self.session.add(
            AuditEventModel(
                organization_id=scope.organization_id,
                actor_profile_id=scope.profile_id,
                occurred_at=datetime.now(UTC),
                event_type="import_completed",
                entity_type="import_batch",
                entity_id=batch.id,
                metadata_json={
                    "total_count": preview.total_count,
                    "valid_count": preview.valid_count,
                    "invalid_count": preview.invalid_count,
                    "duplicate_count": preview.duplicate_count,
                },
            )
        )
        await self.session.commit()
        return self._result(batch)

    async def _chargers_for_preview(
        self,
        organization_id: UUID,
        preview: ImportPreview,
    ) -> dict[str, ChargerModel]:
        serials = {
            record.session.charger_serial
            for record in preview.records
            if record.classification == "valid" and record.session is not None
        }
        if not serials:
            return {}
        chargers = (
            await self.session.scalars(
                select(ChargerModel).where(
                    ChargerModel.organization_id == organization_id,
                    ChargerModel.serial.in_(serials),
                )
            )
        ).all()
        by_serial = {charger.serial: charger for charger in chargers}
        missing = sorted(serials - by_serial.keys())
        if missing:
            raise LookupError(
                f"No charger in organization for serial: {', '.join(missing)}"
            )
        return by_serial

    @staticmethod
    def _result(
        batch: ImportBatchModel,
        *,
        created: bool = True,
    ) -> ImportBatchResult:
        created_at = batch.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        else:
            created_at = created_at.astimezone(UTC)
        return ImportBatchResult(
            id=batch.id,
            filename=batch.filename,
            checksum=batch.checksum,
            source=batch.source,
            status="completed",
            created=created,
            total_count=batch.total_count,
            valid_count=batch.valid_count,
            invalid_count=batch.invalid_count,
            duplicate_count=batch.duplicate_count,
            created_at=created_at,
        )
