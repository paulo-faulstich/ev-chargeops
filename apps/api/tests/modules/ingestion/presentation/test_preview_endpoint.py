from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"


def test_preview_endpoint_returns_camel_case_summary() -> None:
    response = TestClient(app).post(
        "/v1/import-batches/preview",
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


def test_preview_endpoint_returns_stable_error_for_unsupported_file() -> None:
    response = TestClient(app).post(
        "/v1/import-batches/preview",
        files={"file": ("sessions.txt", b"not csv", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "UNSUPPORTED_FILE",
            "message": "Only CSV files are supported.",
            "details": [{"field": "file"}],
        }
    }


def test_preview_endpoint_returns_stable_error_when_file_is_omitted() -> None:
    response = TestClient(app).post("/v1/import-batches/preview")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "FILE_REQUIRED",
            "message": "A file is required.",
            "details": [{"field": "file"}],
        }
    }


def test_preview_endpoint_preserves_missing_cells_and_continues() -> None:
    content = b"""Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
29/08/2026 17:10:00,29/08/2026 18:10:00,7.00,1,CARD-1
29/08/2026 19:10:00,29/08/2026 20:10:00,7.00,1,CARD-2,97500NAP25BL0008
"""

    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/import-batches/preview",
        files={"file": ("sems.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["invalidCount"] == 1
    assert body["validCount"] == 1
    assert body["records"][0]["raw"]["Device SN"] is None
    assert body["records"][0]["errorCode"] == "MISSING_VALUE"
    assert body["records"][1]["classification"] == "valid"
