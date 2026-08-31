"""Read views of issued invoices.

These are projections of rows already persisted by the close transaction. They
carry the stored integers untouched: no field here is ever recomputed, so the
API, the screen and the PDF all show the same cents the close wrote.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class InvoiceItemView:
    id: UUID
    charging_session_id: UUID
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    band_code: str
    rate_cents_per_kwh: int
    value_cents: int


@dataclass(frozen=True, slots=True)
class InvoiceView:
    id: UUID
    number: str
    billing_period_id: UUID
    period_value: str
    unit_id: UUID
    unit_code: str
    unit_name: str
    contact_label: str
    energy_kwh: Decimal
    energy_value_cents: int
    infra_fee_cents: int
    loss_share_cents: int
    total_cents: int
    issued_at: datetime
    items: tuple[InvoiceItemView, ...]
