"""The resident context: one unit, read-only, short-lived, audited.

This is the only door to the `resident` role in this increment. A future
resident login adds another way to obtain the same scope; it changes nothing
here.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ResidentContextView:
    id: UUID
    organization_id: UUID
    unit_id: UUID
    unit_code: str
    unit_name: str
    expires_at: datetime


class ResidentContextNotActive(LookupError):
    """Missing, expired, exited, or not issued to this manager."""


class ResidentContextUnitNotFound(LookupError):
    pass
