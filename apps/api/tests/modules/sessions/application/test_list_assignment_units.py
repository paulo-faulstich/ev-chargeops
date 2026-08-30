from uuid import UUID

import pytest

from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.sessions.domain.models import AssignmentUnitView
from tests.modules.sessions.application.fakes import RecordingSessionRepository

pytestmark = pytest.mark.asyncio


def scope() -> OrganizationScope:
    return OrganizationScope(
        auth_user_id=UUID("50000000-0000-0000-0000-000000000001"),
        profile_id=UUID("60000000-0000-0000-0000-000000000001"),
        organization_id=UUID("10000000-0000-0000-0000-000000000001"),
        role=OrganizationRole.MANAGER,
        unit_id=None,
    )


async def test_list_assignment_units_uses_authorized_organization_scope() -> None:
    from app.modules.sessions.application.list_assignment_units import (
        ListAssignmentUnits,
    )

    expected = (
        AssignmentUnitView(
            id=UUID("80000000-0000-0000-0000-000000000001"),
            code="101",
            display_name="Apartment 101",
            resident_name=None,
        ),
    )
    repository = RecordingSessionRepository(units=expected)

    units = await ListAssignmentUnits(repository).execute(scope())

    assert units == expected
    assert repository.list_assignment_unit_calls == [scope().organization_id]
