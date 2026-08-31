from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.modules.billing.application.ports import BillingRepository
from app.modules.billing.application.render_invoice import RenderInvoiceDocument
from app.modules.billing.infrastructure.pdf_renderer import PdfInvoiceRenderer
from app.modules.billing.infrastructure.repository import SqlAlchemyBillingRepository
from app.modules.identity.domain.auth import OrganizationRole, OrganizationScope
from app.modules.identity.presentation.dependencies import current_scope
from app.shared.database import get_db_session


def get_billing_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BillingRepository:
    return SqlAlchemyBillingRepository(session)


def get_open_billing_period(
    repository: Annotated[BillingRepository, Depends(get_billing_repository)],
) -> OpenBillingPeriod:
    return OpenBillingPeriod(repository)


def get_list_billing_periods(
    repository: Annotated[BillingRepository, Depends(get_billing_repository)],
) -> ListBillingPeriods:
    return ListBillingPeriods(repository)


def get_period_readiness(
    repository: Annotated[BillingRepository, Depends(get_billing_repository)],
) -> GetPeriodReadiness:
    return GetPeriodReadiness(repository)


def get_generate_closing_opinion(
    repository: Annotated[BillingRepository, Depends(get_billing_repository)],
) -> GenerateClosingOpinion:
    return GenerateClosingOpinion(repository)


def get_close_billing_period(
    repository: Annotated[BillingRepository, Depends(get_billing_repository)],
) -> CloseBillingPeriod:
    return CloseBillingPeriod(repository)


def get_list_invoices(
    repository: Annotated[BillingRepository, Depends(get_billing_repository)],
) -> ListInvoices:
    return ListInvoices(repository)


def get_list_findings(
    repository: Annotated[BillingRepository, Depends(get_billing_repository)],
) -> ListFindings:
    return ListFindings(repository)


def get_decide_finding(
    repository: Annotated[BillingRepository, Depends(get_billing_repository)],
) -> DecideFinding:
    return DecideFinding(repository)


def get_get_invoice_detail(
    repository: Annotated[BillingRepository, Depends(get_billing_repository)],
) -> GetInvoiceDetail:
    return GetInvoiceDetail(repository)


def get_render_invoice_document(
    repository: Annotated[BillingRepository, Depends(get_billing_repository)],
) -> RenderInvoiceDocument:
    return RenderInvoiceDocument(repository, PdfInvoiceRenderer())


async def billing_reader_scope(
    scope: Annotated[OrganizationScope, Depends(current_scope)],
) -> OrganizationScope:
    """Managers, or a resident context scoped to its one unit."""
    if scope.role is OrganizationRole.MANAGER:
        return scope
    if scope.role is OrganizationRole.RESIDENT and scope.unit_id is not None:
        return scope
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Manager role or resident context required.",
    )
