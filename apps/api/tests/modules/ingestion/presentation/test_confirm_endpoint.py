from pathlib import Path

from fastapi.testclient import TestClient

FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"


def post_fixture(
    api_client: TestClient,
    fixture_token: str,
    *,
    filename: str = "sems.csv",
) -> object:
    return api_client.post(
        "/v1/import-batches",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": (filename, FIXTURE.read_bytes(), "text/csv")},
    )


def test_confirm_endpoint_persists_authenticated_batch(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    response = post_fixture(api_client, fixture_token)

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["totalCount"] == 2
    assert body["validCount"] == 2
    assert body["invalidCount"] == 0
    assert body["duplicateCount"] == 0


def test_confirm_replay_returns_existing_batch(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    first = post_fixture(api_client, fixture_token)
    replay = post_fixture(api_client, fixture_token, filename="renamed.csv")

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["filename"] == "sems.csv"
    assert replay.json()["created"] is False


def test_import_endpoints_require_bearer_token(api_client: TestClient) -> None:
    assert api_client.get("/v1/import-batches").status_code == 401
    assert api_client.post("/v1/import-batches/preview").status_code == 401
    assert api_client.post("/v1/import-batches").status_code == 401
    assert (
        api_client.get(
            "/v1/import-batches/10000000-0000-0000-0000-000000000001"
        ).status_code
        == 401
    )


def test_confirm_returns_stable_error_for_unsupported_file(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    response = api_client.post(
        "/v1/import-batches",
        headers={"Authorization": f"Bearer {fixture_token}"},
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


def test_confirm_requires_a_file(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    response = api_client.post(
        "/v1/import-batches",
        headers={"Authorization": f"Bearer {fixture_token}"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FILE_REQUIRED"


def test_confirm_uses_the_uploaded_file_bytes(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    content = FIXTURE.read_bytes().replace(b"7.00", b"8.25", 1)

    response = api_client.post(
        "/v1/import-batches",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("changed.csv", content, "text/csv")},
    )

    assert response.status_code == 201
    assert response.json()["filename"] == "changed.csv"
