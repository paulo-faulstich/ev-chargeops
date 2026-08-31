from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response

from app.modules.billing.application.manage_periods import (
    CloseBillingPeriod,
    DecideFinding,
    GenerateClosingOpinion,
    GetInvoiceDetail,
    GetPeriodReadiness,
    ListBillingPeriods,
    ListFindings,
    ListInvoices,
    OpenBillingPeriod,
)
from app.modules.billing.application.render_invoice import RenderInvoiceDocument
from app.modules.billing.domain.errors import (
    FindingAlreadyDecided,
    FindingNotFound,
    InvalidPeriodValue,
    InvoiceNotFound,
    PeriodCloseBlocked,
    PeriodCloseConflict,
    PeriodNotFound,
    SiteNotFound,
)
from app.modules.billing.domain.period import PeriodStatus
from app.modules.billing.domain.readiness import Blocker
from app.modules.billing.presentation.dependencies import (
    billing_reader_scope,
    get_close_billing_period,
    get_decide_finding,
    get_generate_closing_opinion,
    get_get_invoice_detail,
    get_list_billing_periods,
    get_list_findings,
    get_list_invoices,
    get_open_billing_period,
    get_period_readiness,
    get_render_invoice_document,
)
from app.modules.billing.presentation.schemas import (
    BillingPeriodListResponse,
    BillingPeriodResponse,
    BlockerResponse,
    CloseConflictResponse,
    ClosePeriodResponse,
    ClosingOpinionResponse,
    DecideFindingRequest,
    FindingListResponse,
    InvoiceContextResponse,
    InvoiceDetailResponse,
    InvoiceListResponse,
    InvoiceResponse,
    OpenBillingPeriodRequest,
    PeriodOpinionResponse,
    PeriodReadinessResponse,
    PersistedFindingResponse,
    ReadinessResponse,
    TariffBandResponse,
)
from app.modules.identity.domain.auth import OrganizationScope
from app.modules.ingestion.presentation.schemas import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    HttpErrorResponse,
)
from app.modules.sessions.presentation.dependencies import manager_scope
from app.modules.sessions.presentation.router import (
    StructuredValidationRoute,
    validation_error,
)

router = APIRouter(
    prefix="/v1",
    tags=["billing"],
    route_class=StructuredValidationRoute,
)

AUTH_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {
        "model": HttpErrorResponse,
        "description": "Invalid or missing bearer token.",
    },
    403: {
        "model": HttpErrorResponse,
        "description": "Organization membership and manager role required.",
    },
}

NOT_FOUND_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {
        "model": HttpErrorResponse,
        "description": "Period not found in this organization.",
    },
}


def not_found(code: str, message: str) -> JSONResponse:
    """Cross-tenant reads look identical to a missing record, on purpose."""
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=[]))
    return JSONResponse(status_code=404, content=body.model_dump(by_alias=True))


@router.get(
    "/billing-periods",
    response_model=BillingPeriodListResponse,
    response_model_by_alias=True,
    responses=AUTH_ERROR_RESPONSES,
)
async def list_billing_periods(
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[ListBillingPeriods, Depends(get_list_billing_periods)],
) -> BillingPeriodListResponse:
    periods = await use_case.execute(scope)
    return BillingPeriodListResponse(
        items=[BillingPeriodResponse.from_view(period) for period in periods]
    )


@router.post(
    "/billing-periods",
    response_model=BillingPeriodResponse,
    response_model_by_alias=True,
    responses={
        **AUTH_ERROR_RESPONSES,
        404: {
            "model": HttpErrorResponse,
            "description": "Site not found in this organization.",
        },
        422: {"model": ErrorResponse, "description": "Invalid period value."},
    },
)
async def open_billing_period(
    payload: OpenBillingPeriodRequest,
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[OpenBillingPeriod, Depends(get_open_billing_period)],
) -> BillingPeriodResponse | JSONResponse:
    """Open the month, or return the one already open. Opening is idempotent."""
    try:
        period = await use_case.execute(scope, payload.period_value, payload.site_id)
    except InvalidPeriodValue:
        return validation_error(
            code="INVALID_PERIOD",
            message="Period must use YYYY-MM format.",
            field="periodValue",
        )
    except SiteNotFound:
        return not_found("SITE_NOT_FOUND", "Local não encontrado.")
    return BillingPeriodResponse.from_view(period)


