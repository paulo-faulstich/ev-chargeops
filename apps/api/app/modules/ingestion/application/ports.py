from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from app.modules.ingestion.domain.session import SessionCandidate, SourceKind


@dataclass(frozen=True, slots=True)
class SourceRecord:
    row_number: int
    raw: Mapping[str, str]


class ChargingSessionSource(Protocol):
    kind: SourceKind

    def read(self, content: bytes) -> list[SourceRecord]: ...

    def normalize(self, record: SourceRecord) -> SessionCandidate: ...
