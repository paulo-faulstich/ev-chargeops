import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo

from .errors import InvalidPeriodValue

PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class PeriodStatus(StrEnum):
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


def normalize_period_value(value: str) -> str:
    normalized = value.strip()
    if not PERIOD_PATTERN.match(normalized):
        raise InvalidPeriodValue(normalized)
    return normalized


def period_bounds(period_value: str, timezone: str) -> tuple[datetime, datetime]:
    """Half-open month boundaries in the site's wall clock, expressed in UTC.

    Every part of the system that decides which period a session belongs to must
    use this one function. Measuring in UTC instead would move late-evening
    charging on the last day of the month into the next close.
    """
    zone = ZoneInfo(timezone)
    year, month = (
        int(part) for part in normalize_period_value(period_value).split("-")
    )
    start = datetime(year, month, 1, tzinfo=zone)
    end = (
        datetime(year + 1, 1, 1, tzinfo=zone)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=zone)
    )
    return start.astimezone(UTC), end.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class BillingPeriodView:
    id: UUID
    site_id: UUID
    site_name: str
    timezone: str
    period_value: str
    status: str
    approved_at: datetime | None
    approved_by_name: str | None
    tariff_snapshot_id: UUID | None
    billing_policy_id: UUID | None
    eligible_energy_kwh: Decimal | None
    invoiced_energy_kwh: Decimal | None
    aggregate_energy_kwh: Decimal | None
