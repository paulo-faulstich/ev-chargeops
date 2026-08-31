from dataclasses import dataclass

from .errors import InvalidPolicy


@dataclass(frozen=True, slots=True)
class BillingPolicy:
    """Immutable apportionment rules for the common costs of shared charging.

    `infra_fee_cents` is a flat amount charged to each unit that charged in the
    period. It is deliberately not a monthly total split among active units: a
    split would make one unit's bill move because a neighbour did or did not
    charge that month, which is indefensible in a condominium assembly.

    `loss_basis_points` covers technical losses and standby draw, charged in
    proportion to each unit's energy value. Basis points keep the rule in
    integers; four percent is 400.
    """

    name: str
    infra_fee_cents: int
    loss_basis_points: int

    def __post_init__(self) -> None:
        if self.infra_fee_cents < 0:
            raise InvalidPolicy("infra fee cannot be negative")
        if not 0 <= self.loss_basis_points <= 10_000:
            raise InvalidPolicy(
                f"loss basis points out of range: {self.loss_basis_points}"
            )
