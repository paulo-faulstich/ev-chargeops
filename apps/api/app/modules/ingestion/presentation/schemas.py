from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.ingestion.application.preview_import import ImportPreview
from app.modules.ingestion.domain.import_batch import (
    ImportBatchDetail,
    ImportBatchResult,
)


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.title() for part in rest)


class ApiSchema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SessionPreviewResponse(ApiSchema):
    charger_serial: str
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    charge_port: int | None
    card_id_raw: str | None
    identity_confidence: str
    provenance: str
    deduplication_key: str


class PreviewRecordResponse(ApiSchema):
    row_number: int
    classification: str
    raw: dict[str, str | None]
    session: SessionPreviewResponse | None = None
    error_field: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class ImportPreviewResponse(ApiSchema):
    filename: str
    checksum: str
    source: str
    total_count: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    records: list[PreviewRecordResponse]

    @classmethod
    def from_result(cls, result: ImportPreview) -> "ImportPreviewResponse":
        return cls(
            filename=result.filename,
            checksum=result.checksum,
            source=result.source,
            total_count=result.total_count,
            valid_count=result.valid_count,
            invalid_count=result.invalid_count,
            duplicate_count=result.duplicate_count,
            records=[
                PreviewRecordResponse(
                    row_number=record.row_number,
                    classification=record.classification,
                    raw=dict(record.raw),
                    session=(
                        SessionPreviewResponse.model_validate(
                            record.session, from_attributes=True
                        )
                        if record.session
                        else None
                    ),
                    error_field=record.error_field,
                    error_code=record.error_code,
                    error_message=record.error_message,
                )
                for record in result.records
            ],
        )


class ImportBatchResponse(ApiSchema):
    id: UUID
    filename: str
    checksum: str
    source: str
    status: str
    created: bool
    total_count: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    created_at: datetime

    @classmethod
    def from_result(cls, result: ImportBatchResult) -> "ImportBatchResponse":
        return cls.model_validate(result, from_attributes=True)


class ImportBatchListResponse(ApiSchema):
    items: list[ImportBatchResponse]


class PersistedRawRecordResponse(ApiSchema):
    id: UUID
    row_number: int
    raw: dict[str, str | None]
    classification: str
    error_field: str | None
    error_code: str | None
    error_message: str | None
    session_id: UUID | None


class ImportBatchDetailResponse(ImportBatchResponse):
    records: list[PersistedRawRecordResponse]

    @classmethod
    def from_detail(cls, detail: ImportBatchDetail) -> "ImportBatchDetailResponse":
        return cls(
            **ImportBatchResponse.from_result(detail.batch).model_dump(),
            records=[
                PersistedRawRecordResponse.model_validate(
                    record,
                    from_attributes=True,
                )
                for record in detail.records
            ],
        )


class ErrorDetail(ApiSchema):
    field: str


class ErrorBody(ApiSchema):
    code: str
    message: str
    details: list[ErrorDetail]


class ErrorResponse(ApiSchema):
    error: ErrorBody


class HttpErrorResponse(ApiSchema):
    detail: str
