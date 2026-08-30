from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.modules.ingestion.domain.errors import InvalidSession
from app.modules.ingestion.domain.session import IdentityConfidence, SourceKind
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource

FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"
EXPECTED_HEADER = "Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN"


def test_sems_csv_normalizes_observed_fields_to_utc() -> None:
    source = SemsCsvSource(default_timezone=ZoneInfo("America/Sao_Paulo"))
    records = source.read(FIXTURE.read_bytes())

    session = source.normalize(records[0])

    assert len(records) == 2
    assert session.source is SourceKind.SEMS_EXPORT
    assert session.started_at == datetime(2026, 8, 29, 20, 10, tzinfo=UTC)
    assert session.ended_at == datetime(2026, 8, 29, 21, 10, tzinfo=UTC)
    assert session.energy_kwh == Decimal("7.00")
    assert session.card_id_raw == "97500NAP25BL0008"
    assert session.identity_confidence is IdentityConfidence.UNKNOWN


def test_sems_csv_explains_invalid_energy_with_row_number() -> None:
    source = SemsCsvSource(default_timezone=ZoneInfo("America/Sao_Paulo"))
    content = FIXTURE.read_text(encoding="utf-8").replace("7.00", "not-a-number", 1).encode()
    record = source.read(content)[0]

    with pytest.raises(InvalidSession) as error:
        source.normalize(record)

    assert error.value.field == "Charging Energy(kWh)"
    assert error.value.code == "INVALID_DECIMAL"
    assert "row 2" in error.value.message


@pytest.mark.parametrize(
    "invalid_header",
    [
        f"{EXPECTED_HEADER},Extra Column",
        "Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN,Device SN",
        "End Time,Start Time,Charging Energy(kWh),Charging Port,Card ID,Device SN",
    ],
    ids=["added", "duplicate", "reordered"],
)
def test_sems_csv_rejects_schema_changes_other_than_missing_columns(invalid_header: str) -> None:
    source = SemsCsvSource(default_timezone=ZoneInfo("America/Sao_Paulo"))
    content = FIXTURE.read_text(encoding="utf-8").replace(EXPECTED_HEADER, invalid_header, 1).encode()

    with pytest.raises(InvalidSession) as error:
        source.read(content)

    assert error.value.field == "file"
    assert error.value.code == "INVALID_SCHEMA"
    assert error.value.message == "CSV columns must exactly match the SEMS v1 schema."


def test_sems_csv_preserves_missing_columns_error() -> None:
    source = SemsCsvSource(default_timezone=ZoneInfo("America/Sao_Paulo"))
    content = FIXTURE.read_text(encoding="utf-8").replace(",Device SN", "", 1).encode()

    with pytest.raises(InvalidSession) as error:
        source.read(content)

    assert error.value.field == "file"
    assert error.value.code == "MISSING_COLUMNS"
    assert error.value.message == "Missing columns: Device SN"
