from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"


def test_preview_endpoint_returns_camel_case_summary(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    response = api_client.post(
        "/v1/import-batches/preview",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("sems.csv", FIXTURE.read_bytes(), "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "sems_export"
    assert body["totalCount"] == 2
    assert body["validCount"] == 2
    assert body["invalidCount"] == 0
    assert body["duplicateCount"] == 0
    assert body["records"][0]["session"]["provenance"] == "real"
    assert body["records"][0]["session"]["identityConfidence"] == "unknown"


def test_preview_endpoint_returns_stable_error_for_unsupported_file(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    response = api_client.post(
        "/v1/import-batches/preview",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("sessions.txt", b"not csv", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "UNSUPPORTED_FILE",
            "message": "Só arquivos CSV são aceitos.",
            "details": [{"field": "file"}],
        }
    }


def test_preview_endpoint_returns_stable_error_when_file_is_omitted(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    response = api_client.post(
        "/v1/import-batches/preview",
        headers={"Authorization": f"Bearer {fixture_token}"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "FILE_REQUIRED",
            "message": "A file is required.",
            "details": [{"field": "file"}],
        }
    }


def test_preview_endpoint_preserves_missing_cells_and_continues(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    content = b"""Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1
29/08/2026 19:10:00,29/08/2026 20:10:00,7.00,1,CARD-2,97500NAP25BL0008
"""

    response = api_client.post(
        "/v1/import-batches/preview",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("sems.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["invalidCount"] == 1
    assert body["validCount"] == 1
    assert body["records"][0]["raw"]["Device SN"] is None
    assert body["records"][0]["errorCode"] == "MISSING_VALUE"
    assert body["records"][1]["classification"] == "valid"


def test_preview_endpoint_preserves_surplus_cells_and_continues(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    content = b"""Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1,97500NAP25BL0008,unexpected,second
29/08/2026 19:10:00,29/08/2026 20:10:00,7.00,1,CARD-2,97500NAP25BL0008
"""

    response = api_client.post(
        "/v1/import-batches/preview",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("sems.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["invalidCount"] == 1
    assert body["validCount"] == 1
    assert body["records"][0]["raw"]["__extra_cell_1"] == "unexpected"
    assert body["records"][0]["raw"]["__extra_cell_2"] == "second"
    assert body["records"][0]["errorCode"] == "SURPLUS_CELLS"
    assert body["records"][0]["errorMessage"] == "A linha 2 tem células a mais do que colunas."
    assert body["records"][1]["classification"] == "valid"


@pytest.mark.parametrize("energy", ["NaN", "Infinity", "-Infinity"])
def test_preview_endpoint_rejects_non_finite_energy_and_continues(
    energy: str,
    api_client: TestClient,
    fixture_token: str,
) -> None:
    content = f"""Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
29/08/2026 17:10:00,29/08/2026 18:10:00,{energy},1,CARD-1,97500NAP25BL0008
29/08/2026 19:10:00,29/08/2026 20:10:00,7.00,1,CARD-2,97500NAP25BL0008
""".encode()

    response = api_client.post(
        "/v1/import-batches/preview",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("sems.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["invalidCount"] == 1
    assert body["validCount"] == 1
    assert body["records"][0]["classification"] == "invalid"
    assert body["records"][0]["errorField"] == "Charging Energy(kWh)"
    assert body["records"][0]["errorCode"] == "INVALID_DECIMAL"
    assert body["records"][0]["errorMessage"] == "Energia inválida na linha 2."
    assert body["records"][1]["classification"] == "valid"


def test_preview_reports_duplicates_already_persisted(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    confirmed = api_client.post(
        "/v1/import-batches",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("sems.csv", FIXTURE.read_bytes(), "text/csv")},
    )

    response = api_client.post(
        "/v1/import-batches/preview",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("sems.csv", FIXTURE.read_bytes(), "text/csv")},
    )

    assert confirmed.status_code == 201
    assert response.status_code == 200
    assert response.json()["validCount"] == 0
    assert response.json()["duplicateCount"] == 2
    assert {record["classification"] for record in response.json()["records"]} == {
        "duplicate"
    }
