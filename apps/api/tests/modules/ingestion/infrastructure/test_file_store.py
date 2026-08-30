import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from app.modules.ingestion.application.import_ports import OriginalFileStorageError
from app.modules.ingestion.infrastructure.file_store import (
    LocalOriginalFileStore,
    SupabaseOriginalFileStore,
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
CHECKSUM = "a" * 64
OBJECT_PATH = f"{ORGANIZATION_ID}/{CHECKSUM}/sems.csv"

pytestmark = pytest.mark.asyncio


async def test_local_store_writes_and_deletes_tenant_checksum_object(
    tmp_path: Path,
) -> None:
    store = LocalOriginalFileStore(tmp_path)

    storage_path = await store.put(
        ORGANIZATION_ID,
        CHECKSUM,
        "sems.csv",
        b"observed,csv\n",
    )

    assert storage_path == OBJECT_PATH
    assert (tmp_path / OBJECT_PATH).read_bytes() == b"observed,csv\n"

    await store.delete(storage_path)

    assert not (tmp_path / OBJECT_PATH).exists()


async def test_local_store_rejects_filename_traversal(tmp_path: Path) -> None:
    store = LocalOriginalFileStore(tmp_path)

    with pytest.raises(OriginalFileStorageError, match="outside import directory"):
        await store.put(
            ORGANIZATION_ID,
            CHECKSUM,
            "../../secret.csv",
            b"secret",
        )

    assert list(tmp_path.rglob("*")) == []


async def test_local_store_rejects_delete_traversal(tmp_path: Path) -> None:
    victim = tmp_path / "victim.csv"
    victim.write_bytes(b"must remain")
    store = LocalOriginalFileStore(tmp_path)

    with pytest.raises(OriginalFileStorageError, match="outside import directory"):
        await store.delete(f"{ORGANIZATION_ID}/{CHECKSUM}/../../victim.csv")

    assert victim.read_bytes() == b"must remain"


async def test_supabase_store_uses_private_immutable_storage_requests() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = SupabaseOriginalFileStore(
            client,
            "https://project.supabase.co/",
            "service-role-secret",
        )

        storage_path = await store.put(
            ORGANIZATION_ID,
            CHECKSUM,
            "sems.csv",
            b"observed,csv\n",
        )
        await store.delete(storage_path)

    upload, delete = requests
    assert storage_path == OBJECT_PATH
    assert upload.method == "POST"
    assert str(upload.url) == (
        "https://project.supabase.co/storage/v1/object/sems-imports/" + OBJECT_PATH
    )
    assert upload.headers["apikey"] == "service-role-secret"
    assert upload.headers["authorization"] == "Bearer service-role-secret"
    assert upload.headers["content-type"] == "text/csv"
    assert upload.headers["x-upsert"] == "false"
    assert upload.content == b"observed,csv\n"
    assert delete.method == "DELETE"
    assert str(delete.url) == (
        "https://project.supabase.co/storage/v1/object/sems-imports"
    )
    assert delete.headers["apikey"] == "service-role-secret"
    assert delete.headers["authorization"] == "Bearer service-role-secret"
    assert delete.headers["content-type"] == "application/json"
    assert json.loads(delete.content) == {"prefixes": [OBJECT_PATH]}


async def test_supabase_store_wraps_http_errors_stably() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = SupabaseOriginalFileStore(
            client,
            "https://project.supabase.co",
            "service-role-secret",
        )

        with pytest.raises(
            OriginalFileStorageError,
            match="Original file upload failed.",
        ) as error:
            await store.put(
                ORGANIZATION_ID,
                CHECKSUM,
                "sems.csv",
                b"observed,csv\n",
            )

    assert "service-role-secret" not in str(error.value)
