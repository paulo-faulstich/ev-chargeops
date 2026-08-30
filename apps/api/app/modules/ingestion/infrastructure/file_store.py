import re
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from uuid import UUID

import httpx

from app.modules.ingestion.application.import_ports import OriginalFileStorageError

BUCKET = "sems-imports"


def _sanitize_filename(filename: str) -> str:
    if (
        not filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
    ):
        raise OriginalFileStorageError(
            "Original file path resolves outside import directory."
        )
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    if not sanitized:
        raise OriginalFileStorageError("Original file name is invalid.")
    return sanitized


def _object_path(
    organization_id: UUID,
    checksum: str,
    filename: str,
) -> str:
    return f"{organization_id}/{checksum}/{_sanitize_filename(filename)}"


class LocalOriginalFileStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    async def put(
        self,
        organization_id: UUID,
        checksum: str,
        filename: str,
        content: bytes,
    ) -> str:
        object_path = _object_path(organization_id, checksum, filename)
        import_directory = (self.root / str(organization_id) / checksum).resolve()
        target = (self.root / object_path).resolve()
        if target.parent != import_directory or not target.is_relative_to(self.root):
            raise OriginalFileStorageError(
                "Original file path resolves outside import directory."
            )
        import_directory.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as stored_file:
                stored_file.write(content)
        except FileExistsError:
            if target.read_bytes() != content:
                raise OriginalFileStorageError(
                    "Original file object already exists with different content."
                ) from None
        except OSError as error:
            raise OriginalFileStorageError("Original file write failed.") from error
        return object_path

    async def delete(self, storage_path: str) -> None:
        relative_path = PurePosixPath(storage_path)
        parts = relative_path.parts
        if (
            relative_path.is_absolute()
            or len(parts) != 3
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise OriginalFileStorageError(
                "Original file path resolves outside import directory."
            )
        import_directory = (self.root / parts[0] / parts[1]).resolve()
        target = self.root.joinpath(*parts).resolve()
        if target.parent != import_directory or not target.is_relative_to(self.root):
            raise OriginalFileStorageError(
                "Original file path resolves outside import directory."
            )
        try:
            target.unlink(missing_ok=True)
        except OSError as error:
            raise OriginalFileStorageError("Original file delete failed.") from error


class SupabaseOriginalFileStore:
    def __init__(
        self,
        client: httpx.AsyncClient,
        supabase_url: str,
        service_role_key: str,
    ) -> None:
        self.client = client
        self.supabase_url = supabase_url.rstrip("/")
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        }

    async def put(
        self,
        organization_id: UUID,
        checksum: str,
        filename: str,
        content: bytes,
    ) -> str:
        object_path = _object_path(organization_id, checksum, filename)
        try:
            response = await self.client.post(
                f"{self.supabase_url}/storage/v1/object/{BUCKET}/"
                f"{quote(object_path, safe='/')}",
                headers={
                    **self.headers,
                    "Content-Type": "text/csv",
                    "x-upsert": "false",
                },
                content=content,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise OriginalFileStorageError("Original file upload failed.") from error
        return object_path

    async def delete(self, storage_path: str) -> None:
        try:
            response = await self.client.request(
                "DELETE",
                f"{self.supabase_url}/storage/v1/object/{BUCKET}",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"prefixes": [storage_path]},
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise OriginalFileStorageError("Original file delete failed.") from error
