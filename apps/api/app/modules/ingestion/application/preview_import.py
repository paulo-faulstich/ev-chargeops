from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from app.modules.ingestion.application.ports import ChargingSessionSource
from app.modules.ingestion.domain.errors import InvalidSession
from app.modules.ingestion.domain.session import SessionCandidate


@dataclass(frozen=True, slots=True)
class PreviewRecord:
    row_number: int
    classification: Literal["valid", "invalid", "duplicate"]
    raw: Mapping[str, str | None]
    session: SessionCandidate | None = None
    error_field: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ImportPreview:
    filename: str
    checksum: str
    source: str
    records: tuple[PreviewRecord, ...]

    @property
    def total_count(self) -> int:
        return len(self.records)

    @property
    def valid_count(self) -> int:
        return sum(record.classification == "valid" for record in self.records)

    @property
    def invalid_count(self) -> int:
        return sum(record.classification == "invalid" for record in self.records)

    @property
    def duplicate_count(self) -> int:
        return sum(record.classification == "duplicate" for record in self.records)


class PreviewImport:
    def __init__(self, source: ChargingSessionSource) -> None:
        self.source = source

    def execute(self, filename: str, content: bytes) -> ImportPreview:
        if not filename.lower().endswith(".csv"):
            raise InvalidSession(
                "file", "UNSUPPORTED_FILE", "Só arquivos CSV são aceitos."
            )

        records: list[PreviewRecord] = []
        seen: set[str] = set()
        for source_record in self.source.read(content):
            try:
                session = self.source.normalize(source_record)
                classification: Literal["valid", "duplicate"] = (
                    "duplicate" if session.deduplication_key in seen else "valid"
                )
                seen.add(session.deduplication_key)
                records.append(
                    PreviewRecord(
                        row_number=source_record.row_number,
                        classification=classification,
                        raw=source_record.raw,
                        session=session,
                    )
                )
            except InvalidSession as error:
                records.append(
                    PreviewRecord(
                        row_number=source_record.row_number,
                        classification="invalid",
                        raw=source_record.raw,
                        error_field=error.field,
                        error_code=error.code,
                        error_message=error.message,
                    )
                )

        return ImportPreview(
            filename=filename,
            checksum=sha256(content).hexdigest(),
            source=self.source.kind.value,
            records=tuple(records),
        )
