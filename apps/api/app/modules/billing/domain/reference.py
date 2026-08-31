"""Reference tariff and policy delivered and graded in Sprint 1.

These values are the implementation contract for the apportionment model. They
are kept in the domain, rather than in a fixture, because the demo seed and the
golden test must use the very same numbers the Sprint 1 worked example was
computed with.

Band windows were derived from the eight sessions of `data/exemplos/sessoes.csv`
and their `periodo_tarifario` labels, and reproduce every one of them from the
session start time alone. Sprint 1 applied peak pricing on weekends too, so the
windows carry no weekday distinction.
"""

from .policy import BillingPolicy
from .tariff import TariffBand, TariffSnapshot, TariffWindow

SPRINT1_TIMEZONE = "America/Sao_Paulo"

PEAK = "ponta"
MID = "intermediario"
OFF_PEAK = "fora_ponta"


def sprint1_tariff() -> TariffSnapshot:
    return TariffSnapshot(
        name="Referência Sprint 1",
        timezone=SPRINT1_TIMEZONE,
        bands=(
            TariffBand(
                code=PEAK,
                rate_cents_per_kwh=125,
                windows=(TariffWindow(18 * 60, 21 * 60),),
            ),
            TariffBand(
                code=MID,
                rate_cents_per_kwh=95,
                windows=(TariffWindow(6 * 60, 18 * 60),),
            ),
            TariffBand(
                code=OFF_PEAK,
                rate_cents_per_kwh=78,
                windows=(
                    TariffWindow(0, 6 * 60),
                    TariffWindow(21 * 60, 24 * 60),
                ),
            ),
        ),
    )


def sprint1_policy() -> BillingPolicy:
    return BillingPolicy(
        name="Referência Sprint 1",
        infra_fee_cents=2_500,
        loss_basis_points=400,
    )
