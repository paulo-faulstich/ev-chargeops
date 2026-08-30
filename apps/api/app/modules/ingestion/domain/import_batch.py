from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PersistedRawRecord:
    id: UUID
    row_number: int
    raw: dict[str, str | None]
    classification: Literal["valid", "invalid", "duplicate"]
    error_field: str | None
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class ImportBatchResult:
    id: UUID
    filename: str
    checksum: str
    source: str
    status: Literal["completed"]
    created: bool
    total_count: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    created_at: datetime
