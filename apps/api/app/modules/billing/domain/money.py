from decimal import ROUND_HALF_UP, Decimal

_ONE = Decimal(1)
_BASIS_POINT_DIVISOR = Decimal(10_000)


def round_cents(amount: Decimal) -> int:
    """The single rounding rule of the billing domain.

    Takes an exact amount already expressed in cents and returns integer cents,
    rounded half-up. Every monetary value passes through here, so calculation,
    screen and PDF cannot disagree.
    """
    return int(amount.quantize(_ONE, rounding=ROUND_HALF_UP))


def energy_value_cents(energy_kwh: Decimal, rate_cents_per_kwh: int) -> int:
    return round_cents(energy_kwh * Decimal(rate_cents_per_kwh))


def basis_points_of(amount_cents: int, basis_points: int) -> int:
    return round_cents(
        Decimal(amount_cents) * Decimal(basis_points) / _BASIS_POINT_DIVISOR
    )