@router.get(
    "/billing-periods/{period_id}",
    response_model=BillingPeriodResponse,
    response_model_by_alias=True,
    responses={**AUTH_ERROR_RESPONSES, **NOT_FOUND_RESPONSES},
)
async def get_billing_period(
    period_id: UUID,
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[GetPeriodReadiness, Depends(get_period_readiness)],
) -> BillingPeriodResponse | JSONResponse:
    try:
        period, _ = await use_case.execute(scope, period_id)
    except PeriodNotFound:
        return not_found("PERIOD_NOT_FOUND", "Período não encontrado.")
    return BillingPeriodResponse.from_view(period)


@router.get(
    "/billing-periods/{period_id}/readiness",
    response_model=PeriodReadinessResponse,
    response_model_by_alias=True,
    responses={**AUTH_ERROR_RESPONSES, **NOT_FOUND_RESPONSES},
)
async def get_billing_period_readiness(
    period_id: UUID,
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[GetPeriodReadiness, Depends(get_period_readiness)],
) -> PeriodReadinessResponse | JSONResponse:
    """Coverage, blockers and both reconciliations for the period."""
    try:
        period, readiness = await use_case.execute(scope, period_id)
    except PeriodNotFound:
        return not_found("PERIOD_NOT_FOUND", "Período não encontrado.")
    return PeriodReadinessResponse(
        period=BillingPeriodResponse.from_view(period),
        readiness=ReadinessResponse.from_domain(readiness),
    )


@router.post(
    "/billing-periods/{period_id}/closing-opinion",
    response_model=PeriodOpinionResponse,
    response_model_by_alias=True,
    responses={**AUTH_ERROR_RESPONSES, **NOT_FOUND_RESPONSES},
)
async def generate_closing_opinion(
    period_id: UUID,
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[GenerateClosingOpinion, Depends(get_generate_closing_opinion)],
) -> PeriodOpinionResponse | JSONResponse:
    """Analyse the period and record the run the manager will approve against."""
    try:
        period, opinion, run_id = await use_case.execute(scope, period_id)
    except PeriodNotFound:
        return not_found("PERIOD_NOT_FOUND", "Período não encontrado.")
    return PeriodOpinionResponse(
        period=BillingPeriodResponse.from_view(period),
        opinion=ClosingOpinionResponse.from_domain(opinion, run_id),
    )


@router.get(
    "/billing-periods/{period_id}/findings",
    response_model=FindingListResponse,
    response_model_by_alias=True,
    responses={**AUTH_ERROR_RESPONSES, **NOT_FOUND_RESPONSES},
)
async def list_findings(
    period_id: UUID,
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[ListFindings, Depends(get_list_findings)],
) -> FindingListResponse:
    """The latest opinion's findings, each addressable and with its decision."""
    findings = await use_case.execute(scope, period_id)
    return FindingListResponse(
        items=[PersistedFindingResponse.from_domain(f) for f in findings]
    )


@router.post(
    "/billing-periods/{period_id}/findings/{finding_id}/decision",
    response_model=PersistedFindingResponse,
    response_model_by_alias=True,
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        409: {
            "model": HttpErrorResponse,
            "description": "The finding already carries a decision.",
        },
    },
)
async def decide_finding(
    period_id: UUID,
    finding_id: UUID,
    payload: DecideFindingRequest,
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[DecideFinding, Depends(get_decide_finding)],
) -> PersistedFindingResponse | JSONResponse:
    """Accept a finding, on the record, so it stops blocking the close.

    A critical finding is the analysis refusing to let the period close
    silently. Clearing it is a manager decision with a reason attached, never a
    dismissal.
    """
    try:
        finding = await use_case.execute(
            scope, period_id, finding_id, payload.note
        )
    except FindingNotFound:
        return not_found("FINDING_NOT_FOUND", "Achado não encontrado.")
    except FindingAlreadyDecided:
        body = ErrorResponse(
            error=ErrorBody(
                code="FINDING_ALREADY_DECIDED",
                message="Este achado já possui uma decisão registrada.",
                details=[],
            )
        )
        return JSONResponse(
            status_code=409, content=body.model_dump(by_alias=True)
        )
    return PersistedFindingResponse.from_domain(finding)


def close_conflict(
    code: str, message: str, blockers: tuple[Blocker, ...] = ()
) -> JSONResponse:
    body = CloseConflictResponse(
        code=code,
        message=message,
        blockers=[BlockerResponse.from_domain(blocker) for blocker in blockers],
    )
    return JSONResponse(
        status_code=409, content=body.model_dump(by_alias=True, mode="json")
    )


