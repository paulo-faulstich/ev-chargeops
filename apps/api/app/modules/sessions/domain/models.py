from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from .errors import InvalidJustification


@dataclass(frozen=True, slots=True)
class SessionView:
    id: UUID
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    charger_serial: str
    source: str
    provenance: str
    identity_confidence: str
    status: str
    unit_id: UUID | None
    unit_code: str | None
    unit_name: str | None
    resident_name: str | None


@dataclass(frozen=True, slots=True)
class AssignmentUnitView:
    id: UUID
    code: str
    display_name: str
    resident_name: str | None


@dataclass(frozen=True, slots=True)
class SessionAssignment:
    id: UUID
    session_id: UUID
    unit_id: UUID
    assigned_by: UUID
    justification: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AssignmentResult:
    assignment: SessionAssignment
    session: SessionView
    created: bool


def normalize_justification(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise InvalidJustification(field="justification")
    return normalized
