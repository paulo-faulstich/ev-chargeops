from zoneinfo import ZoneInfo

from app.modules.ingestion.application.preview_import import PreviewImport
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource


def test_preview_classifies_valid_duplicate_and_invalid_rows() -> None:
    content = b"""Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1,97500NAP25BL0008
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1,97500NAP25BL0008
29/08/2026 19:10:00,29/08/2026 20:10:00,0.00,1,CARD-2,97500NAP25BL0008
"""
    use_case = PreviewImport(SemsCsvSource(ZoneInfo("America/Sao_Paulo")))

    preview = use_case.execute("sems.csv", content)

    assert preview.total_count == 3
    assert preview.valid_count == 1
    assert preview.duplicate_count == 1
    assert preview.invalid_count == 1
    assert preview.records[1].classification == "duplicate"
    assert preview.records[2].error_code == "ENERGY_NOT_POSITIVE"
    assert len(preview.checksum) == 64


def test_preview_classifies_truncated_row_as_invalid_and_continues() -> None:
    content = b"""Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1
29/08/2026 19:10:00,29/08/2026 20:10:00,7.00,1,CARD-2,97500NAP25BL0008
"""
    use_case = PreviewImport(SemsCsvSource(ZoneInfo("America/Sao_Paulo")))

    preview = use_case.execute("sems.csv", content)

    assert preview.total_count == 2
    assert preview.invalid_count == 1
    assert preview.valid_count == 1
    assert preview.records[0].classification == "invalid"
    assert preview.records[0].error_field == "Device SN"
    assert preview.records[0].error_code == "MISSING_VALUE"
    assert preview.records[1].classification == "valid"


def test_preview_classifies_surplus_cells_as_invalid_and_continues() -> None:
    content = b"""Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1,97500NAP25BL0008,unexpected
29/08/2026 19:10:00,29/08/2026 20:10:00,7.00,1,CARD-2,97500NAP25BL0008
"""
    use_case = PreviewImport(SemsCsvSource(ZoneInfo("America/Sao_Paulo")))

    preview = use_case.execute("sems.csv", content)

    assert preview.total_count == 2
    assert preview.invalid_count == 1
    assert preview.valid_count == 1
    assert preview.records[0].classification == "invalid"
    assert preview.records[0].error_field == "row"
    assert preview.records[0].error_code == "SURPLUS_CELLS"
    assert preview.records[0].error_message == "A linha 2 tem células a mais do que colunas."
    assert preview.records[0].raw["__extra_cell_1"] == "unexpected"
    assert preview.records[1].classification == "valid"
