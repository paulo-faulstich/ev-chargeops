from hashlib import sha256
from uuid import UUID

from app.modules.billing.application.manage_periods import reader_unit_filter
from app.modules.billing.application.ports import BillingRepository
from app.modules.billing.domain.invoice import InvoiceView
from app.modules.billing.domain.rendering import InvoiceRenderer
from app.modules.identity.domain.auth import OrganizationScope


class RenderInvoiceDocument:
    """Render the invoice PDF from its persisted integers and prove identity.

    The first download records the document's checksum; every later download is
    hashed against it, so two downloads of one invoice are provably the same
    file. A mismatch is a rendering defect and is raised, never served.
    """

    def __init__(
        self, repository: BillingRepository, renderer: InvoiceRenderer
    ) -> None:
        self.repository = repository
        self.renderer = renderer

    async def execute(
        self,
        scope: OrganizationScope,
        invoice_id: UUID,
    ) -> tuple[InvoiceView, bytes, str]:
        invoice, context = await self.repository.load_invoice_document_context(
            scope.organization_id, invoice_id, unit_id=reader_unit_filter(scope)
        )
        document = self.renderer.render(invoice, context)
        checksum = sha256(document).hexdigest()
        await self.repository.record_invoice_document(
            scope.organization_id, invoice.id, checksum, len(document)
        )
        return invoice, document, checksum
