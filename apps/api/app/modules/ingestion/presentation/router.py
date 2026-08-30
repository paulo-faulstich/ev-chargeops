from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app.modules.ingestion.application.preview_import import PreviewImport
from app.modules.ingestion.domain.errors import InvalidSession
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource
from app.modules.ingestion.presentation.schemas import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    ImportPreviewResponse,
)

router = APIRouter(prefix="/v1/import-batches", tags=["imports"])


def preview_use_case() -> PreviewImport:
    return PreviewImport(SemsCsvSource(ZoneInfo("America/Sao_Paulo")))


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    response_model_by_alias=True,
    responses={422: {"model": ErrorResponse}},
)
async def preview_import(
    file: Annotated[UploadFile, File(...)],
    use_case: Annotated[PreviewImport, Depends(preview_use_case)],
) -> ImportPreviewResponse | JSONResponse:
    try:
        result = use_case.execute(file.filename or "", await file.read())
    except InvalidSession as error:
        body = ErrorResponse(
            error=ErrorBody(
                code=error.code,
                message=error.message,
                details=[ErrorDetail(field=error.field)],
            )
        )
        return JSONResponse(
            status_code=422,
            content=body.model_dump(by_alias=True),
        )
    return ImportPreviewResponse.from_result(result)
