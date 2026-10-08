"""The document states the stored integers. It never does arithmetic."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from app.modules.billing.domain.invoice import InvoiceItemView, InvoiceView
from app.modules.billing.domain.rendering import (
    InvoiceDocumentContext,
    format_brl,
    invoice_document_lines,
    provenance_label,
)


def _context(**overrides: object) -> InvoiceDocumentContext:
    values: dict[str, object] = {
        "organization_name": "Condomínio Jardim",
        "site_name": "Garagem",
        "timezone": "America/Sao_Paulo",
        "tariff_name": "Referência Sprint 1",
        "tariff_source": "sprint1_reference",
        "tariff_source_reference": None,
        "tariff_valid_from": date(2026, 1, 1),
        "tariff_valid_to": None,
        "policy_name": "Referência Sprint 1",
        "infra_fee_cents": 2500,
        "loss_basis_points": 400,
        "provenances": ("simulated",),
    }
    values.update(overrides)
    return InvoiceDocumentContext(**values)  # type: ignore[arg-type]


def _invoice(
    items: tuple[InvoiceItemView, ...],
    *,
    energy_value_cents: int,
    total_cents: int,
) -> InvoiceView:
    return InvoiceView(
        id=UUID(int=1),
        number="FAT-2026-05-A-101",
        billing_period_id=UUID(int=2),
        period_value="2026-05",
        unit_id=UUID(int=3),
        unit_code="A-101",
        unit_name="Unidade A-101",
        contact_label="Moradora A-101",
        energy_kwh=Decimal("17.703"),
        energy_value_cents=energy_value_cents,
        infra_fee_cents=2500,
        loss_share_cents=55,
        total_cents=total_cents,
        issued_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        items=items,
    )


def _item() -> InvoiceItemView:
    return InvoiceItemView(
        id=UUID(int=4),
        charging_session_id=UUID(int=5),
        started_at=datetime(2026, 5, 10, 21, 30, tzinfo=UTC),
        ended_at=datetime(2026, 5, 10, 23, 45, tzinfo=UTC),
        energy_kwh=Decimal("10.500"),
        band_code="ponta",
        rate_cents_per_kwh=125,
        value_cents=1313,
    )


def test_format_brl_groups_thousands_with_comma_cents() -> None:
    assert format_brl(0) == "R$ 0,00"
    assert format_brl(55) == "R$ 0,55"
    assert format_brl(1_234_56) == "R$ 1.234,56"


def test_lines_state_the_stored_integers_without_recomputing() -> None:
    """A deliberately inconsistent total is printed as stored, proving the
    renderer does no arithmetic of its own."""
    invoice = _invoice((_item(),), energy_value_cents=9999, total_cents=1)
    lines = invoice_document_lines(invoice, _context())

    assert "Energia: R$ 99,99" in lines
    assert "Total: R$ 0,01" in lines
    assert any("R$ 13,13" in line for line in lines)


def test_item_times_are_shown_in_the_site_timezone() -> None:
    """21:30 UTC on 10 May is 18:30 in São Paulo, the peak band."""
    invoice = _invoice((_item(),), energy_value_cents=1313, total_cents=3868)
    lines = invoice_document_lines(invoice, _context())

    item_line = next(line for line in lines if "Ponta" in line)
    assert "10/05/2026 18:30 a 20:45" in item_line
    assert "(2h15)" in item_line
    assert "10,500 kWh" in item_line
    assert "125 centavos/kWh" in item_line


def test_zero_invoice_says_so_instead_of_an_empty_table() -> None:
    invoice = _invoice((), energy_value_cents=0, total_cents=0)
    lines = invoice_document_lines(invoice, _context(provenances=()))

    assert "Sem recargas no período. Sem consumo, nada é cobrado." in lines
    assert "Procedência: sem recargas no período" in lines


def test_provenance_labels_are_plain_language() -> None:
    assert provenance_label(("simulated",)) == "dados simulados"
    assert provenance_label(("real", "simulated")) == "dados reais, dados simulados"


def test_tariff_block_cites_source_and_validity() -> None:
    invoice = _invoice((_item(),), energy_value_cents=1313, total_cents=3868)
    lines = invoice_document_lines(
        invoice,
        _context(
            tariff_valid_to=date(2026, 12, 31),
            tariff_source_reference="README.md secao 5.2",
        ),
    )

    # The stored source is a classifier; the document prints what it means.
    assert (
        "Tarifa: Referência Sprint 1 (fonte: Tabela de referência do desafio)"
    ) in lines
    assert "Vigência: 01/01/2026 a 31/12/2026" in lines
    assert (
        "Política de rateio: Referência Sprint 1 "
        "(taxa R$ 25,00 por unidade ativa, perdas 4,00%)"
    ) in lines
    assert "Referência da tarifa: README.md secao 5.2" in lines