@router.post(
    "/billing-periods/{period_id}/close",
    response_model=ClosePeriodResponse,
    response_model_by_alias=True,
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        409: {
            "model": CloseConflictResponse,
            "description": (
                "Close refused: blockers remain, the period is already "
                "closed, or another close is in flight. Nothing was changed."
            ),
        },
    },
)
async def close_billing_period(
    period_id: UUID,
    scope: Annotated[OrganizationScope, Depends(manager_scope)],
    use_case: Annotated[CloseBillingPeriod, Depends(get_close_billing_period)],
) -> ClosePeriodResponse | JSONResponse:
    """Approve the close and issue the period's invoices, in one transaction."""
    try:
        period, invoices = await use_case.execute(scope, period_id)
    except PeriodNotFound:
        return not_found("PERIOD_NOT_FOUND", "Período não encontrado.")
    except PeriodCloseBlocked as blocked:
        return close_conflict(
            "CLOSE_BLOCKED",
            "O período não pode ser fechado enquanto houver bloqueios.",
            blocked.blockers,
        )
    except PeriodCloseConflict as conflict:
        if conflict.status == PeriodStatus.CLOSED.value:
            return close_conflict(
                "PERIOD_ALREADY_CLOSED",
                "O período já foi fechado. Nada foi alterado.",
            )
        return close_conflict(
            "CLOSE_IN_PROGRESS",
            "Outro fechamento deste período está em andamento.",
        )
    return ClosePeriodResponse(
        period=BillingPeriodResponse.from_view(period),
        invoices=[InvoiceResponse.from_view(invoice) for invoice in invoices],
    )


@router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    response_model_by_alias=True,
    responses=AUTH_ERROR_RESPONSES,
)
async def list_invoices(
    scope: Annotated[OrganizationScope, Depends(billing_reader_scope)],
    use_case: Annotated[ListInvoices, Depends(get_list_invoices)],
    period_id: Annotated[UUID | None, Query(alias="periodId")] = None,
    unit_id: Annotated[UUID | None, Query(alias="unitId")] = None,
) -> InvoiceListResponse:
    invoices = await use_case.execute(scope, period_id=period_id, unit_id=unit_id)
    return InvoiceListResponse(
        items=[InvoiceResponse.from_view(invoice) for invoice in invoices]
    )


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceDetailResponse,
    response_model_by_alias=True,
    responses={
        **AUTH_ERROR_RESPONSES,
        404: {
            "model": HttpErrorResponse,
            "description": "Invoice not found in this organization.",
        },
    },
)
async def get_invoice(
    invoice_id: UUID,
    scope: Annotated[OrganizationScope, Depends(billing_reader_scope)],
    use_case: Annotated[GetInvoiceDetail, Depends(get_get_invoice_detail)],
) -> InvoiceDetailResponse | JSONResponse:
    """The invoice with the frozen records it cites.

    The tariff and policy come from the snapshot frozen at close, so this page
    keeps stating what the invoice was issued under even after a newer tariff
    is registered.
    """
    try:
        invoice, context, bands = await use_case.execute(scope, invoice_id)
    except InvoiceNotFound:
        return not_found("INVOICE_NOT_FOUND", "Fatura não encontrada.")
    energies = tuple(item.energy_kwh for item in invoice.items)
    return InvoiceDetailResponse(
        invoice=InvoiceResponse.from_view(invoice),
        context=InvoiceContextResponse.from_domain(context),
        bands=[
            TariffBandResponse.from_domain(band, energies) for band in bands
        ],
    )


@router.get(
    "/invoices/{invoice_id}/document",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {
            "content": {"application/pdf": {}},
            "description": "The invoice document, rendered from stored values.",
        },
        404: {
            "model": HttpErrorResponse,
            "description": "Invoice not found in this organization.",
        },
    },
)
async def download_invoice_document(
    invoice_id: UUID,
    scope: Annotated[OrganizationScope, Depends(billing_reader_scope)],
    use_case: Annotated[
        RenderInvoiceDocument, Depends(get_render_invoice_document)
    ],
) -> Response:
    """Stream the PDF. Two downloads of one invoice are provably identical."""
    try:
        invoice, document, checksum = await use_case.execute(scope, invoice_id)
    except InvoiceNotFound:
        return not_found("INVOICE_NOT_FOUND", "Fatura não encontrada.")
    return Response(
        content=document,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{invoice.number}.pdf"'
            ),
            "ETag": f'"{checksum}"',
        },
    )


__all__ = ["ErrorDetail", "router"]
