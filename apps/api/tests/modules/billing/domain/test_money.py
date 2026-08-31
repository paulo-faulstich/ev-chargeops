"""The single rounding rule of the billing domain.

Half-up is chosen over Python's default banker's rounding because a resident
checking a bill expects half a cent to go up, and because the printed lines must
add up to the printed total under the same rule everywhere.
"""

from decimal import Decimal

import pytest

from app.modules.billing.domain.money import (
    basis_points_of,
    energy_value_cents,
    round_cents,
)


@pytest.mark.parametrize(
    ("amount", "expected"),
    [("0.5", 1), ("1.5", 2), ("2.5", 3), ("-0.5", -1), ("0.4999", 0), ("0.5001", 1)],
)
def test_rounding_is_half_up_not_bankers(amount, expected):
    assert round_cents(Decimal(amount)) == expected


@pytest.mark.parametrize(
    ("energy", "rate", "expected"),
    [
        ("21.5", 78, 1677),
        ("3.1", 78, 242),
        ("12.2", 125, 1525),
        ("17.8", 95, 1691),
        ("0", 125, 0),
    ],
)
def test_energy_value_uses_the_same_rule(energy, rate, expected):
    assert energy_value_cents(Decimal(energy), rate) == expected


@pytest.mark.parametrize(
    ("amount_cents", "basis_points", "expected"),
    [(3791, 400, 152), (4275, 400, 171), (2348, 400, 94), (0, 400, 0), (1000, 0, 0)],
)
def test_basis_points_reproduce_the_sprint1_loss_share(
    amount_cents, basis_points, expected
):
    assert basis_points_of(amount_cents, basis_points) == expected


def test_losses_on_zero_energy_are_zero():
    assert basis_points_of(0, 10_000) == 0


def test_energy_with_more_precision_than_cents_still_lands_on_an_integer():
    assert isinstance(energy_value_cents(Decimal("1.23456789"), 97), int)
