"""Typesetting of the invoice document with fpdf2.

Every figure printed here comes from `invoice_document_lines`, which reads only
the persisted invoice and its frozen context. The renderer adds typography,
never arithmetic. The creation date is pinned to the invoice's `issued_at`, so
rendering the same invoice twice yields byte-identical files and the stored
checksum can prove it.
"""

from fpdf import FPDF

from app.modules.billing.domain.invoice import InvoiceView
from app.modules.billing.domain.rendering import (
    InvoiceDocumentContext,
    invoice_document_lines,
)

_HEADING_PREFIXES = ("Quanto e por quê", "De onde veio", "Por que esta tarifa")
_MARGIN = 18
_LINE_HEIGHT = 6


class PdfInvoiceRenderer:
    def render(
        self, invoice: InvoiceView, context: InvoiceDocumentContext
    ) -> bytes:
        pdf = FPDF(format="A4")
        pdf.set_creation_date(invoice.issued_at)
        pdf.set_margins(_MARGIN, _MARGIN)
        pdf.set_auto_page_break(auto=True, margin=_MARGIN)
        pdf.add_page()

        lines = invoice_document_lines(invoice, context)
        width = pdf.w - 2 * _MARGIN
        for index, line in enumerate(lines):
            if not line:
                pdf.ln(_LINE_HEIGHT / 2)
                continue
            if index == 0:
                pdf.set_font("helvetica", style="B", size=16)
            elif line.startswith(_HEADING_PREFIXES):
                pdf.set_font("helvetica", style="B", size=12)
            elif line.startswith("Total:"):
                pdf.set_font("helvetica", style="B", size=11)
            else:
                pdf.set_font("helvetica", size=10)
            pdf.multi_cell(width, _LINE_HEIGHT, line)
        return bytes(pdf.output())
