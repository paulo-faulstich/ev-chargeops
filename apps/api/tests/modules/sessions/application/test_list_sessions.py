from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.sessions.domain.errors import InvalidPeriod
from app.modules.sessions.domain.models import SessionView
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


def session_view() -> SessionView:
    return SessionView(
        id=UUID("70000000-0000-0000-0000-000000000001"),
        started_at=datetime(2026, 8, 29, 17, tzinfo=UTC),
        ended_at=datetime(2026, 8, 29, 18, tzinfo=UTC),
        energy_kwh=Decimal("7.000"),
        charger_serial="97500NAP25BL0008",
        source="sems_export",
        provenance="real",
        identity_confidence="unknown",
        status="pending_review",
        unit_id=None,
        unit_code=None,
        unit_name=None,
        resident_name=None,
        assignment_origin=None,
    )


async def test_list_sessions_uses_authorized_organization_and_filters() -> None:
    from app.modules.sessions.application.list_sessions import ListSessions

    repository = RecordingSessionRepository(sessions=(session_view(),))

    sessions = await ListSessions(repository).execute(
        scope(),
        period="2026-08",
        status="pending_review",
    )

    assert sessions == (session_view(),)
    assert repository.list_session_calls == [
        (scope().organization_id, "2026-08", "pending_review"),
    ]


@pytest.mark.parametrize("period", ["2026-13", "2026-8", "August 2026"])
async def test_list_sessions_rejects_malformed_period(period: str) -> None:
    from app.modules.sessions.application.list_sessions import ListSessions

    with pytest.raises(InvalidPeriod):
        await ListSessions(RecordingSessionRepository()).execute(
            scope(),
            period=period,
            status=None,
        )
