from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.infrastructure.models import ImportBatchModel
from app.modules.organizations.infrastructure.models import OrganizationModel

OTHER_ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000099")
OTHER_BATCH_ID = UUID("70000000-0000-0000-0000-000000000099")
FIXTURE_PROFILE_ID = UUID("60000000-0000-0000-0000-000000000001")
FIXTURE = Path(__file__).parents[3] / "fixtures" / "sems_sessions.csv"


def post_fixture(api_client: TestClient, fixture_token: str) -> object:
    return api_client.post(
        "/v1/import-batches",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("sems.csv", FIXTURE.read_bytes(), "text/csv")},
    )


def _second_fixture() -> bytes:
    return b"""Start Time,End Time,Charging Energy(kWh),Charging Port,Card ID,Device SN
29/08/2026 20:10:00,29/08/2026 21:10:00,4.25,1,CARD-3,97500NAP25BL0008
"""


def test_import_history_is_descending_and_includes_summary_counts(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    first = post_fixture(api_client, fixture_token)
    second = api_client.post(
        "/v1/import-batches",
        headers={"Authorization": f"Bearer {fixture_token}"},
        files={"file": ("later.csv", _second_fixture(), "text/csv")},
    )

    response = api_client.get(
        "/v1/import-batches",
        headers={"Authorization": f"Bearer {fixture_token}"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["createdAt"] for item in items] == sorted(
        [item["createdAt"] for item in items], reverse=True
    )
    assert {item["filename"] for item in items} == {"sems.csv", "later.csv"}
    summaries = {
        item["filename"]: (
            item["totalCount"],
            item["validCount"],
            item["invalidCount"],
            item["duplicateCount"],
        )
        for item in items
    }
    assert summaries == {"sems.csv": (2, 2, 0, 0), "later.csv": (1, 1, 0, 0)}


def test_import_detail_exposes_raw_classification_and_session_ids_without_storage(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    confirmed = post_fixture(api_client, fixture_token)

    response = api_client.get(
        f"/v1/import-batches/{confirmed.json()['id']}",
        headers={"Authorization": f"Bearer {fixture_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["records"]) == 2
    assert [record["rowNumber"] for record in body["records"]] == [2, 3]
    assert {record["classification"] for record in body["records"]} == {"valid"}
    assert all(record["sessionId"] for record in body["records"])
    assert "storagePath" not in body
    assert "storageUrl" not in body


@pytest.mark.asyncio
async def test_import_detail_returns_404_for_another_organization_batch(
    api_client: TestClient,
    fixture_token: str,
    async_session: AsyncSession,
) -> None:
    async_session.add(
        OrganizationModel(id=OTHER_ORGANIZATION_ID, name="Other organization")
    )
    async_session.add(
        ImportBatchModel(
            id=OTHER_BATCH_ID,
            organization_id=OTHER_ORGANIZATION_ID,
            source="sems_export",
            checksum="f" * 64,
            filename="other.csv",
            storage_path="private/other.csv",
            status="completed",
            total_count=1,
            valid_count=1,
            invalid_count=0,
            duplicate_count=0,
            created_by=FIXTURE_PROFILE_ID,
            created_at=datetime(2026, 8, 29, tzinfo=UTC),
            updated_at=datetime(2026, 8, 29, tzinfo=UTC),
        )
    )
    await async_session.commit()

    response = api_client.get(
        f"/v1/import-batches/{OTHER_BATCH_ID}",
        headers={"Authorization": f"Bearer {fixture_token}"},
    )

    assert response.status_code == 404


def test_import_detail_returns_404_for_unknown_batch(
    api_client: TestClient,
    fixture_token: str,
) -> None:
    response = api_client.get(
        "/v1/import-batches/70000000-0000-0000-0000-000000000001",
        headers={"Authorization": f"Bearer {fixture_token}"},
    )

    assert response.status_code == 404
