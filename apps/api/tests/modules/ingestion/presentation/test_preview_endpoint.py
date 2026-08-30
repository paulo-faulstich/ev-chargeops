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
