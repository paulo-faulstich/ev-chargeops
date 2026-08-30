from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.ingestion.application.import_ports import (
    ImportRepository,
    OriginalFileStore,
)
from app.modules.ingestion.application.preview_import import (
    ImportPreview,
    PreviewImport,
)
from app.modules.ingestion.domain.import_batch import (
    ImportBatchResult,
    PersistedRawRecord,
)
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource

FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"
CSV_HEADER = (
    "Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN"
)


def scope() -> OrganizationScope:
    return OrganizationScope(
        auth_user_id=UUID("50000000-0000-0000-0000-000000000001"),
        profile_id=UUID("60000000-0000-0000-0000-000000000001"),
        organization_id=UUID("10000000-0000-0000-0000-000000000001"),
        role=OrganizationRole.MANAGER,
        unit_id=None,
    )


def source() -> SemsCsvSource:
    return SemsCsvSource(ZoneInfo("America/Sao_Paulo"))


def fixture_content() -> bytes:
    return FIXTURE.read_bytes()


def mixed_content() -> bytes:
    return (
        f"""{CSV_HEADER}
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1,97500NAP25BL0008
29/08/2026 19:10:00,29/08/2026 20:10:00,0.00,1,CARD-2,97500NAP25BL0008
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1,97500NAP25BL0008
"""
    ).encode()


def preview_for_fixture() -> ImportPreview:
    return PreviewImport(source()).execute("sems_sessions.csv", fixture_content())


def existing_batch() -> ImportBatchResult:
    return ImportBatchResult(
        id=UUID("70000000-0000-0000-0000-000000000001"),
        filename="sems.csv",
        checksum="a" * 64,
        source="sems_export",
        status="completed",
        created=True,
        total_count=2,
        valid_count=2,
        invalid_count=0,
        duplicate_count=0,
        created_at=datetime(2026, 8, 29, tzinfo=UTC),
    )


@dataclass(frozen=True, slots=True)
class SavedSession:
    raw_record_id: UUID


class FakeImportRepository(ImportRepository):
    def __init__(
        self,
        *,
        existing_keys: set[str] | None = None,
        existing_batch: ImportBatchResult | None = None,
        save_error: Exception | None = None,
    ) -> None:
        self._existing_keys = existing_keys or set()
        self._existing_batch = existing_batch
        self.save_error = save_error
        self.existing_key_calls: list[tuple[UUID, set[str]]] = []
        self.find_batch_calls: list[tuple[UUID, str]] = []
        self.saved_raw_records: list[PersistedRawRecord] = []
        self.saved_sessions: list[SavedSession] = []
        self.save_calls = 0
        self.saved_storage_paths: list[str] = []
        self.list_batch_calls: list[UUID] = []
        self.get_batch_calls: list[tuple[UUID, UUID]] = []

    async def existing_keys(
        self,
        organization_id: UUID,
        keys: set[str],
    ) -> set[str]:
        self.existing_key_calls.append((organization_id, set(keys)))
        return self._existing_keys & keys

    async def find_batch_by_checksum(
        self,
        organization_id: UUID,
        checksum: str,
    ) -> ImportBatchResult | None:
        self.find_batch_calls.append((organization_id, checksum))
        return self._existing_batch

    async def save_import(
        self,
        scope: OrganizationScope,
        preview: ImportPreview,
        storage_path: str,
    ) -> ImportBatchResult:
        self.save_calls += 1
        self.saved_storage_paths.append(storage_path)
        if self.save_error is not None:
            raise self.save_error

        for index, record in enumerate(preview.records, start=1):
            raw_record = PersistedRawRecord(
                id=UUID(int=index),
                row_number=record.row_number,
                raw=dict(record.raw),
                classification=record.classification,
                error_field=record.error_field,
                error_code=record.error_code,
                error_message=record.error_message,
            )
            self.saved_raw_records.append(raw_record)
            if record.classification == "valid":
                self.saved_sessions.append(SavedSession(raw_record_id=raw_record.id))

        return ImportBatchResult(
            id=UUID("70000000-0000-0000-0000-000000000002"),
            filename=preview.filename,
            checksum=preview.checksum,
            source=preview.source,
            status="completed",
            created=True,
            total_count=preview.total_count,
            valid_count=preview.valid_count,
            invalid_count=preview.invalid_count,
            duplicate_count=preview.duplicate_count,
            created_at=datetime(2026, 8, 29, tzinfo=UTC),
        )

    async def list_batches(
        self,
        organization_id: UUID,
    ) -> tuple[ImportBatchResult, ...]:
        self.list_batch_calls.append(organization_id)
        if self._existing_batch is None:
            return ()
        return (self._existing_batch,)

    async def get_batch(
        self,
        organization_id: UUID,
        batch_id: UUID,
    ) -> ImportBatchResult | None:
        self.get_batch_calls.append((organization_id, batch_id))
        if self._existing_batch is None or self._existing_batch.id != batch_id:
            return None
        return self._existing_batch


class FakeOriginalFileStore(OriginalFileStore):
    def __init__(self, path: str = "imports/org/checksum.csv") -> None:
        self.path = path
        self.put_calls: list[tuple[UUID, str, str, bytes]] = []
        self.deleted_paths: list[str] = []

    async def put(
        self,
        organization_id: UUID,
        checksum: str,
        filename: str,
        content: bytes,
    ) -> str:
        self.put_calls.append((organization_id, checksum, filename, content))
        return self.path

    async def delete(self, storage_path: str) -> None:
        self.deleted_paths.append(storage_path)
