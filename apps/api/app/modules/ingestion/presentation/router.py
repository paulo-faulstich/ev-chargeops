from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse

from app.modules.identity.domain.auth import OrganizationScope
from app.modules.identity.presentation.dependencies import current_scope
from app.modules.ingestion.application.confirm_import import ConfirmImport
from app.modules.ingestion.application.list_imports import GetImportDetail, ListImports
from app.modules.ingestion.application.preview_import import PreviewImport
from app.modules.ingestion.application.review_import import ReviewImport
from app.modules.ingestion.domain.errors import InvalidSession
from app.modules.ingestion.infrastructure.sems_csv_source import SemsCsvSource
from app.modules.ingestion.presentation.dependencies import (
    get_confirm_import,
    get_import_detail,
    get_list_imports,
    get_review_import,
)
from app.modules.ingestion.presentation.schemas import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    ImportBatchDetailResponse,
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportPreviewResponse,
)

router = APIRouter(prefix="/v1/import-batches", tags=["imports"])


def preview_use_case() -> PreviewImport:
    return PreviewImport(SemsCsvSource(ZoneInfo("America/Sao_Paulo")))


def error_response(error: InvalidSession) -> JSONResponse:
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


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    response_model_by_alias=True,
    responses={422: {"model": ErrorResponse}},
)
async def preview_import(
    scope: Annotated[OrganizationScope, Depends(current_scope)],
    reviewer: Annotated[ReviewImport, Depends(get_review_import)],
    use_case: Annotated[PreviewImport, Depends(preview_use_case)],
    file: Annotated[UploadFile | None, File()] = None,
) -> ImportPreviewResponse | JSONResponse:
    if file is None:
        return error_response(
            InvalidSession("file", "FILE_REQUIRED", "A file is required.")
        )
    try:
        parsed = use_case.execute(file.filename or "", await file.read())
    except InvalidSession as error:
        return error_response(error)
    result = await reviewer.execute(scope, parsed)
    return ImportPreviewResponse.from_result(result)


@router.post(
    "",
    response_model=ImportBatchResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": ImportBatchResponse},
        422: {"model": ErrorResponse},
    },
)
async def confirm_import(
    response: Response,
    scope: Annotated[OrganizationScope, Depends(current_scope)],
    use_case: Annotated[ConfirmImport, Depends(get_confirm_import)],
    file: Annotated[UploadFile | None, File()] = None,
) -> ImportBatchResponse | JSONResponse:
    if file is None:
        return error_response(
            InvalidSession("file", "FILE_REQUIRED", "A file is required.")
        )
    try:
        result = await use_case.execute(
            scope,
            file.filename or "",
            await file.read(),
        )
    except InvalidSession as error:
        return error_response(error)
    response.status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )
    return ImportBatchResponse.from_result(result)


@router.get(
    "",
    response_model=ImportBatchListResponse,
    response_model_by_alias=True,
)
async def list_import_batches(
    scope: Annotated[OrganizationScope, Depends(current_scope)],
    use_case: Annotated[ListImports, Depends(get_list_imports)],
) -> ImportBatchListResponse:
    batches = await use_case.execute(scope)
    return ImportBatchListResponse(
        items=[ImportBatchResponse.from_result(batch) for batch in batches]
    )


@router.get(
    "/{batch_id}",
    response_model=ImportBatchDetailResponse,
    response_model_by_alias=True,
)
async def get_import_batch(
    batch_id: UUID,
    scope: Annotated[OrganizationScope, Depends(current_scope)],
    use_case: Annotated[GetImportDetail, Depends(get_import_detail)],
) -> ImportBatchDetailResponse:
    detail = await use_case.execute(scope, batch_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Import batch not found.")
    return ImportBatchDetailResponse.from_detail(detail)
