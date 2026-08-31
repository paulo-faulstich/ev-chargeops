from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from .money import basis_points_of, energy_value_cents
from .policy import BillingPolicy
from .tariff import TariffSnapshot


@dataclass(frozen=True, slots=True)
class BillableSession:
    """A charging session eligible for billing, already assigned to a unit."""

    id: UUID
    unit_id: UUID
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal


@dataclass(frozen=True, slots=True)
class InvoiceItemDraft:
    """One charging session on an invoice.

    Observed measurements are copied rather than referenced, so the invoice can
    be rendered and defended without re-reading the session, and cannot drift.
    """

    charging_session_id: UUID
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    band_code: str
    rate_cents_per_kwh: int
    value_cents: int


@dataclass(frozen=True, slots=True)
class InvoiceDraft:
    unit_id: UUID
    items: tuple[InvoiceItemDraft, ...]
    energy_kwh: Decimal
    energy_value_cents: int
    infra_fee_cents: int
    loss_share_cents: int
    total_cents: int


def build_item(session: BillableSession, tariff: TariffSnapshot) -> InvoiceItemDraft:
    band = tariff.resolve_band(session.started_at)
    return InvoiceItemDraft(
        charging_session_id=session.id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        energy_kwh=session.energy_kwh,
        band_code=band.code,
        rate_cents_per_kwh=band.rate_cents_per_kwh,
        value_cents=energy_value_cents(session.energy_kwh, band.rate_cents_per_kwh),
    )


def calculate_invoices(
    sessions: tuple[BillableSession, ...],
    tariff: TariffSnapshot,
    policy: BillingPolicy,
    unit_ids: tuple[UUID, ...],
) -> tuple[InvoiceDraft, ...]:
    """Turn eligible sessions into invoice drafts. Pure, deterministic, in cents.

    Rounding happens once per session, so every printed line is independently
    verifiable and the total is the visible sum of the lines.

    Every unit in `unit_ids` receives a draft. A unit that did not charge gets a
    zero invoice with no infrastructure fee, which keeps the period's coverage
    complete and makes the absence auditable instead of silent.
    """
    items_by_unit: dict[UUID, list[InvoiceItemDraft]] = {
        unit_id: [] for unit_id in unit_ids
    }
    for session in sessions:
        items_by_unit.setdefault(session.unit_id, []).append(
            build_item(session, tariff)
        )

    drafts: list[InvoiceDraft] = []
    for unit_id, unit_items in items_by_unit.items():
        items = tuple(
            sorted(
                unit_items,
                key=lambda item: (item.started_at, item.charging_session_id),
            )
        )
        energy_kwh = sum((item.energy_kwh for item in items), Decimal(0))
        energy_cents = sum(item.value_cents for item in items)
        infra_cents = policy.infra_fee_cents if items else 0
        loss_cents = basis_points_of(energy_cents, policy.loss_basis_points)
        drafts.append(
            InvoiceDraft(
                unit_id=unit_id,
                items=items,
                energy_kwh=energy_kwh,
                energy_value_cents=energy_cents,
                infra_fee_cents=infra_cents,
                loss_share_cents=loss_cents,
                total_cents=energy_cents + infra_cents + loss_cents,
            )
        )
    return tuple(sorted(drafts, key=lambda draft: str(draft.unit_id)))


def energy_value_in_band(
    energies: tuple[Decimal, ...], rate_cents_per_kwh: int
) -> int:
    """What the same energy would have cost entirely at one rate.

    Rounds once per session, exactly as the close does, so the comparison is
    the number a close at that rate would have produced rather than an
    approximation of it. It is derived from the versioned tariff alone: no
    invented baseline and no imagined saving.
    """
    return sum(
        energy_value_cents(energy, rate_cents_per_kwh) for energy in energies
    )
