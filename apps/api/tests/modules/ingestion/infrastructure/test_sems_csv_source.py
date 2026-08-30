from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.modules.ingestion.domain.errors import InvalidSession
from app.modules.ingestion.domain.session import IdentityConfidence, SourceKind
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource

FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"


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
