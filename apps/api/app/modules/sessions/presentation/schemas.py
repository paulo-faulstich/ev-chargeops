from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.modules.ingestion.presentation.schemas import ApiSchema
from app.modules.sessions.domain.models import (
    AssignmentResult,
    AssignmentUnitView,
    SessionAssignment,
    SessionView,
)


class SessionResponse(ApiSchema):
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

    @classmethod
    def from_view(cls, view: SessionView) -> "SessionResponse":
        return cls.model_validate(view, from_attributes=True)


class SessionListResponse(ApiSchema):
    items: list[SessionResponse]


class AssignmentUnitResponse(ApiSchema):
    id: UUID
    code: str
    display_name: str
    resident_name: str | None

    @classmethod
    def from_view(cls, view: AssignmentUnitView) -> "AssignmentUnitResponse":
        return cls.model_validate(view, from_attributes=True)


class AssignmentUnitListResponse(ApiSchema):
    items: list[AssignmentUnitResponse]


class SessionAssignmentRequest(ApiSchema):
    unit_id: UUID
    justification: str


class SessionAssignmentDetailResponse(ApiSchema):
    id: UUID
    session_id: UUID
    unit_id: UUID
    assigned_by: UUID
    justification: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_assignment(
        cls,
        assignment: SessionAssignment,
    ) -> "SessionAssignmentDetailResponse":
        return cls.model_validate(assignment, from_attributes=True)


class SessionAssignmentResponse(ApiSchema):
    assignment: SessionAssignmentDetailResponse
    session: SessionResponse
    created: bool

    @classmethod
    def from_result(cls, result: AssignmentResult) -> "SessionAssignmentResponse":
        return cls(
            assignment=SessionAssignmentDetailResponse.from_assignment(
                result.assignment
            ),
            session=SessionResponse.from_view(result.session),
            created=result.created,
        )
