from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256

from .errors import InvalidSession


class SourceKind(StrEnum):
    SEMS_EXPORT = "sems_export"
    MANUAL = "manual"
    SIMULATED = "simulated"
    GOODWE_API = "goodwe_api"


class IdentityConfidence(StrEnum):
    CONFIRMED = "confirmed"
    ASSIGNED = "assigned"
    UNKNOWN = "unknown"


class DataProvenance(StrEnum):
    REAL = "real"
    ASSIGNED = "assigned"
    SIMULATED = "simulated"
    DERIVED = "derived"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class SessionCandidate:
    source: SourceKind
    external_id: str | None
    charger_serial: str
    started_at: datetime
    ended_at: datetime
    energy_kwh: Decimal
    charge_port: int | None
    card_id_raw: str | None
    identity_confidence: IdentityConfidence
    provenance: DataProvenance
    deduplication_key: str

    @classmethod
    def create(
        cls,
        *,
        source: SourceKind,
        external_id: str | None,
        charger_serial: str,
        started_at: datetime,
        ended_at: datetime,
        energy_kwh: Decimal,
        charge_port: int | None,
        card_id_raw: str | None,
    ) -> "SessionCandidate":
        if started_at.tzinfo is None or started_at.utcoffset() is None:
            raise InvalidSession("started_at", "TIMEZONE_REQUIRED", "Start time must include a timezone.")
        if ended_at.tzinfo is None or ended_at.utcoffset() is None:
            raise InvalidSession("ended_at", "TIMEZONE_REQUIRED", "End time must include a timezone.")
        if ended_at <= started_at:
            raise InvalidSession("ended_at", "END_NOT_AFTER_START", "End time must be after start time.")
        if energy_kwh <= 0:
            raise InvalidSession("energy_kwh", "ENERGY_NOT_POSITIVE", "Energy must be greater than zero.")
        if not charger_serial.strip():
            raise InvalidSession("charger_serial", "CHARGER_REQUIRED", "Charger serial is required.")

        normalized_serial = charger_serial.strip()
        started_at_utc = started_at.astimezone(UTC)
        ended_at_utc = ended_at.astimezone(UTC)
        payload = "|".join(
            (
                source.value,
                normalized_serial,
                started_at_utc.isoformat(),
                ended_at_utc.isoformat(),
                format(energy_kwh.normalize(), "f"),
            )
        )
        return cls(
            source=source,
            external_id=external_id,
            charger_serial=normalized_serial,
            started_at=started_at_utc,
            ended_at=ended_at_utc,
            energy_kwh=energy_kwh,
            charge_port=charge_port,
            card_id_raw=card_id_raw or None,
            identity_confidence=IdentityConfidence.UNKNOWN,
            provenance=provenance_of(source),
            deduplication_key=sha256(payload.encode("utf-8")).hexdigest(),
        )


def provenance_of(source: SourceKind) -> DataProvenance:
    """Provenance follows from the source and is never chosen by the caller.

    A demonstrative scenario must not be able to enter the system claiming to be
    observed telemetry. Deriving the value here turns the guardrail "no simulated
    session is ever presented as real" into something the type system enforces at
    construction, instead of a rule every future adapter has to remember.
    """
    if source is SourceKind.SIMULATED:
        return DataProvenance.SIMULATED
    return DataProvenance.REAL
