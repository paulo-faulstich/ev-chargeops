import csv
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from zoneinfo import ZoneInfo

from app.modules.ingestion.application.ports import SourceRecord
from app.modules.ingestion.domain.errors import InvalidSession
from app.modules.ingestion.domain.session import SessionCandidate, SourceKind

SEMS_V1_COLUMNS = (
    "Start Time",
    "End Time",
    "Charging Energy(kWh)",
    "Charging Port",
    "Card ID",
    "Device SN",
)
REQUIRED_COLUMNS = set(SEMS_V1_COLUMNS)


class SemsCsvSource:
    kind = SourceKind.SEMS_EXPORT

    def __init__(self, default_timezone: ZoneInfo) -> None:
        self.default_timezone = default_timezone

    def read(self, content: bytes) -> list[SourceRecord]:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise InvalidSession(
                "file", "INVALID_ENCODING", "CSV must use UTF-8 encoding."
            ) from error

        reader = csv.DictReader(StringIO(text))
        columns = reader.fieldnames or []
        missing = sorted(REQUIRED_COLUMNS - set(columns))
        if missing:
            raise InvalidSession(
                "file", "MISSING_COLUMNS", f"Missing columns: {', '.join(missing)}"
            )
        if tuple(columns) != SEMS_V1_COLUMNS:
            raise InvalidSession(
                "file",
                "INVALID_SCHEMA",
                "CSV columns must exactly match the SEMS v1 schema.",
            )

        return [
            SourceRecord(row_number=index, raw=dict(row))
            for index, row in enumerate(reader, start=2)
        ]

    def normalize(self, record: SourceRecord) -> SessionCandidate:
        raw = record.raw
        started_at = self._datetime(
            self._value(raw, "Start Time", record.row_number),
            "Start Time",
            record.row_number,
        )
        ended_at = self._datetime(
            self._value(raw, "End Time", record.row_number),
            "End Time",
            record.row_number,
        )
        try:
            energy_kwh = Decimal(
                self._value(raw, "Charging Energy(kWh)", record.row_number).strip()
            )
        except InvalidOperation as error:
            raise InvalidSession(
                "Charging Energy(kWh)",
                "INVALID_DECIMAL",
                f"Invalid energy at row {record.row_number}.",
            ) from error
        port_text = self._value(raw, "Charging Port", record.row_number).strip()
        try:
            charge_port = int(port_text) if port_text else None
        except ValueError as error:
            raise InvalidSession(
                "Charging Port",
                "INVALID_INTEGER",
                f"Invalid charging port at row {record.row_number}.",
            ) from error

        return SessionCandidate.create(
            source=self.kind,
            external_id=None,
            charger_serial=self._value(raw, "Device SN", record.row_number),
            started_at=started_at,
            ended_at=ended_at,
            energy_kwh=energy_kwh,
            charge_port=charge_port,
            card_id_raw=self._value(raw, "Card ID", record.row_number).strip() or None,
        )

    def _value(self, raw: Mapping[str, str | None], field: str, row_number: int) -> str:
        value = raw.get(field)
        if value is None:
            raise InvalidSession(
                field,
                "MISSING_VALUE",
                f"Missing value for {field} at row {row_number}.",
            )
        return value

    def _datetime(self, value: str, field: str, row_number: int) -> datetime:
        try:
            return datetime.strptime(value.strip(), "%d/%m/%Y %H:%M:%S").replace(
                tzinfo=self.default_timezone
            )
        except ValueError as error:
            raise InvalidSession(
                field,
                "INVALID_DATETIME",
                f"Invalid datetime at row {row_number}.",
            ) from error
