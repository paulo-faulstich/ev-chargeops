from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.sessions.domain.errors import (
    AssignmentForbidden,
    InvalidJustification,
)
from app.modules.sessions.domain.models import (
    AssignmentResult,
    SessionAssignment,
    SessionView,
)

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 8, 30, 18, tzinfo=UTC)
SESSION_ID = UUID("70000000-0000-0000-0000-000000000001")
UNIT_ID = UUID("80000000-0000-0000-0000-000000000001")


def scope(role: OrganizationRole = OrganizationRole.MANAGER) -> OrganizationScope:
    return OrganizationScope(
        auth_user_id=UUID("50000000-0000-0000-0000-000000000001"),
        profile_id=UUID("60000000-0000-0000-0000-000000000001"),
        organization_id=UUID("10000000-0000-0000-0000-000000000001"),
        role=role,
        unit_id=None,
    )


def assignment_result() -> AssignmentResult:
    return AssignmentResult(
        assignment=SessionAssignment(
            id=UUID("90000000-0000-0000-0000-000000000001"),
            session_id=SESSION_ID,
            unit_id=UNIT_ID,
            assigned_by=scope().profile_id,
            justification="Confirmado pelo síndico",
            created_at=NOW,
            updated_at=NOW,
        ),
        session=SessionView(
            id=SESSION_ID,
            started_at=datetime(2026, 8, 29, 17, tzinfo=UTC),
            ended_at=datetime(2026, 8, 29, 18, tzinfo=UTC),
            energy_kwh=Decimal("7.000"),
            charger_serial="97500NAP25BL0008",
            source="sems_export",
            provenance="real",
            identity_confidence="assigned",
            status="ready",
            unit_id=UNIT_ID,
            unit_code="A-101",
            unit_name="Apartment A-101",
            resident_name="Resident One",
            assignment_origin=None,
        ),
        created=True,
    )


class RecordingAssignmentRepository:
    def __init__(self) -> None:
        self.assignment_result = assignment_result()
        self.assignment_call: tuple[
            OrganizationScope,
            UUID,
            UUID,
            str,
            datetime,
        ] | None = None

    async def assign_session(
        self,
        assignment_scope: OrganizationScope,
        session_id: UUID,
        unit_id: UUID,
        justification: str,
        occurred_at: datetime,
    ) -> AssignmentResult:
        self.assignment_call = (
            assignment_scope,
            session_id,
            unit_id,
            justification,
            occurred_at,
        )
        return self.assignment_result


async def test_assign_session_normalizes_reason_and_delegates_once() -> None:
    from app.modules.sessions.application.assign_session import AssignSession

    repository = RecordingAssignmentRepository()
    manager_scope = scope()

    result = await AssignSession(repository, clock=lambda: NOW).execute(
        manager_scope,
        SESSION_ID,
        UNIT_ID,
        "  Confirmado pelo síndico  ",
    )

    assert repository.assignment_call == (
        manager_scope,
        SESSION_ID,
        UNIT_ID,
        "Confirmado pelo síndico",
        NOW,
    )
    assert result == repository.assignment_result


@pytest.mark.parametrize(
    "role",
    tuple(role for role in OrganizationRole if role is not OrganizationRole.MANAGER),
)
async def test_assign_session_rejects_every_non_manager_role_without_repository_call(
    role: OrganizationRole,
) -> None:
    from app.modules.sessions.application.assign_session import AssignSession

    repository = RecordingAssignmentRepository()

    with pytest.raises(AssignmentForbidden):
        await AssignSession(repository, clock=lambda: NOW).execute(
            scope(role),
            SESSION_ID,
            UNIT_ID,
            "Confirmado pelo síndico",
        )

    assert repository.assignment_call is None


async def test_assign_session_rejects_blank_reason_without_repository_call() -> None:
    from app.modules.sessions.application.assign_session import AssignSession

    repository = RecordingAssignmentRepository()

    with pytest.raises(InvalidJustification):
        await AssignSession(repository, clock=lambda: NOW).execute(
            scope(),
            SESSION_ID,
            UNIT_ID,
            "  \n\t  ",
        )

    assert repository.assignment_call is None
