import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from zoneinfo import ZoneInfo

from app.modules.ingestion.application.ports import SourceRecord
from app.modules.ingestion.domain.errors import InvalidSession
from app.modules.ingestion.domain.session import SessionCandidate, SourceKind

REQUIRED_COLUMNS = {
    "Start Time",
    "End Time",
    "Charging Energy(kWh)",
    "Charging Port",
    "Card ID",
    "Device SN",
}


class SemsCsvSource:
    kind = SourceKind.SEMS_EXPORT

    def __init__(self, default_timezone: ZoneInfo) -> None:
        self.default_timezone = default_timezone

    def read(self, content: bytes) -> list[SourceRecord]:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise InvalidSession("file", "INVALID_ENCODING", "CSV must use UTF-8 encoding.") from error

        reader = csv.DictReader(StringIO(text))
        columns = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise InvalidSession("file", "MISSING_COLUMNS", f"Missing columns: {', '.join(missing)}")

        return [SourceRecord(row_number=index, raw=dict(row)) for index, row in enumerate(reader, start=2)]

    def normalize(self, record: SourceRecord) -> SessionCandidate:
        raw = record.raw
        started_at = self._datetime(raw["Start Time"], "Start Time", record.row_number)
        ended_at = self._datetime(raw["End Time"], "End Time", record.row_number)
        try:
            energy_kwh = Decimal(raw["Charging Energy(kWh)"].strip())
        except InvalidOperation as error:
            raise InvalidSession(
                "Charging Energy(kWh)",
                "INVALID_DECIMAL",
                f"Invalid energy at row {record.row_number}.",
            ) from error
        port_text = raw["Charging Port"].strip()
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
            charger_serial=raw["Device SN"],
            started_at=started_at,
            ended_at=ended_at,
            energy_kwh=energy_kwh,
            charge_port=charge_port,
            card_id_raw=raw["Card ID"].strip() or None,
        )

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
