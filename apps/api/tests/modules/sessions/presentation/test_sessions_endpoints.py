from conftest import OTHER_SESSION_ID, OTHER_UNIT_ID, import_fixture
from fastapi.testclient import TestClient


def test_manager_lists_filtered_canonical_sessions_without_raw_identity(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    import_fixture(api_client, auth_headers)

    response = api_client.get(
        "/v1/sessions?period=2026-08&status=pending_review",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert {item["identityConfidence"] for item in body["items"]} == {"unknown"}
    assert {item["status"] for item in body["items"]} == {"pending_review"}
    assert all(item["unitId"] is None for item in body["items"])
    assert all("cardIdRaw" not in item and "raw" not in item for item in body["items"])


def test_manager_lists_seeded_assignment_units_without_email(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = api_client.get("/v1/assignment-units", headers=auth_headers)

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["code"] for item in items] == ["A-101", "A-102", "A-103", "A-104"]
    assert all("email" not in item for item in items)


def test_manager_assigns_session_and_receives_ready_canonical_view(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    import_fixture(api_client, auth_headers)
    session_id = api_client.get("/v1/sessions", headers=auth_headers).json()["items"][0]["id"]
    unit = api_client.get("/v1/assignment-units", headers=auth_headers).json()["items"][0]

    response = api_client.put(
        f"/v1/sessions/{session_id}/assignment",
        headers=auth_headers,
        json={
            "unitId": unit["id"],
            "justification": "  Confirmado pelo síndico  ",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] is True
    assert body["assignment"]["sessionId"] == session_id
    assert body["assignment"]["unitId"] == unit["id"]
    assert body["assignment"]["justification"] == "Confirmado pelo síndico"
    assert body["session"]["identityConfidence"] == "assigned"
    assert body["session"]["status"] == "ready"
    assert body["session"]["unitId"] == unit["id"]
    assert "cardIdRaw" not in body["session"]


def test_session_endpoints_require_authentication(api_client: TestClient) -> None:
    assert api_client.get("/v1/sessions").status_code == 401
    assert api_client.get("/v1/assignment-units").status_code == 401
    assert (
        api_client.put(
            "/v1/sessions/90000000-0000-0000-0000-000000000001/assignment",
            json={
                "unitId": "40000000-0000-0000-0000-000000000001",
                "justification": "Known reason",
            },
        ).status_code
        == 401
    )


def test_resident_cannot_review_or_assign_sessions(
    api_client: TestClient,
    resident_headers: dict[str, str],
) -> None:
    assert api_client.get("/v1/sessions", headers=resident_headers).status_code == 403
    assert (
        api_client.get("/v1/assignment-units", headers=resident_headers).status_code
        == 403
    )
    assert (
        api_client.put(
            "/v1/sessions/90000000-0000-0000-0000-000000000001/assignment",
            headers=resident_headers,
            json={
                "unitId": "40000000-0000-0000-0000-000000000001",
                "justification": "Known reason",
            },
        ).status_code
        == 403
    )


def test_sessions_reject_malformed_period(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = api_client.get("/v1/sessions?period=2026-13", headers=auth_headers)

    assert response.status_code == 422
    assert response.json()["error"]["details"] == [{"field": "period"}]


def test_assignment_rejects_blank_justification(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    import_fixture(api_client, auth_headers)
    session_id = api_client.get("/v1/sessions", headers=auth_headers).json()["items"][0]["id"]

    response = api_client.put(
        f"/v1/sessions/{session_id}/assignment",
        headers=auth_headers,
        json={
            "unitId": "40000000-0000-0000-0000-000000000001",
            "justification": "   ",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"] == [{"field": "justification"}]


def test_assignment_request_validation_uses_declared_error_envelope(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = api_client.put(
        "/v1/sessions/not-a-uuid/assignment",
        headers=auth_headers,
        json={
            "unitId": "40000000-0000-0000-0000-000000000001",
            "justification": "Known reason",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "INVALID_REQUEST",
            "message": "Request validation failed.",
            "details": [{"field": "sessionId"}],
        }
    }


def test_assignment_hides_cross_tenant_session_and_unit_ids(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    import_fixture(api_client, auth_headers)
    local_session_id = api_client.get("/v1/sessions", headers=auth_headers).json()["items"][0]["id"]
    local_unit_id = api_client.get("/v1/assignment-units", headers=auth_headers).json()["items"][0]["id"]

    foreign_session = api_client.put(
        f"/v1/sessions/{OTHER_SESSION_ID}/assignment",
        headers=auth_headers,
        json={"unitId": local_unit_id, "justification": "Known reason"},
    )
    foreign_unit = api_client.put(
        f"/v1/sessions/{local_session_id}/assignment",
        headers=auth_headers,
        json={"unitId": str(OTHER_UNIT_ID), "justification": "Known reason"},
    )

    assert foreign_session.status_code == 404
    assert foreign_unit.status_code == 404
    assert foreign_session.json() == {"detail": "Session not found."}
    assert foreign_unit.json() == {"detail": "Unit not found."}
