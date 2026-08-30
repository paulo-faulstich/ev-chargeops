from collections.abc import AsyncIterator
from typing import Annotated
from zoneinfo import ZoneInfo

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.application.confirm_import import ConfirmImport
from app.modules.ingestion.application.import_ports import (
    ImportRepository,
    OriginalFileStore,
)
from app.modules.ingestion.application.list_imports import (
    GetImportDetail,
    ListImports,
)
from app.modules.ingestion.application.review_import import ReviewImport
from app.modules.ingestion.infrastructure.file_store import (
    LocalOriginalFileStore,
    SupabaseOriginalFileStore,
)
from app.modules.ingestion.infrastructure.repository import (
    SqlAlchemyImportRepository,
)
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource
from app.shared.config import Settings, get_settings
from app.shared.database import get_db_session


def get_import_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ImportRepository:
    return SqlAlchemyImportRepository(session)


def get_sems_source() -> SemsCsvSource:
    return SemsCsvSource(ZoneInfo("America/Sao_Paulo"))


async def get_original_file_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[OriginalFileStore]:
    if settings.original_file_store == "local":
        yield LocalOriginalFileStore(settings.original_files_root)
        return

    service_role_key = settings.supabase_service_role_key
    if service_role_key is None:
        raise RuntimeError("Supabase original-file storage is not configured.")
    async with httpx.AsyncClient() as client:
        yield SupabaseOriginalFileStore(
            client,
            settings.supabase_url,
            service_role_key,
        )


def get_review_import(
    repository: Annotated[ImportRepository, Depends(get_import_repository)],
) -> ReviewImport:
    return ReviewImport(repository)


def get_confirm_import(
    source: Annotated[SemsCsvSource, Depends(get_sems_source)],
    repository: Annotated[ImportRepository, Depends(get_import_repository)],
    file_store: Annotated[OriginalFileStore, Depends(get_original_file_store)],
) -> ConfirmImport:
    return ConfirmImport(source, repository, file_store)


def get_list_imports(
    repository: Annotated[ImportRepository, Depends(get_import_repository)],
) -> ListImports:
    return ListImports(repository)


def get_import_detail(
    repository: Annotated[ImportRepository, Depends(get_import_repository)],
) -> GetImportDetail:
    return GetImportDetail(repository)
