"""Whether a period can be closed, and what stands in the way.

Two reconciliations run here, and they answer different questions.

The **internal** one asks whether every kilowatt-hour measured in the period has
somewhere to go: it compares the energy of the period's sessions against the
energy that would actually be billed. Anything unassigned shows up as the
difference, and it must reach zero before a close.

The **external** one asks whether the platform and the equipment agree: it
compares the period's measured energy against the total the charger itself
reports. It is a warning, never a blocker, because the two are independent
measurements that may legitimately differ — standby draw, cable losses, a
session the exporter dropped. The product's job is to put the number on screen,
not to hide it and not to refuse work because of it.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

DISCARDED = "discarded"
READY = "ready"

UNASSIGNED_ENERGY = "UNASSIGNED_ENERGY"
CRITICAL_FINDING = "CRITICAL_FINDING"
NO_EFFECTIVE_TARIFF = "NO_EFFECTIVE_TARIFF"
NO_EFFECTIVE_POLICY = "NO_EFFECTIVE_POLICY"
PERIOD_ALREADY_CLOSED = "PERIOD_ALREADY_CLOSED"
NO_CLOSING_OPINION = "NO_CLOSING_OPINION"


@dataclass(frozen=True, slots=True)
class PeriodSession:
    id: UUID
    unit_id: UUID | None
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    status: str

    @property
    def is_discarded(self) -> bool:
        return self.status == DISCARDED

    @property
    def is_billable(self) -> bool:
        """Measured, kept, and pointed at a unit that can be charged for it."""
        return not self.is_discarded and self.unit_id is not None


@dataclass(frozen=True, slots=True)
class PeriodDataset:
    """Everything the readiness evaluation needs about one period.

    A value object rather than a protocol: the evaluation reads data, it does
    not call behaviour, and keeping it concrete lets the domain own the shape.
    """

    sessions: tuple[PeriodSession, ...]
    aggregate_energy_kwh: Decimal | None
    has_effective_tariff: bool
    has_effective_policy: bool
    critical_finding_count: int = 0
    has_closing_opinion: bool = True


@dataclass(frozen=True, slots=True)
class Blocker:
    code: str
    detail: str
    count: int


@dataclass(frozen=True, slots=True)
class Readiness:
    period_value: str
    status: str
    session_count: int
    billable_count: int
    pending_count: int
    discarded_count: int
    period_energy_kwh: Decimal
    billable_energy_kwh: Decimal
    aggregate_energy_kwh: Decimal | None
    internal_difference_kwh: Decimal
    external_difference_kwh: Decimal | None
    assignment_coverage: Decimal
    blockers: tuple[Blocker, ...]

    @property
    def can_close(self) -> bool:
        return not self.blockers


def _sum_energy(sessions: tuple[PeriodSession, ...]) -> Decimal:
    return sum((item.energy_kwh for item in sessions), Decimal(0))


def evaluate_readiness(
    *,
    period_value: str,
    status: str,
    sessions: tuple[PeriodSession, ...],
    aggregate_energy_kwh: Decimal | None,
    has_effective_tariff: bool,
    has_effective_policy: bool,
    critical_finding_count: int = 0,
    has_closing_opinion: bool = True,
) -> Readiness:
    kept = tuple(item for item in sessions if not item.is_discarded)
    billable = tuple(item for item in kept if item.is_billable)
    pending = tuple(item for item in kept if not item.is_billable)

    period_energy = _sum_energy(kept)
    billable_energy = _sum_energy(billable)
    internal_difference = period_energy - billable_energy

    external_difference = (
        aggregate_energy_kwh - period_energy
        if aggregate_energy_kwh is not None
        else None
    )

    coverage = (
        (Decimal(len(billable)) / Decimal(len(kept))).quantize(Decimal("0.0001"))
        if kept
        else Decimal(0)
    )

    blockers: list[Blocker] = []
    if status == "closed":
        blockers.append(
            Blocker(
                code=PERIOD_ALREADY_CLOSED,
                detail="O período já foi fechado e não pode ser fechado de novo.",
                count=1,
            )
        )
    if pending:
        blockers.append(
            Blocker(
                code=UNASSIGNED_ENERGY,
                detail=(
                    f"{len(pending)} recarga(s) sem unidade, somando "
                    f"{internal_difference} kWh que não seriam cobrados."
                ),
                count=len(pending),
            )
        )
    if critical_finding_count:
        blockers.append(
            Blocker(
                code=CRITICAL_FINDING,
                detail=(
                    f"{critical_finding_count} achado(s) crítico(s) do parecer "
                    "aguardando decisão registrada."
                ),
                count=critical_finding_count,
            )
        )
    if not has_effective_tariff:
        blockers.append(
            Blocker(
                code=NO_EFFECTIVE_TARIFF,
                detail="Nenhuma tarifa vigente cobre este período.",
                count=1,
            )
        )
    if not has_effective_policy:
        blockers.append(
            Blocker(
                code=NO_EFFECTIVE_POLICY,
                detail="Nenhuma política de rateio vigente cobre este período.",
                count=1,
            )
        )
    if not has_closing_opinion:
        blockers.append(
            Blocker(
                code=NO_CLOSING_OPINION,
                detail=(
                    "Nenhum parecer de fechamento foi gerado para este período. "
                    "A aprovação precisa referenciar o parecer que o síndico viu."
                ),
                count=1,
            )
        )

    return Readiness(
        period_value=period_value,
        status=status,
        session_count=len(sessions),
        billable_count=len(billable),
        pending_count=len(pending),
        discarded_count=len(sessions) - len(kept),
        period_energy_kwh=period_energy,
        billable_energy_kwh=billable_energy,
        aggregate_energy_kwh=aggregate_energy_kwh,
        internal_difference_kwh=internal_difference,
        external_difference_kwh=external_difference,
        assignment_coverage=coverage,
        blockers=tuple(blockers),
    )
