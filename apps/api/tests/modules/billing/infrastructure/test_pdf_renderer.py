"""The PDF is deterministic: same invoice, same bytes, provable by checksum."""

from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from app.modules.billing.domain.invoice import InvoiceItemView, InvoiceView
from app.modules.billing.domain.rendering import InvoiceDocumentContext
from app.modules.billing.infrastructure.pdf_renderer import PdfInvoiceRenderer

CONTEXT = InvoiceDocumentContext(
    organization_name="Condomínio Jardim",
    site_name="Garagem",
    timezone="America/Sao_Paulo",
    tariff_name="Referência Sprint 1",
    tariff_source="sprint1_reference",
    tariff_source_reference=None,
    tariff_valid_from=date(2026, 1, 1),
    tariff_valid_to=None,
    policy_name="Referência Sprint 1",
    infra_fee_cents=2500,
    loss_basis_points=400,
    provenances=("simulated",),
)


def _invoice(number: str) -> InvoiceView:
    return InvoiceView(
        id=UUID(int=1),
        number=number,
        billing_period_id=UUID(int=2),
        period_value="2026-05",
        unit_id=UUID(int=3),
        unit_code="A-101",
        unit_name="Unidade A-101",
        contact_label="Moradora A-101",
        energy_kwh=Decimal("10.500"),
        energy_value_cents=1313,
        infra_fee_cents=2500,
        loss_share_cents=53,
        total_cents=3866,
        issued_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        items=(
            InvoiceItemView(
                id=UUID(int=4),
                charging_session_id=UUID(int=5),
                started_at=datetime(2026, 5, 10, 21, 30, tzinfo=UTC),
                ended_at=datetime(2026, 5, 10, 23, 45, tzinfo=UTC),
                energy_kwh=Decimal("10.500"),
                band_code="ponta",
                rate_cents_per_kwh=125,
                value_cents=1313,
            ),
        ),
    )


def test_rendering_twice_yields_byte_identical_documents() -> None:
    renderer = PdfInvoiceRenderer()
    first = renderer.render(_invoice("FAT-2026-05-A-101"), CONTEXT)
    second = renderer.render(_invoice("FAT-2026-05-A-101"), CONTEXT)

    assert first.startswith(b"%PDF")
    assert sha256(first).hexdigest() == sha256(second).hexdigest()
    assert first == second


def test_different_invoices_render_different_documents() -> None:
    renderer = PdfInvoiceRenderer()
    first = renderer.render(_invoice("FAT-2026-05-A-101"), CONTEXT)
    other = renderer.render(_invoice("FAT-2026-05-B-202"), CONTEXT)

    assert first != other
