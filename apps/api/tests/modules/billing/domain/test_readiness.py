"""What blocks a close, and what only warns."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.billing.domain.readiness import (
    CRITICAL_FINDING,
    NO_EFFECTIVE_POLICY,
    NO_EFFECTIVE_TARIFF,
    PERIOD_ALREADY_CLOSED,
    UNASSIGNED_ENERGY,
    PeriodSession,
    evaluate_readiness,
)

UNIT = UUID("40000000-0000-0000-0000-000000000001")
START = datetime(2026, 5, 4, 22, 0, tzinfo=UTC)


def session(
    energy: str,
    *,
    unit_id: UUID | None = UNIT,
    status: str = "ready",
) -> PeriodSession:
    return PeriodSession(
        id=uuid4(),
        unit_id=unit_id,
        started_at=START,
        ended_at=START + timedelta(hours=3),
        energy_kwh=Decimal(energy),
        status=status,
    )


def evaluate(sessions, aggregate=None, **overrides):
    defaults = {
        "period_value": "2026-05",
        "status": "open",
        "sessions": tuple(sessions),
        "aggregate_energy_kwh": aggregate,
        "has_effective_tariff": True,
        "has_effective_policy": True,
    }
    return evaluate_readiness(**{**defaults, **overrides})


def test_a_fully_assigned_period_closes():
    readiness = evaluate([session("10"), session("5")])
    assert readiness.can_close
    assert readiness.blockers == ()
    assert readiness.billable_energy_kwh == Decimal(15)
    assert readiness.assignment_coverage == Decimal("1.0000")


def test_internal_difference_is_exactly_the_unassigned_energy():
    """The number a manager needs: how much would silently go unbilled."""
    readiness = evaluate([session("10"), session("4", unit_id=None)])
    assert readiness.period_energy_kwh == Decimal(14)
    assert readiness.billable_energy_kwh == Decimal(10)
    assert readiness.internal_difference_kwh == Decimal(4)


def test_unassigned_energy_blocks_the_close():
    readiness = evaluate([session("10"), session("4", unit_id=None)])
    assert not readiness.can_close
    codes = [blocker.code for blocker in readiness.blockers]
    assert codes == [UNASSIGNED_ENERGY]
    assert readiness.blockers[0].count == 1
    assert "4 kWh" in readiness.blockers[0].detail


def test_a_discarded_session_leaves_the_period_without_blocking_it():
    """Discarding is a decision already taken; it must not hold the close."""
    readiness = evaluate(
        [session("10"), session("4", unit_id=None, status="discarded")]
    )
    assert readiness.can_close
    assert readiness.discarded_count == 1
    assert readiness.period_energy_kwh == Decimal(10)
    assert readiness.internal_difference_kwh == Decimal(0)


def test_external_difference_is_reported_and_never_blocks():
    """The charger and the session list are independent measurements."""
    readiness = evaluate([session("10")], aggregate=Decimal("10.5"))
    assert readiness.external_difference_kwh == Decimal("0.5")
    assert readiness.can_close


def test_external_difference_can_be_negative():
    readiness = evaluate([session("10")], aggregate=Decimal("9.2"))
    assert readiness.external_difference_kwh == Decimal("-0.8")
    assert readiness.can_close


def test_no_aggregate_means_no_external_reconciliation():
    readiness = evaluate([session("10")])
    assert readiness.aggregate_energy_kwh is None
    assert readiness.external_difference_kwh is None
    assert readiness.can_close


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"has_effective_tariff": False}, NO_EFFECTIVE_TARIFF),
        ({"has_effective_policy": False}, NO_EFFECTIVE_POLICY),
        ({"critical_finding_count": 2}, CRITICAL_FINDING),
        ({"status": "closed"}, PERIOD_ALREADY_CLOSED),
    ],
)
def test_each_condition_blocks_the_close(override, code):
    readiness = evaluate([session("10")], **override)
    assert not readiness.can_close
    assert code in [blocker.code for blocker in readiness.blockers]


def test_blockers_accumulate():
    readiness = evaluate(
        [session("10"), session("4", unit_id=None)],
        has_effective_tariff=False,
        has_effective_policy=False,
        critical_finding_count=1,
    )
    assert [blocker.code for blocker in readiness.blockers] == [
        UNASSIGNED_ENERGY,
        CRITICAL_FINDING,
        NO_EFFECTIVE_TARIFF,
        NO_EFFECTIVE_POLICY,
    ]


def test_coverage_is_a_ratio_of_kept_sessions():
    readiness = evaluate(
        [
            session("10"),
            session("10"),
            session("10"),
            session("10", unit_id=None),
            session("10", status="discarded"),
        ]
    )
    assert readiness.assignment_coverage == Decimal("0.7500")
    assert readiness.billable_count == 3
    assert readiness.pending_count == 1
    assert readiness.discarded_count == 1


def test_an_empty_period_has_no_coverage_and_nothing_to_bill():
    readiness = evaluate([])
    assert readiness.assignment_coverage == Decimal(0)
    assert readiness.period_energy_kwh == Decimal(0)
    assert readiness.can_close
