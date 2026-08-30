from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from app.modules.ingestion.domain.session import SessionCandidate, SourceKind


@dataclass(frozen=True, slots=True)
class SourceRecordIssue:
    field: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class SourceRecord:
    row_number: int
    raw: Mapping[str, str | None]
    issue: SourceRecordIssue | None = None


class ChargingSessionSource(Protocol):
    kind: SourceKind

    def read(self, content: bytes) -> list[SourceRecord]: ...

    def normalize(self, record: SourceRecord) -> SessionCandidate: ...
