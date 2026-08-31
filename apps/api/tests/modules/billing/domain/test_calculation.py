"""Properties the apportionment must hold regardless of the data it runs on."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from app.modules.billing.domain.calculation import (
    BillableSession,
    calculate_invoices,
    energy_value_in_band,
)
from app.modules.billing.domain.errors import InvalidPolicy
from app.modules.billing.domain.money import round_cents
from app.modules.billing.domain.policy import BillingPolicy
from app.modules.billing.domain.reference import (
    SPRINT1_TIMEZONE,
    sprint1_policy,
    sprint1_tariff,
)

SITE_ZONE = ZoneInfo(SPRINT1_TIMEZONE)
UTC = ZoneInfo("UTC")
UNIT_A = UUID("11111111-1111-1111-1111-111111111111")
UNIT_B = UUID("22222222-2222-2222-2222-222222222222")


def session(unit_id: UUID, hour: int, energy: str, day: int = 4) -> BillableSession:
    started = datetime(2026, 5, day, hour, 0, tzinfo=SITE_ZONE).astimezone(UTC)
    return BillableSession(
        id=uuid4(),
        unit_id=unit_id,
        started_at=started,
        ended_at=started,
        energy_kwh=Decimal(energy),
    )


def calculate(sessions, units=(UNIT_A, UNIT_B)):
    return calculate_invoices(sessions, sprint1_tariff(), sprint1_policy(), units)


def test_same_input_produces_identical_output():
    """Determinism is what lets a closed period be recomputed and defended."""
    sessions = (session(UNIT_A, 19, "10"), session(UNIT_B, 8, "5"))
    assert calculate(sessions) == calculate(sessions)


def test_output_order_does_not_depend_on_input_order():
    forward = (session(UNIT_A, 19, "10"), session(UNIT_B, 8, "5"))
    backward = tuple(reversed(forward))
    assert [d.unit_id for d in calculate(forward)] == [
        d.unit_id for d in calculate(backward)
    ]


def test_every_requested_unit_receives_a_draft():
    """A unit that did not charge is still billed, at zero, so coverage is complete."""
    drafts = calculate((session(UNIT_A, 19, "10"),))
    assert {draft.unit_id for draft in drafts} == {UNIT_A, UNIT_B}


def test_items_are_ordered_chronologically():
    late = session(UNIT_A, 20, "1")
    early = session(UNIT_A, 7, "1")
    draft = next(d for d in calculate((late, early)) if d.unit_id == UNIT_A)
    assert [item.started_at for item in draft.items] == sorted(
        item.started_at for item in draft.items
    )


def test_an_unrequested_unit_with_sessions_is_still_billed():
    """Energy can never fall out of the period because a unit was left off the list."""
    orphan = uuid4()
    drafts = calculate((session(orphan, 19, "4"),), units=(UNIT_A,))
    assert {draft.unit_id for draft in drafts} == {UNIT_A, orphan}


def test_total_energy_is_preserved_across_the_apportionment():
    sessions = (
        session(UNIT_A, 19, "10.5"),
        session(UNIT_A, 8, "2.25"),
        session(UNIT_B, 3, "7"),
    )
    drafts = calculate(sessions)
    assert sum((d.energy_kwh for d in drafts), Decimal(0)) == Decimal("19.75")


def test_a_zero_loss_policy_charges_no_losses():
    policy = BillingPolicy(name="sem perdas", infra_fee_cents=1000, loss_basis_points=0)
    drafts = calculate_invoices(
        (session(UNIT_A, 19, "10"),), sprint1_tariff(), policy, (UNIT_A,)
    )
    assert drafts[0].loss_share_cents == 0
    assert drafts[0].total_cents == drafts[0].energy_value_cents + 1000


@pytest.mark.parametrize("basis_points", [-1, 10_001])
def test_a_loss_share_outside_the_unit_interval_is_rejected(basis_points):
    with pytest.raises(InvalidPolicy):
        BillingPolicy(
            name="inválida", infra_fee_cents=0, loss_basis_points=basis_points
        )


def test_a_negative_infrastructure_fee_is_rejected():
    with pytest.raises(InvalidPolicy):
        BillingPolicy(name="inválida", infra_fee_cents=-1, loss_basis_points=400)


def test_band_comparison_rounds_once_per_session_like_the_close() -> None:
    """The comparison must be a close at that rate, not an approximation.

    Rounding the summed energy instead of each session would drift from what
    the close would actually have produced, which is the only thing that makes
    the figure worth showing.
    """
    energies = (Decimal("1.005"), Decimal("1.005"))

    assert energy_value_in_band(energies, 100) == 202
    # Rounding the total once would give 201, and the invoice never does that.
    assert energy_value_in_band(energies, 100) != round_cents(
        sum(energies, Decimal(0)) * Decimal(100)
    )


def test_band_comparison_of_no_sessions_is_zero() -> None:
    assert energy_value_in_band((), 78) == 0
